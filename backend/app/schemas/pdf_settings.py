"""Pydantic schemas for PDF settings endpoints."""
import uuid
from typing import Optional

from pydantic import BaseModel, Field


class PdfSettingsBase(BaseModel):
    company_name: Optional[str] = Field(None, max_length=255)
    page_format: str = Field("a4", pattern="^(a4|letter)$")
    language: str = Field("de", pattern="^(de|en)$")
    header_text: Optional[str] = Field(None, max_length=500)
    footer_text: Optional[str] = Field(None, max_length=500)


class PdfSettingsUpdate(PdfSettingsBase):
    pass


class PdfSettingsRead(PdfSettingsBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    letterhead_filename: Optional[str] = None
    logo_filename: Optional[str] = None

    model_config = {"from_attributes": True}
