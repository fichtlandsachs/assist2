"""PDF generation service: renders HTML template and calls Stirling PDF."""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings
from app.services.stirling_client import stirling_client

logger = logging.getLogger(__name__)

# Jinja2 env — loads templates from app/templates/
_template_dir = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_template_dir)),
    autoescape=select_autoescape(["html"]),
)


class PdfService:
    """Orchestrates HTML rendering + Stirling PDF conversion + local cache storage."""

    def render_html(
        self,
        story: Any,
        settings: Any,
        test_cases: List,
        features: List,
        creator_name: Optional[str] = None,
    ) -> str:
        """Render the Jinja2 template with story data. Returns HTML string."""
        docs: dict = {}
        if story.generated_docs:
            try:
                docs = json.loads(story.generated_docs)
            except (json.JSONDecodeError, TypeError):
                docs = {}

        dod_items: list = []
        if story.definition_of_done:
            try:
                dod_items = json.loads(story.definition_of_done)
            except (json.JSONDecodeError, TypeError):
                dod_items = []

        logo_path: Optional[str] = None
        if settings.logo_filename and hasattr(story, "organization_id"):
            cfg = get_settings()
            logo_path = str(
                Path(cfg.PDF_TEMPLATES_PATH) / str(story.organization_id) / settings.logo_filename
            )

        template = _jinja_env.get_template("userstory_pdf.html.jinja2")
        return template.render(
            story=story,
            settings=settings,
            test_cases=test_cases,
            features=features,
            docs=docs,
            dod_items=dod_items,
            logo_path=logo_path,
            creator_name=creator_name,
            generated_at=datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
        )

    async def generate_and_cache(
        self,
        story: Any,
        settings: Any,
        test_cases: List,
        features: List,
        creator_name: Optional[str] = None,
    ) -> str:
        """
        Render HTML, convert to PDF via Stirling, apply letterhead if configured,
        write to cache volume. Returns the filename (not full path).
        """
        cfg = get_settings()
        html = self.render_html(story, settings, test_cases, features, creator_name=creator_name)

        # Convert HTML → PDF
        pdf_bytes = await stirling_client.html_to_pdf(html)

        # Apply letterhead overlay if configured
        if settings.letterhead_filename and hasattr(story, "organization_id"):
            letterhead_path = (
                Path(cfg.PDF_TEMPLATES_PATH)
                / str(story.organization_id)
                / settings.letterhead_filename
            )
            if letterhead_path.exists():
                letterhead_bytes = letterhead_path.read_bytes()
                try:
                    pdf_bytes = await stirling_client.overlay_pdfs(pdf_bytes, letterhead_bytes)
                except Exception as e:
                    logger.warning(f"Letterhead overlay failed, using plain PDF: {e}")

        # Write to cache
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"{story.id}_{date_str}.pdf"
        cache_dir = Path(cfg.PDF_CACHE_PATH)
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / filename).write_bytes(pdf_bytes)

        logger.info(f"PDF cached: {filename} ({len(pdf_bytes)} bytes)")
        return filename


pdf_service = PdfService()
