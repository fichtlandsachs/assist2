"""Public contact/demo-booking endpoint — no authentication required."""
import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, field_validator

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Contact"])
settings = get_settings()


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


def _send_email_sync(data: DemoBookingRequest) -> None:
    smtp_host = settings.SMTP_HOST
    smtp_port = settings.SMTP_PORT
    smtp_user = settings.SMTP_USER
    smtp_pass = settings.SMTP_PASS
    from_addr = settings.SMTP_FROM
    to_addr = settings.CONTACT_EMAIL_TO

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
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Reply-To"] = str(data.email)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        if smtp_user and smtp_pass:
            # Relay mode (STARTTLS on port 587 or SSL on 465)
            if smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as s:
                    s.login(smtp_user, smtp_pass)
                    s.sendmail(from_addr, [to_addr], msg.as_string())
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as s:
                    s.ehlo()
                    s.starttls()
                    s.login(smtp_user, smtp_pass)
                    s.sendmail(from_addr, [to_addr], msg.as_string())
        else:
            # Direct MX delivery (no credentials)
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as s:
                s.ehlo("heykarl.app")
                s.sendmail(from_addr, [to_addr], msg.as_string())
    except Exception as e:
        logger.error("Failed to send demo booking email: %s", e)
        raise


@router.post("/contact/demo", status_code=200)
async def book_demo(data: DemoBookingRequest):
    try:
        await asyncio.get_event_loop().run_in_executor(None, _send_email_sync, data)
    except Exception as e:
        logger.error("Demo booking email error: %s", e)
        raise HTTPException(status_code=502, detail="E-Mail konnte nicht gesendet werden. Bitte versuche es später erneut.")
    return {"ok": True}
