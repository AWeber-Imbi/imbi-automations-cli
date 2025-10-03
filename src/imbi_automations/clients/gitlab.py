"""GitLab API client for project operations and repository management.

Provides GitLab API integration for project retrieval and repository
operations, supporting self-hosted GitLab instances with configurable
hostnames.
"""

import logging

import httpx
import yarl

from imbi_automations import models

from . import http

LOGGER = logging.getLogger(__name__)


class GitLab(http.BaseURLHTTPClient):
    """GitLab API client for project operations.

    Provides GitLab API integration for project retrieval, supporting both
    self-hosted GitLab instances and GitLab.com with private token
    authentication.
    """

    def __init__(
        self,
        config: models.Configuration,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(transport)
        self._base_url = f'https://{config.gitlab.hostname}'
        self.add_header(
            'PRIVATE-TOKEN', config.gitlab.api_key.get_secret_value()
        )

    async def get_project(
        self, project: models.ImbiProject
    ) -> models.GitLabProject | None:
        """Get a repository by name/slug in a specific organization."""
        project_id = project.identifiers.get(
            self.configuration.imbi.gitlab_identifier
        )
        if project_id:
            return await self.get_project_by_id(project_id)
        project_link = project.links.get(self.configuration.imbi.gitlab_link)
        if project_link:
            return await self.get_project_by_url(project_link)
        return None

    async def _get_project_by_id(
        self, project_id: int
    ) -> models.GitLabProject | None:
        """Get a GitLab project by ID"""
        response = await self.get(f'/api/v4/projects/{project_id}')
        if response.status_code == http.HTTPStatus.NOT_FOUND:
            return None
        response.raise_for_status()
        return models.GitLabProject.model_validate(response.json())

    async def _get_project_by_url(
        self, project_url: str
    ) -> models.GitLabProject | None:
        """Get a GitLab project by URL"""
        url = yarl.URL(project_url)
        response = await self.get(
            f'/api/v4/projects/{url.raw_path}', follow_redirects=True
        )
        if response.status_code == http.HTTPStatus.NOT_FOUND:
            return None
        response.raise_for_status()
        return models.GitLabProject.model_validate(response.json())
