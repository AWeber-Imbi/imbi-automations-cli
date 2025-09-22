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
            LOGGER.debug('Repository not found: %s/%s (404)', org, repo_name)
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
        elif not response.is_success:
            LOGGER.error(
                'GitHub API error for repository %s/%s (%s): %s',
                org,
                repo_name,
                response.status_code,
                response.text,
            )

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
            LOGGER.debug('Repository not found for ID %s (404)', repo_id)
            return None
        elif response.status_code == http.HTTPStatus.FORBIDDEN:
            LOGGER.warning(
                'Access forbidden for repository ID %s (403): %s',
                repo_id,
                response.text,
            )
            return None
        elif not response.is_success:
            LOGGER.error(
                'GitHub API error for repository ID %s (%s): %s',
                repo_id,
                response.status_code,
                response.text,
            )
            response.raise_for_status()

        try:
            return models.GitHubRepository(**response.json())
        except Exception as exc:
            LOGGER.error(
                'Failed to parse repository data for ID %s: %s', repo_id, exc
            )
            raise

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

    async def get_repository_identifier(
        self, org: str, repo_name: str, branch: str | None = None
    ) -> int | None:
        """Get repository ID by organization and repository name.

        Args:
            org: Organization name
            repo_name: Repository name
            branch: Branch name (ignored, for workflow compatibility)

        Returns:
            Repository ID or None if not found

        """
        repository = await self.get_repository(org, repo_name)
        return repository.id if repository else None

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

    async def get_repository_team_permissions(
        self, org: str, repo_name: str
    ) -> dict[str, str]:
        """Get team permissions for a repository.

        Args:
            org: Organization name
            repo_name: Repository name

        Returns:
            Dictionary mapping team slug to permission level

        Raises:
            httpx.HTTPError: If API request fails

        """
        response = await self.get(f'/repos/{org}/{repo_name}/teams')
        response.raise_for_status()

        response_data = response.json()
        LOGGER.debug(
            'GitHub API response for %s/%s teams: %d items',
            org,
            repo_name,
            len(response_data),
        )

        team_permissions = {}
        for team_data in response_data:
            team = models.GitHubTeam.model_validate(team_data)
            team_permissions[team.slug] = team.permission
            LOGGER.debug(
                'Team %s has permission %s', team.slug, team.permission
            )

        LOGGER.info(
            'Found %d teams for repository %s/%s: %s',
            len(team_permissions),
            org,
            repo_name,
            team_permissions,
        )

        return team_permissions

    async def get_organization_teams(
        self, org: str
    ) -> list[models.GitHubTeam]:
        """Get all teams in an organization.

        Args:
            org: Organization name

        Returns:
            List of GitHubTeam objects

        Raises:
            httpx.HTTPError: If API request fails

        """
        response = await self.get(f'/orgs/{org}/teams')
        response.raise_for_status()

        teams = []
        for team_data in response.json():
            teams.append(models.GitHubTeam.model_validate(team_data))

        LOGGER.debug(
            'Found %d teams in organization %s: %s',
            len(teams),
            org,
            [team.slug for team in teams],
        )

        return teams

    async def sync_repository_team_access(
        self,
        org: str,
        repo_name: str,
        current_teams: dict[str, str],
        desired_mappings: dict[str, str],
    ) -> str:
        """Synchronize team access permissions for a repository.

        Args:
            org: Organization name
            repo_name: Repository name
            current_teams: Current team permissions (team_slug -> permission)
            desired_mappings: Desired team permissions
                (team_slug -> permission)

        Returns:
            Status string: 'success', 'partial', or 'failed'

        """
        success_count = 0
        total_operations = 0
        errors = []

        # Add or update teams that should have access
        for team_slug, desired_permission in desired_mappings.items():
            current_permission = current_teams.get(team_slug)

            if current_permission != desired_permission:
                total_operations += 1
                try:
                    await self._assign_team_to_repository(
                        org, team_slug, repo_name, desired_permission
                    )
                    success_count += 1
                    LOGGER.info(
                        'Updated team %s permission to %s for %s/%s',
                        team_slug,
                        desired_permission,
                        org,
                        repo_name,
                    )
                except httpx.HTTPError as exc:
                    error_msg = f'Failed to assign team {team_slug}: {exc}'
                    errors.append(error_msg)
                    LOGGER.error(error_msg)

        # Remove teams that should not have access
        teams_to_remove = set(current_teams.keys()) - set(
            desired_mappings.keys()
        )
        for team_slug in teams_to_remove:
            total_operations += 1
            try:
                await self._remove_team_from_repository(
                    org, team_slug, repo_name
                )
                success_count += 1
                LOGGER.info(
                    'Removed team %s access from %s/%s',
                    team_slug,
                    org,
                    repo_name,
                )
            except httpx.HTTPError as exc:
                error_msg = f'Failed to remove team {team_slug}: {exc}'
                errors.append(error_msg)
                LOGGER.error(error_msg)

        # Determine overall status
        if total_operations == 0:
            LOGGER.debug(
                'No team permission changes needed for %s/%s', org, repo_name
            )
            return 'success'
        elif success_count == total_operations:
            LOGGER.info(
                'Successfully updated all team permissions for %s/%s '
                '(%d operations)',
                org,
                repo_name,
                total_operations,
            )
            return 'success'
        elif success_count > 0:
            LOGGER.warning(
                'Partial success updating team permissions for %s/%s '
                '(%d/%d operations): %s',
                org,
                repo_name,
                success_count,
                total_operations,
                '; '.join(errors),
            )
            return 'partial'
        else:
            LOGGER.error(
                'Failed to update team permissions for %s/%s: %s',
                org,
                repo_name,
                '; '.join(errors),
            )
            return 'failed'

    async def _assign_team_to_repository(
        self, org: str, team_slug: str, repo_name: str, permission: str
    ) -> None:
        """Assign a team to a repository with specific permission.

        Args:
            org: Organization name
            team_slug: Team slug
            repo_name: Repository name
            permission: Permission level (pull, triage, push, maintain, admin)

        Raises:
            httpx.HTTPError: If API request fails

        """
        response = await self.put(
            f'/orgs/{org}/teams/{team_slug}/repos/{org}/{repo_name}',
            json={'permission': permission},
        )

        if response.status_code == 422:
            # Enhanced error handling for 422 responses
            try:
                error_data = response.json()
                if 'message' in error_data:
                    raise RuntimeError(
                        f'Team assignment failed for {team_slug}: '
                        f'{error_data["message"]}'
                    )
            except (httpx.RequestError, KeyError):
                # Ignore JSON parsing errors and continue with generic error
                pass
            raise RuntimeError(
                f'Team {team_slug} may not exist in organization {org} '
                f'or insufficient permissions'
            )

        response.raise_for_status()

    async def _remove_team_from_repository(
        self, org: str, team_slug: str, repo_name: str
    ) -> None:
        """Remove a team's access from a repository.

        Args:
            org: Organization name
            team_slug: Team slug
            repo_name: Repository name

        Raises:
            httpx.HTTPError: If API request fails

        """
        response = await self.delete(
            f'/orgs/{org}/teams/{team_slug}/repos/{org}/{repo_name}'
        )
        response.raise_for_status()
