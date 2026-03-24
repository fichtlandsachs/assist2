import logging
from typing import Any, Dict

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class N8NClient:
    """HTTP client for communicating with the n8n workflow automation service."""

    def __init__(self):
        settings = get_settings()
        self._base_url = settings.N8N_WEBHOOK_URL
        self._api_key = settings.N8N_API_KEY

    @property
    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            headers["X-N8N-API-KEY"] = self._api_key
        return headers

    async def trigger_workflow(
        self,
        workflow_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Trigger a workflow via its webhook endpoint.
        POST /webhook/{workflow_id}
        """
        url = f"{self._base_url}/webhook/{workflow_id}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=data, headers=self._headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"n8n workflow trigger failed: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"n8n connection error: {e}")
            raise

    async def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        Get the status and result of a workflow execution.
        GET /api/v1/executions/{execution_id}
        """
        url = f"{self._base_url}/api/v1/executions/{execution_id}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self._headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"n8n get execution failed: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"n8n connection error: {e}")
            raise

    async def list_workflows(self) -> Dict[str, Any]:
        """
        List all workflows in n8n.
        GET /api/v1/workflows
        """
        url = f"{self._base_url}/api/v1/workflows"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self._headers)
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            logger.error(f"n8n list workflows failed: {e}")
            raise

    async def provision_user(self, email: str, role: str = "global:member") -> bool:
        """
        Ensure a user exists in n8n. Creates the user if not present.
        Returns True if the user is now provisioned, False on error.
        POST /api/v1/users  → [{email, role}]
        """
        if not self._api_key:
            logger.debug("n8n provisioning skipped: N8N_API_KEY not configured")
            return False

        url = f"{self._base_url}/api/v1/users"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json=[{"email": email, "role": role}],
                    headers=self._headers,
                )
                if response.status_code in (200, 201):
                    logger.info(f"n8n: provisioned user {email}")
                    return True
                # 409 means user already exists — treat as success
                if response.status_code == 409:
                    logger.debug(f"n8n: user {email} already exists")
                    return True
                logger.warning(f"n8n provision_user unexpected status {response.status_code}: {response.text[:200]}")
                return False
        except httpx.RequestError as e:
            logger.warning(f"n8n provision_user connection error: {e}")
            return False


n8n_client = N8NClient()
