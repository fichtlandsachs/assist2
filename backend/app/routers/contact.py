"""Public contact/demo-booking endpoint — no authentication required."""
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.system_settings_service import RuntimeSettings, get_runtime_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Contact"])


class DemoBookingRequest(BaseModel):
    name: str
    company: str
    email: EmailStr
    phone: str = ""
    team_size: str = ""
    message: str = ""

    @field_validator("name", "company")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("Mindestens 2 Zeichen erforderlich")
        return v.strip()

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        return v.strip()


def _send_email_sync(data: DemoBookingRequest, s: RuntimeSettings) -> None:
    body = f"""Neue Demo-Anfrage von heykarl.app

Name:         {data.name}
Unternehmen:  {data.company}
E-Mail:       {data.email}
Telefon:      {data.phone or '—'}
Teamgröße:    {data.team_size or '—'}

Nachricht:
{data.message or '(keine)'}
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Demo-Anfrage: {data.name} ({data.company})"
    msg["From"] = s.SMTP_FROM
    msg["To"] = s.CONTACT_EMAIL_TO
    msg["Reply-To"] = str(data.email)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if s.SMTP_USER and s.SMTP_PASS:
        if s.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(s.SMTP_HOST, s.SMTP_PORT, timeout=10) as conn:
                conn.login(s.SMTP_USER, s.SMTP_PASS)
                conn.sendmail(s.SMTP_FROM, [s.CONTACT_EMAIL_TO], msg.as_string())
        else:
            with smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=10) as conn:
                conn.ehlo()
                conn.starttls()
                conn.login(s.SMTP_USER, s.SMTP_PASS)
                conn.sendmail(s.SMTP_FROM, [s.CONTACT_EMAIL_TO], msg.as_string())
    else:
        with smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=10) as conn:
            conn.ehlo("heykarl.app")
            conn.sendmail(s.SMTP_FROM, [s.CONTACT_EMAIL_TO], msg.as_string())


@router.post("/contact/demo", status_code=200)
async def book_demo(
    data: DemoBookingRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Always log the request so no lead is lost even if email fails
    logger.info(
        "DEMO REQUEST — Name: %s | Company: %s | Email: %s | Phone: %s | TeamSize: %s | Message: %s",
        data.name, data.company, data.email, data.phone, data.team_size, data.message,
    )
    s = await get_runtime_settings(db)
    try:
        await asyncio.get_event_loop().run_in_executor(None, _send_email_sync, data, s)
    except Exception as e:
        logger.error("Demo booking email delivery failed (request still logged above): %s", e)
    return {"ok": True}
