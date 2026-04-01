"""Jira REST API proxy + ADF conversion + AI story generation."""
import json
import logging
import re
from typing import Any

import anthropic
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_JIRA_BASE = "https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3"
_TIMEOUT = httpx.Timeout(15.0)

_USERSTORY_SYSTEM = (
    "Du bist ein Experte für agile Anforderungsanalyse. "
    "Erstelle aus dem folgenden Jira-Ticket eine vollständige User Story im exakten Format:\n\n"
    "## User Story\n\n"
    "**Als** {Rolle aus Kontext}\n"
    "**möchte ich** {konkrete Funktionalität},\n"
    "**damit** {messbarer Nutzen}.\n\n"
    "---\n\n"
    "### Akzeptanzkriterien\n"
    "- [ ] {konkretes, testbares Kriterium}\n"
    "(mindestens 3, maximal 7)\n\n"
    "### Definition of Done\n"
    "- [ ] Code reviewed und gemergt\n"
    "- [ ] Unit Tests vorhanden (Coverage ≥ 80 %)\n"
    "- [ ] Acceptance Criteria manuell getestet\n"
    "- [ ] Dokumentation aktualisiert (falls relevant)\n"
    '- [ ] Ticket in Jira auf "Done" gesetzt\n\n'
    "### Technische Notizen\n"
    "{Nur wenn aus dem Ticket ableitbar — sonst diesen Abschnitt weglassen}\n\n"
    "Antworte NUR mit dem Markdown — kein JSON, kein Erklärungstext davor oder danach."
)


def adf_to_text(node: Any) -> str:
    """Recursively extract plain text from an Atlassian Document Format node."""
    if not isinstance(node, dict):
        return ""
    t = node.get("type", "")
    if t == "text":
        return node.get("text", "")
    if t == "hardBreak":
        return "\n"
    if t == "rule":
        return "\n---\n"
    children = "".join(adf_to_text(c) for c in node.get("content", []))
    if t in ("paragraph", "heading", "listItem", "taskItem"):
        return children + "\n"
    return children


def markdown_to_adf(text: str) -> dict:
    """Convert simple Markdown to Atlassian Document Format for Jira write-back."""
    lines = text.split("\n")
    content: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("## "):
            content.append({
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": stripped[3:]}],
            })
        elif stripped.startswith("### "):
            content.append({
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": stripped[4:]}],
            })
        elif stripped in ("---", "***"):
            content.append({"type": "rule"})
        elif re.match(r"^- \[[ x]\] ", stripped):
            checked = stripped[3] == "x"
            task_text = stripped[6:]
            content.append({
                "type": "taskList",
                "attrs": {"localId": str(i)},
                "content": [{
                    "type": "taskItem",
                    "attrs": {"localId": str(i) + "i", "state": "DONE" if checked else "TODO"},
                    "content": [{"type": "text", "text": task_text}],
                }],
            })
        elif stripped == "":
            pass
        else:
            content.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": stripped}],
            })
        i += 1

    if not content:
        content = [{"type": "paragraph", "content": [{"type": "text", "text": ""}]}]
    return {"version": 1, "type": "doc", "content": content}


class JiraService:
    def _headers(self, access_token: str) -> dict:
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _base(self, cloud_id: str) -> str:
        return _JIRA_BASE.format(cloud_id=cloud_id)

    async def search_tickets(
        self,
        access_token: str,
        cloud_id: str,
        project: str,
        q: str,
    ) -> list[dict]:
        """Search Jira tickets and return simplified list."""
        if not q:
            jql = f"project={project} ORDER BY updated DESC"
        elif "=" in q or any(kw in q for kw in ("AND", "OR", "NOT", "ORDER")):
            jql = f"project={project} AND ({q}) ORDER BY updated DESC"
        else:
            jql = f'project={project} AND text ~ "{q}" ORDER BY updated DESC'

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self._base(cloud_id)}/search",
                headers=self._headers(access_token),
                params={
                    "jql": jql,
                    "fields": "summary,status,priority,assignee",
                    "maxResults": 20,
                },
            )
        resp.raise_for_status()
        issues = resp.json().get("issues", [])
        return [
            {
                "key": issue["key"],
                "summary": issue["fields"]["summary"],
                "status": issue["fields"]["status"]["name"],
                "priority": (issue["fields"].get("priority") or {}).get("name", ""),
                "assignee": ((issue["fields"].get("assignee") or {}).get("displayName", "")),
            }
            for issue in issues
        ]

    async def get_ticket(
        self,
        access_token: str,
        cloud_id: str,
        key: str,
    ) -> dict:
        """Fetch a single Jira ticket with plaintext description."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self._base(cloud_id)}/issue/{key}",
                headers=self._headers(access_token),
                params={"fields": "summary,description,status,priority,assignee,reporter"},
            )
        resp.raise_for_status()
        data = resp.json()
        fields = data["fields"]
        raw_desc = fields.get("description")
        description = adf_to_text(raw_desc).strip() if isinstance(raw_desc, dict) else (raw_desc or "")
        return {
            "key": key,
            "id": data["id"],
            "summary": fields["summary"],
            "description": description,
            "status": fields["status"]["name"],
            "priority": (fields.get("priority") or {}).get("name", ""),
            "assignee": ((fields.get("assignee") or {}).get("displayName", "")),
            "reporter": ((fields.get("reporter") or {}).get("displayName", "")),
        }

    async def write_ticket(
        self,
        access_token: str,
        cloud_id: str,
        key: str,
        summary: str,
        description_md: str,
    ) -> None:
        """Write summary + user story (Markdown → ADF) back to Jira."""
        adf = markdown_to_adf(description_md)
        body: dict = {"fields": {"description": adf}}
        if summary:
            body["fields"]["summary"] = summary

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.put(
                f"{self._base(cloud_id)}/issue/{key}",
                headers=self._headers(access_token),
                content=json.dumps(body),
            )
        if resp.status_code not in (200, 204):
            logger.error("Jira write failed %s: %s", resp.status_code, resp.text)
            resp.raise_for_status()

    async def generate_user_story(
        self,
        key: str,
        summary: str,
        description: str,
    ) -> str:
        """Call Claude to generate a User Story Markdown from a Jira ticket."""
        settings = get_settings()
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        user_content = (
            f"Ticket: {key}\n"
            f"Summary: {summary}\n\n"
            f"Description:\n{description or '(keine Beschreibung)'}"
        )
        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=_USERSTORY_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
        return msg.content[0].text.strip() if msg.content else ""


jira_service = JiraService()
