"""PDF settings per organization — branding and format configuration."""
import uuid
from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class PdfSettings(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "pdf_settings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        unique=True, nullable=False, index=True
    )
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    page_format: Mapped[str] = mapped_column(
        String(10), nullable=False, default="a4"
    )  # 'a4' | 'letter'
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="de"
    )  # 'de' | 'en'
    header_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    footer_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    letterhead_filename: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # file stored at {PDF_TEMPLATES_PATH}/{org_id}/letterhead.pdf
    logo_filename: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # file stored at {PDF_TEMPLATES_PATH}/{org_id}/logo.png
