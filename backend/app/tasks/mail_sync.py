import asyncio
import email
import email.header
import imaplib
import ssl
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery
from app.config import get_settings
from app.core.security import decrypt_value
from app.services.ai_mail_service import cluster_messages_sync
import app.models  # ensure all models are registered with SQLAlchemy mapper
from app.models.mail_connection import MailConnection
from app.models.message import Message, MessageStatus


def _make_engine():
    settings = get_settings()
    return create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)


def _decode_header(raw: Optional[str]) -> Optional[str]:
    """Decode MIME-encoded email header."""
    if not raw:
        return None
    parts = []
    for part, charset in email.header.decode_header(raw):
        if isinstance(part, bytes):
            try:
                parts.append(part.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                parts.append(part.decode("utf-8", errors="replace"))
        else:
            parts.append(part)
    return "".join(parts)


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _get_body(msg: email.message.Message) -> Optional[str]:
    """Extract plain-text body."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return None


async def _run_sync(connection_id: str, org_id: str) -> dict:
    engine = _make_engine()
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        # Load connection
        stmt = select(MailConnection).where(MailConnection.id == uuid.UUID(connection_id))
        result = await db.execute(stmt)
        conn = result.scalar_one_or_none()
        if conn is None:
            return {"status": "error", "detail": "connection not found"}

        if not conn.imap_host or not conn.imap_password_enc:
            return {"status": "error", "detail": "IMAP credentials not configured"}

        # Decrypt password
        try:
            password = decrypt_value(conn.imap_password_enc)
        except Exception as e:
            return {"status": "error", "detail": f"decrypt failed: {e}"}

        host = conn.imap_host
        port = conn.imap_port or 993
        use_ssl = conn.imap_use_ssl if conn.imap_use_ssl is not None else True

        # Connect via IMAP (synchronous — run in executor)
        def do_imap():
            if use_ssl:
                ctx = ssl.create_default_context()
                imap = imaplib.IMAP4_SSL(host, port, ssl_context=ctx)
            else:
                imap = imaplib.IMAP4(host, port)
                try:
                    imap.starttls()
                except Exception:
                    pass
            imap.login(conn.email_address, password)
            imap.select("INBOX", readonly=True)

            # Fetch last 50 UIDs
            status, data = imap.uid("search", None, "ALL")
            if status != "OK":
                imap.logout()
                return []

            all_uids = data[0].split()
            uids = all_uids[-50:]  # newest 50

            messages_raw = []
            for uid in uids:
                status2, msg_data = imap.uid("fetch", uid, "(RFC822)")
                if status2 != "OK" or not msg_data or not msg_data[0]:
                    continue
                raw_email = msg_data[0][1]
                if not isinstance(raw_email, bytes):
                    continue
                messages_raw.append((uid.decode(), email.message_from_bytes(raw_email)))

            imap.logout()
            return messages_raw

        loop = asyncio.get_event_loop()
        try:
            messages_raw = await loop.run_in_executor(None, do_imap)
        except imaplib.IMAP4.error as e:
            return {"status": "error", "detail": f"IMAP error: {e}"}
        except Exception as e:
            return {"status": "error", "detail": f"connection failed: {e}"}

        # Persist messages
        saved = 0
        for uid_str, msg in messages_raw:
            external_id = f"{connection_id}:{uid_str}"

            # Skip existing
            exists = await db.execute(
                select(Message.id).where(Message.external_id == external_id)
            )
            if exists.scalar_one_or_none():
                continue

            from_raw = msg.get("From", "")
            sender_name: Optional[str] = None
            sender_email_addr = ""
            try:
                decoded_from = _decode_header(from_raw)
                parsed = email.utils.parseaddr(decoded_from or from_raw)
                sender_name = parsed[0] or None
                sender_email_addr = parsed[1] or from_raw
            except Exception:
                sender_email_addr = from_raw

            subject = _decode_header(msg.get("Subject"))
            body_text = _get_body(msg)
            snippet = (body_text or "")[:200].strip() or None
            received_at = _parse_date(msg.get("Date"))

            new_msg = Message(
                organization_id=uuid.UUID(org_id),
                connection_id=uuid.UUID(connection_id),
                external_id=external_id,
                subject=subject,
                sender_email=sender_email_addr,
                sender_name=sender_name,
                snippet=snippet,
                body_text=body_text,
                status=MessageStatus.unread,
                received_at=received_at,
            )
            db.add(new_msg)
            saved += 1

        # Flush to get IDs, then run AI clustering on new messages
        await db.flush()

        if saved > 0:
            # Fetch the newly inserted messages for clustering
            new_stmt = (
                select(Message)
                .where(
                    Message.connection_id == uuid.UUID(connection_id),
                    Message.topic_cluster == None,  # noqa: E711
                )
                .order_by(Message.received_at.desc())
                .limit(100)
            )
            new_result = await db.execute(new_stmt)
            msgs_to_cluster = new_result.scalars().all()

            if msgs_to_cluster:
                batch = [
                    {
                        "id": str(m.id),
                        "subject": m.subject,
                        "sender_email": m.sender_email,
                        "sender_name": m.sender_name,
                        "snippet": m.snippet,
                    }
                    for m in msgs_to_cluster
                ]
                # Run AI clustering (synchronous call, runs in worker process)
                clusters = cluster_messages_sync(batch)
                cluster_map = {c["id"]: c["topic_cluster"] for c in clusters if "id" in c and "topic_cluster" in c}
                for m in msgs_to_cluster:
                    if str(m.id) in cluster_map:
                        m.topic_cluster = cluster_map[str(m.id)]

        # Update last_sync_at
        await db.execute(
            update(MailConnection)
            .where(MailConnection.id == uuid.UUID(connection_id))
            .values(last_sync_at=datetime.now(timezone.utc))
        )
        await db.commit()

    await engine.dispose()
    return {"status": "ok", "saved": saved, "connection_id": connection_id}


@celery.task(name="mail_sync.sync_mailbox")
def sync_mailbox_task(connection_id: str, org_id: str):
    """Sync emails for a mail connection via IMAP."""
    result = asyncio.run(_run_sync(connection_id, org_id))
    return result


async def _run_recluster(org_id: str) -> dict:
    """Re-run AI clustering on all messages for an org that have no cluster yet."""
    engine = _make_engine()
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        stmt = (
            select(Message)
            .where(
                Message.organization_id == uuid.UUID(org_id),
                Message.topic_cluster == None,  # noqa: E711
            )
            .order_by(Message.received_at.desc())
            .limit(200)
        )
        result = await db.execute(stmt)
        msgs = result.scalars().all()

        if not msgs:
            await engine.dispose()
            return {"status": "ok", "clustered": 0}

        batch = [
            {
                "id": str(m.id),
                "subject": m.subject,
                "sender_email": m.sender_email,
                "sender_name": m.sender_name,
                "snippet": m.snippet,
            }
            for m in msgs
        ]
        clusters = cluster_messages_sync(batch)
        cluster_map = {c["id"]: c["topic_cluster"] for c in clusters if "id" in c and "topic_cluster" in c}
        for m in msgs:
            if str(m.id) in cluster_map:
                m.topic_cluster = cluster_map[str(m.id)]

        await db.commit()

    await engine.dispose()
    return {"status": "ok", "clustered": len(cluster_map)}


@celery.task(name="mail_sync.recluster_messages")
def recluster_messages_task(org_id: str):
    """Re-run AI topic clustering on all unclustered messages for an org."""
    return asyncio.run(_run_recluster(org_id))
