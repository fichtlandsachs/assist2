import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.mail_connection import MailConnection
from app.models.message import Message, MessageStatus
from app.schemas.inbox import MailConnectionCreate, MailConnectionRead, MessageRead, MessageUpdate, MailConnectionUpdate
from app.core.exceptions import NotFoundException
from app.core.security import encrypt_value
from app.tasks.mail_sync import sync_mailbox_task, recluster_messages_task

router = APIRouter()


@router.get(
    "/inbox/connections",
    response_model=List[MailConnectionRead],
    summary="List mail connections for an organization",
)
async def list_mail_connections(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[MailConnectionRead]:
    """List all mail connections for the given organization."""
    stmt = (
        select(MailConnection)
        .where(MailConnection.organization_id == org_id)
        .order_by(MailConnection.created_at.desc())
    )
    result = await db.execute(stmt)
    connections = result.scalars().all()
    return [MailConnectionRead.model_validate(c) for c in connections]


@router.post(
    "/inbox/connections",
    response_model=MailConnectionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a mail connection",
)
async def create_mail_connection(
    org_id: uuid.UUID,
    data: MailConnectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MailConnectionRead:
    """Create a new mail connection (manual, no OAuth)."""
    connection = MailConnection(
        organization_id=org_id,
        user_id=current_user.id,
        provider=data.provider,
        email_address=data.email_address,
        display_name=data.display_name,
        imap_host=data.imap_host if data.provider.value == "imap" else None,
        imap_port=data.imap_port if data.provider.value == "imap" else None,
        imap_use_ssl=data.imap_use_ssl if data.provider.value == "imap" else None,
        imap_password_enc=encrypt_value(data.imap_password) if data.provider.value == "imap" and data.imap_password else None,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return MailConnectionRead.model_validate(connection)


@router.delete(
    "/inbox/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a mail connection",
)
async def delete_mail_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove a mail connection."""
    stmt = select(MailConnection).where(MailConnection.id == connection_id)
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if connection is None:
        raise NotFoundException("Mail connection not found")
    await db.delete(connection)
    await db.commit()


@router.patch(
    "/inbox/connections/{connection_id}",
    response_model=MailConnectionRead,
    summary="Update a mail connection",
)
async def update_mail_connection(
    connection_id: uuid.UUID,
    data: MailConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MailConnectionRead:
    """Update sync interval or other settings for a mail connection."""
    stmt = select(MailConnection).where(MailConnection.id == connection_id)
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if connection is None:
        raise NotFoundException("Mail connection not found")
    if data.sync_interval_minutes is not None:
        connection.sync_interval_minutes = data.sync_interval_minutes
    if data.display_name is not None:
        connection.display_name = data.display_name
    if data.is_active is not None:
        connection.is_active = data.is_active
    await db.commit()
    await db.refresh(connection)
    return MailConnectionRead.model_validate(connection)


@router.get(
    "/inbox/messages",
    response_model=List[MessageRead],
    summary="List messages",
)
async def list_messages(
    org_id: uuid.UUID,
    connection_id: Optional[uuid.UUID] = None,
    message_status: Optional[MessageStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[MessageRead]:
    """List messages for an organization with optional filters."""
    stmt = select(Message).where(Message.organization_id == org_id)
    if connection_id is not None:
        stmt = stmt.where(Message.connection_id == connection_id)
    if message_status is not None:
        stmt = stmt.where(Message.status == message_status)
    stmt = stmt.order_by(Message.received_at.desc())
    result = await db.execute(stmt)
    messages = result.scalars().all()
    return [MessageRead.model_validate(m) for m in messages]


@router.patch(
    "/inbox/messages/{message_id}",
    response_model=MessageRead,
    summary="Update message status",
)
async def update_message(
    message_id: uuid.UUID,
    data: MessageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageRead:
    """Update the status of a message (read/archive/etc)."""
    stmt = select(Message).where(Message.id == message_id)
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()
    if message is None:
        raise NotFoundException("Message not found")
    message.status = data.status
    await db.commit()
    await db.refresh(message)
    return MessageRead.model_validate(message)


@router.post(
    "/inbox/connections/{connection_id}/sync",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger mailbox sync",
)
async def trigger_sync(
    connection_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Enqueue a Celery task to sync the mailbox."""
    stmt = select(MailConnection).where(MailConnection.id == connection_id)
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if connection is None:
        raise NotFoundException("Mail connection not found")
    sync_mailbox_task.delay(str(connection_id), str(org_id))
    return {"status": "queued", "connection_id": str(connection_id)}


@router.post(
    "/inbox/recluster",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-run AI topic clustering on all messages",
)
async def trigger_recluster(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Enqueue a Celery task to re-cluster all unclustered messages with AI."""
    recluster_messages_task.delay(str(org_id))
    return {"status": "queued", "org_id": str(org_id)}
