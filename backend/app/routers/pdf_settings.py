"""API endpoints for PDF settings (branding + template management)."""
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.pdf_settings import PdfSettings
from app.models.user import User
from app.schemas.pdf_settings import PdfSettingsRead, PdfSettingsUpdate
from app.services.stirling_client import stirling_client
from app.services.pdf_service import pdf_service

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_LETTERHEAD_BYTES = 5 * 1024 * 1024   # 5 MB
MAX_LOGO_BYTES = 1 * 1024 * 1024          # 1 MB
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg"}


async def _get_or_create_settings(org_id: uuid.UUID, db: AsyncSession) -> PdfSettings:
    result = await db.execute(
        select(PdfSettings).where(PdfSettings.organization_id == org_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = PdfSettings(organization_id=org_id)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


@router.get(
    "/organizations/{org_id}/pdf-settings",
    response_model=PdfSettingsRead,
    summary="Get PDF settings for an organization",
)
async def get_pdf_settings(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> PdfSettingsRead:
    row = await _get_or_create_settings(org_id, db)
    return PdfSettingsRead.model_validate(row)


@router.put(
    "/organizations/{org_id}/pdf-settings",
    response_model=PdfSettingsRead,
    summary="Update PDF settings for an organization",
)
async def update_pdf_settings(
    org_id: uuid.UUID,
    data: PdfSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> PdfSettingsRead:
    row = await _get_or_create_settings(org_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return PdfSettingsRead.model_validate(row)


@router.post(
    "/organizations/{org_id}/pdf-settings/letterhead",
    response_model=PdfSettingsRead,
    summary="Upload letterhead PDF",
)
async def upload_letterhead(
    org_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> PdfSettingsRead:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")
    content = await file.read()
    if len(content) > MAX_LETTERHEAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")

    cfg = get_settings()
    dest_dir = Path(cfg.PDF_TEMPLATES_PATH) / str(org_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "letterhead.pdf").write_bytes(content)

    row = await _get_or_create_settings(org_id, db)
    row.letterhead_filename = "letterhead.pdf"
    await db.commit()
    await db.refresh(row)
    return PdfSettingsRead.model_validate(row)


@router.delete(
    "/organizations/{org_id}/pdf-settings/letterhead",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove letterhead PDF",
)
async def delete_letterhead(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> None:
    row = await _get_or_create_settings(org_id, db)
    cfg = get_settings()
    path = Path(cfg.PDF_TEMPLATES_PATH) / str(org_id) / "letterhead.pdf"
    if path.exists():
        path.unlink()
    row.letterhead_filename = None
    await db.commit()


@router.post(
    "/organizations/{org_id}/pdf-settings/logo",
    response_model=PdfSettingsRead,
    summary="Upload logo image",
)
async def upload_logo(
    org_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> PdfSettingsRead:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="File must be PNG or JPEG")
    content = await file.read()
    if len(content) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 1 MB)")

    cfg = get_settings()
    dest_dir = Path(cfg.PDF_TEMPLATES_PATH) / str(org_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = "png" if file.content_type == "image/png" else "jpg"
    logo_filename = f"logo.{ext}"
    (dest_dir / logo_filename).write_bytes(content)

    row = await _get_or_create_settings(org_id, db)
    row.logo_filename = logo_filename
    await db.commit()
    await db.refresh(row)
    return PdfSettingsRead.model_validate(row)


@router.delete(
    "/organizations/{org_id}/pdf-settings/logo",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove logo",
)
async def delete_logo(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> None:
    row = await _get_or_create_settings(org_id, db)
    cfg = get_settings()
    for ext in ["png", "jpg"]:
        path = Path(cfg.PDF_TEMPLATES_PATH) / str(org_id) / f"logo.{ext}"
        if path.exists():
            path.unlink()
    row.logo_filename = None
    await db.commit()


@router.post(
    "/organizations/{org_id}/pdf-settings/preview",
    summary="Generate a preview PDF with current settings",
    response_class=Response,
)
async def preview_pdf(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> Response:
    """
    Synchronously generates a sample PDF using current settings.
    Returns raw PDF bytes (Content-Type: application/pdf).
    """
    import datetime
    from types import SimpleNamespace
    row = await _get_or_create_settings(org_id, db)
    sample_story = SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=org_id,
        title="Beispiel-Userstory: Login-Funktion",
        description="Als Nutzer möchte ich mich mit E-Mail und Passwort anmelden.",
        acceptance_criteria="Login funktioniert mit gültigen Zugangsdaten.",
        status=SimpleNamespace(value="done"),
        priority=SimpleNamespace(value="high"),
        story_points=3,
        quality_score=95,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        definition_of_done='["Tests grün", "Code reviewed", "Deployment erfolgreich"]',
        doc_additional_info=None,
        generated_docs='{"summary":"Implementiert ein sicheres Login-System.","technical_notes":"JWT-basiert.","changelog":"Version 1.0"}',
    )
    html = pdf_service.render_html(sample_story, row, test_cases=[], features=[])
    pdf_bytes = await stirling_client.html_to_pdf(html)
    return Response(content=pdf_bytes, media_type="application/pdf")
