import logging
import urllib.parse

import httpx

from imbi_automations import models

from . import http

LOGGER = logging.getLogger(__name__)


class GitLab(http.BaseURLHTTPClient):
    def __init__(
        self,
        config: models.GitLabConfiguration,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(transport)
        self._base_url = f'https://{config.hostname}'
        self.add_header('PRIVATE-TOKEN', config.api_key.get_secret_value())

    async def get_project(
        self, project_id: int
    ) -> models.GitLabProject | None:
        """Get a GitLab project by ID."""
        response = await self.get(f'/api/v4/projects/{project_id}')
        if response.status_code == http.HTTPStatus.NOT_FOUND:
            return None
        response.raise_for_status()
        return models.GitLabProject.model_validate(response.json())

    async def get_project_by_path(
        self, project_path: str
    ) -> models.GitLabProject | None:
        """Get a GitLab project by path (e.g., 'PSE/bots/aj-slack-bot')."""
        encoded_path = urllib.parse.quote(project_path, safe='')
        response = await self.get(
            f'/api/v4/projects/{encoded_path}', follow_redirects=True
        )
        if response.status_code == http.HTTPStatus.NOT_FOUND:
            return None
        response.raise_for_status()
        return models.GitLabProject.model_validate(response.json())
