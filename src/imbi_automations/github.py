import logging

import httpx

from imbi_automations import http, models

LOGGER = logging.getLogger(__name__)


class GitHub(http.BaseURLClient):
    def __init__(
        self,
        config: models.GitHubConfiguration,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(transport)
        self._base_url = f'https://{config.hostname}'
        self.add_header(
            'Authorization', f'Bearer {config.api_key.get_secret_value()}'
        )
        self.add_header('X-GitHub-Api-Version', '2022-11-28')
        self.add_header('Accept', 'application/vnd.github+json')

    async def get_organizations(self) -> list[models.GitHubOrganization]:
        response = await self.get('/user/orgs')
        response.raise_for_status()
        return [
            models.GitHubOrganization.model_validate(org)
            for org in response.json()
        ]

    async def get_organization(
        self, org_name: str
    ) -> models.GitHubOrganization | None:
        """Get a specific organization by name."""
        try:
            response = await self.get(f'/orgs/{org_name}')
            response.raise_for_status()
            return models.GitHubOrganization.model_validate(response.json())
        except httpx.HTTPError:
            return None

    async def get_repository(
        self, org: str, repo_name: str
    ) -> models.GitHubRepository | None:
        """Get a repository by name/slug in a specific organization."""
        response = await self.get(f'/repos/{org}/{repo_name}')
        if response.status_code == http.HTTPStatus.NOT_FOUND:
            return None
        if response.status_code == 403:
            error_data = response.json() if response.content else {}
            error_message = error_data.get('message', 'Access forbidden')
            LOGGER.error(
                'GitHub API returned 403 Forbidden when getting repository '
                '%s/%s: %s',
                org,
                repo_name,
                error_message,
            )
            raise RuntimeError(f'GitHub API access denied: {error_message}')
        response.raise_for_status()
        return models.GitHubRepository(**response.json())

    async def get_repository_by_id(
        self, repo_id: int
    ) -> models.GitHubRepository | None:
        """Get a repository by its GitHub repository ID.

        Args:
            repo_id: GitHub repository ID

        Returns:
            GitHubRepository object or None if not found

        Raises:
            httpx.HTTPError: If API request fails (except 404)

        """
        response = await self.get(f'/repositories/{repo_id}')
        if response.status_code == http.HTTPStatus.NOT_FOUND:
            return None
        response.raise_for_status()
        return models.GitHubRepository(**response.json())

    async def get_repository_custom_properties(
        self, org: str, repo_name: str
    ) -> dict[str, str | list[str]]:
        """Get all custom property values for a repository.

        Args:
            org: Organization name
            repo_name: Repository name

        Returns:
            Dictionary of custom property names to values

        Raises:
            httpx.HTTPError: If API request fails

        """
        response = await self.get(
            f'/repos/{org}/{repo_name}/properties/values'
        )
        response.raise_for_status()
        properties = {}
        for prop in response.json():
            properties[prop['property_name']] = prop['value']
        return properties

    async def update_repository_custom_properties(
        self, org: str, repo_name: str, properties: dict[str, str | list[str]]
    ) -> None:
        """Create or update custom property values for a repository.

        Args:
            org: Organization name
            repo_name: Repository name
            properties: Dictionary of custom property names to values

        Raises:
            httpx.HTTPError: If API request fails

        """
        payload = {
            'properties': [
                {'property_name': name, 'value': value}
                for name, value in properties.items()
            ]
        }
        response = await self.patch(
            f'/repos/{org}/{repo_name}/properties/values', json=payload
        )
        response.raise_for_status()

    async def get_latest_workflow_run(
        self, org: str, repo_name: str
    ) -> models.GitHubWorkflowRun | None:
        """Get the most recent workflow run for a repository.

        Args:
            org: Organization name
            repo_name: Repository name

        Returns:
            Most recent GitHubWorkflowRun or None if no runs found

        Raises:
            httpx.HTTPError: If API request fails

        """
        response = await self.get(
            f'/repos/{org}/{repo_name}/actions/runs',
            params={'per_page': 1},  # Get only the most recent run
        )
        response.raise_for_status()

        data = response.json()
        if data.get('workflow_runs') and len(data['workflow_runs']) > 0:
            return models.GitHubWorkflowRun.model_validate(
                data['workflow_runs'][0]
            )
        return None

    async def get_repository_workflow_status(
        self, repository: models.GitHubRepository
    ) -> str | None:
        """Get the status of the most recent GitHub Actions workflow run.

        Args:
            repository: GitHub repository to check workflow status for

        Returns:
            Status string or None if no runs

        """
        # Extract org and repo name from repository
        org, repo_name = repository.full_name.split('/', 1)

        latest_run = await self.get_latest_workflow_run(org, repo_name)
        return latest_run.status if latest_run else None

    async def get_latest_workflow_status(
        self, org: str, repo_name: str, branch: str | None = None
    ) -> str | None:
        """Get the status/conclusion of the most recent workflow run.

        Args:
            org: Organization name
            repo_name: Repository name
            branch: Branch name (optional, defaults to all branches)

        Returns:
            Status or conclusion string, or None if no runs found

        """
        params = {'per_page': 1}
        if branch:
            params['branch'] = branch

        response = await self.get(
            f'/repos/{org}/{repo_name}/actions/runs', params=params
        )
        response.raise_for_status()

        data = response.json()
        if data.get('workflow_runs') and len(data['workflow_runs']) > 0:
            run = data['workflow_runs'][0]
            # Return conclusion if completed, otherwise return status
            if run.get('status') == 'completed' and run.get('conclusion'):
                return run['conclusion']
            return run.get('status')
        return None
