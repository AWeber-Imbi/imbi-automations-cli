import logging
import typing

import httpx

from imbi_automations import errors, models

from . import http

LOGGER = logging.getLogger(__name__)


class GitHub(http.BaseURLHTTPClient):
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

            # Check if it's specifically a rate limit error
            if 'rate limit exceeded' in error_message.lower():
                raise errors.GitHubRateLimitError(error_message)
            else:
                LOGGER.error(
                    'GitHub API returned 403 Forbidden for repository '
                    '%s/%s: %s',
                    org,
                    repo_name,
                    error_message,
                )
                raise errors.GitHubNotFoundError(
                    f'Access denied for repository {org}/{repo_name}'
                )
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
            response_data = response.json() if response.content else {}
            message = response_data.get('message', response.text)

            # Check if it's specifically a rate limit error
            if 'rate limit exceeded' in message.lower():
                raise errors.GitHubRateLimitError(message)
            else:
                LOGGER.warning(
                    'Access forbidden for repository ID %s (403): %s',
                    repo_id,
                    message,
                )
                raise errors.GitHubNotFoundError(
                    f'Access denied for repository ID {repo_id}'
                )
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
        except (httpx.HTTPError, ValueError, KeyError) as exc:
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

        last_run = await self.get_latest_workflow_run(org, repo_name)
        return last_run.conclusion or last_run.status if last_run else None

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

    async def get_sonarqube_job_status(
        self,
        org: str,
        repo_name: str,
        branch: str | None = None,
        keyword: str = 'sonar',
    ) -> str | None:
        """Get job status with specified keyword from most recent workflow run.

        Args:
            org: Organization name
            repo_name: Repository name
            branch: Branch name (optional, defaults to all branches)
            keyword: Keyword to search for in job names (default: 'sonar')

        Returns:
            Status string: 'failure', 'success', 'skipped', 'in_progress',
            or None if no matching jobs found

        """
        # Get the most recent workflow run
        params = {'per_page': 1}  # Only get the most recent run
        if branch:
            params['branch'] = branch

        response = await self.get(
            f'/repos/{org}/{repo_name}/actions/runs', params=params
        )
        response.raise_for_status()

        data = response.json()
        workflow_runs = data.get('workflow_runs', [])

        if not workflow_runs:
            LOGGER.debug('No workflow runs found for %s/%s', org, repo_name)
            return None

        # Get the most recent workflow run
        latest_run = workflow_runs[0]
        run_id = latest_run['id']

        LOGGER.debug(
            'Checking most recent workflow run %s for %s/%s',
            run_id,
            org,
            repo_name,
        )

        # Get jobs for the most recent workflow run
        jobs_response = await self.get(
            f'/repos/{org}/{repo_name}/actions/runs/{run_id}/jobs'
        )
        jobs_response.raise_for_status()

        jobs_data = jobs_response.json()
        jobs = jobs_data.get('jobs', [])

        # Look for jobs with the specified keyword (case-insensitive search)
        for job in jobs:
            job_name = job.get('name', '').lower()
            if keyword.lower() in job_name:
                # Found a matching job, return its status
                job_status = job.get('status')
                job_conclusion = job.get('conclusion')

                LOGGER.debug(
                    'Found job "%s" with keyword "%s" in %s/%s: '
                    'status=%s, conclusion=%s',
                    job.get('name'),
                    keyword,
                    org,
                    repo_name,
                    job_status,
                    job_conclusion,
                )

                # Return conclusion if completed, otherwise return status
                if job_status == 'completed' and job_conclusion:
                    return job_conclusion
                return job_status

        LOGGER.debug(
            'No jobs with keyword "%s" found in most recent workflow run '
            'for %s/%s',
            keyword,
            org,
            repo_name,
        )
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

    async def analyze_python_versions(
        self,
        org: str,
        repo_name: str,
        imbi_project_id: int,
        imbi_project_facts: dict[str, typing.Any] | None = None,
        imbi_project_name: str | None = None,
    ) -> dict[str, typing.Any]:
        """Analyze Python version consistency across Dockerfile, CI, and Imbi.

        Args:
            org: GitHub organization name
            repo_name: Repository name
            imbi_project_id: Imbi project ID
            imbi_project_facts: Imbi project facts dictionary
            imbi_project_name: Imbi project name for logging

        Returns:
            Analysis results with version information and update requirements
        """
        try:
            # Extract Python version from Dockerfile
            dockerfile_version = await self._extract_dockerfile_python_version(
                org, repo_name
            )

            # Extract Python versions from GitHub Actions workflows
            workflow_versions = await self._extract_workflow_python_versions(
                org, repo_name
            )

            # Extract Python version from Imbi Programming Language fact
            imbi_version = self._extract_imbi_python_version_from_facts(
                imbi_project_facts
            )

            LOGGER.debug(
                'Python version analysis for %s/%s: '
                'Dockerfile=%s, Workflows=%s, Imbi=%s',
                org,
                repo_name,
                dockerfile_version,
                workflow_versions,
                imbi_version,
            )

            # Determine what needs updating (Dockerfile is source of truth)
            requires_workflow_update = False
            requires_imbi_update = False

            if dockerfile_version and workflow_versions:
                # Check if any workflow version differs from Dockerfile
                for _workflow_file, version in workflow_versions.items():
                    if version and version != dockerfile_version:
                        requires_workflow_update = True
                        break

            if dockerfile_version and imbi_version:
                # Extract just the version number from "Python X.Y" format
                imbi_version_num = (
                    imbi_version.replace('Python ', '')
                    if imbi_version
                    else None
                )
                requires_imbi_update = imbi_version_num != dockerfile_version

            return {
                'dockerfile_version': dockerfile_version,
                'workflow_versions': workflow_versions,
                'imbi_version': imbi_version,
                'source_of_truth': dockerfile_version,
                'requires_workflow_update': requires_workflow_update,
                'requires_imbi_update': requires_imbi_update,
                'correct_language_version': (
                    f'Python {dockerfile_version}'
                    if dockerfile_version
                    else None
                ),
                'analysis_successful': True,
            }

        except (httpx.HTTPError, ValueError, KeyError) as exc:
            LOGGER.error(
                'Failed to analyze Python versions for %s/%s: %s',
                org,
                repo_name,
                exc,
            )
            return {
                'dockerfile_version': None,
                'workflow_versions': {},
                'imbi_version': None,
                'source_of_truth': None,
                'requires_workflow_update': False,
                'requires_imbi_update': False,
                'correct_language_version': None,
                'analysis_successful': False,
                'error': str(exc),
            }

    async def _extract_dockerfile_python_version(
        self, org: str, repo_name: str
    ) -> str | None:
        """Extract Python version from Dockerfile FROM line.

        Args:
            org: GitHub organization name
            repo_name: Repository name

        Returns:
            Python version string (e.g., "3.12") or None if not found
        """
        try:
            response = await self.get(
                f'/repos/{org}/{repo_name}/contents/Dockerfile'
            )
            if response.status_code == http.HTTPStatus.NOT_FOUND:
                LOGGER.debug('Dockerfile not found in %s/%s', org, repo_name)
                return None

            response.raise_for_status()
            content_data = response.json()

            # Decode base64 content
            import base64

            content = base64.b64decode(content_data['content']).decode('utf-8')

            # Look for python3-consumer image version in FROM line
            import re

            pattern = r'FROM.*python3-consumer:(\d+\.\d+)'
            match = re.search(pattern, content)

            if match:
                version = match.group(1)
                LOGGER.debug(
                    'Found Python version %s in Dockerfile for %s/%s',
                    version,
                    org,
                    repo_name,
                )
                return version
            else:
                LOGGER.debug(
                    'No python3-consumer version found in %s/%s Dockerfile',
                    org,
                    repo_name,
                )
                return None

        except (httpx.HTTPError, ValueError, KeyError) as exc:
            LOGGER.warning(
                'Failed to extract Dockerfile Python version for %s/%s: %s',
                org,
                repo_name,
                exc,
            )
            return None

    async def _extract_workflow_python_versions(
        self, org: str, repo_name: str
    ) -> dict[str, str]:
        """Extract Python versions from GitHub Actions workflow files.

        Args:
            org: GitHub organization name
            repo_name: Repository name

        Returns:
            Dictionary mapping workflow filename to Python version
        """
        workflow_versions = {}

        try:
            # Get all workflow files
            response = await self.get(
                f'/repos/{org}/{repo_name}/contents/.github/workflows'
            )
            if response.status_code == http.HTTPStatus.NOT_FOUND:
                LOGGER.debug(
                    'No .github/workflows directory found in %s/%s',
                    org,
                    repo_name,
                )
                return {}

            response.raise_for_status()
            workflow_files = response.json()

            # Process each .yml/.yaml file
            for file_info in workflow_files:
                if file_info['name'].endswith(('.yml', '.yaml')):
                    version = await self._extract_workflow_file_python_version(
                        org, repo_name, file_info['name']
                    )
                    if version:
                        workflow_versions[file_info['name']] = version

            return workflow_versions

        except (httpx.HTTPError, ValueError, KeyError) as exc:
            LOGGER.warning(
                'Failed to extract workflow Python versions for %s/%s: %s',
                org,
                repo_name,
                exc,
            )
            return {}

    async def _extract_workflow_file_python_version(
        self, org: str, repo_name: str, filename: str
    ) -> str | None:
        """Extract Python version from a specific workflow file.

        Args:
            org: GitHub organization name
            repo_name: Repository name
            filename: Workflow filename

        Returns:
            Python version string or None if not found
        """
        try:
            response = await self.get(
                f'/repos/{org}/{repo_name}/contents/.github/workflows/{filename}'
            )
            response.raise_for_status()
            content_data = response.json()

            # Decode base64 content
            import base64

            content = base64.b64decode(content_data['content']).decode('utf-8')

            # Look for python3-testing image versions
            import re

            pattern = r'python3-testing:(\d+\.\d+)'
            match = re.search(pattern, content)

            if match:
                version = match.group(1)
                LOGGER.debug(
                    'Found Python version %s in workflow %s for %s/%s',
                    version,
                    filename,
                    org,
                    repo_name,
                )
                return version

            return None

        except (httpx.HTTPError, ValueError, KeyError) as exc:
            LOGGER.debug(
                'Failed to extract Python version from workflow %s: %s',
                filename,
                exc,
            )
            return None

    def _extract_imbi_python_version(
        self, imbi_project: models.ImbiProject
    ) -> str | None:
        """Extract Python version from Imbi Programming Language fact.

        Args:
            imbi_project: Imbi project with facts

        Returns:
            Programming Language fact value or None if not found
        """
        return self._extract_imbi_python_version_from_facts(imbi_project.facts)

    def _extract_imbi_python_version_from_facts(
        self, facts: dict[str, typing.Any] | str | None
    ) -> str | None:
        """Extract Python version from Imbi facts dictionary.

        Args:
            facts: Imbi project facts dictionary or string representation

        Returns:
            Programming Language fact value or None if not found
        """
        if not facts:
            return None

        # Handle string representation from template rendering
        if isinstance(facts, str):
            try:
                import ast
                import html

                # Decode HTML entities that Jinja2 might have added
                decoded_facts = html.unescape(facts)
                facts = ast.literal_eval(decoded_facts)
            except (ValueError, SyntaxError):
                LOGGER.warning('Failed to parse facts string: %s', facts[:100])
                return None

        if not isinstance(facts, dict):
            return None

        # Look for Programming Language fact (check multiple possible keys)
        programming_language = facts.get('Programming Language') or facts.get(
            'programming_language'
        )
        if programming_language:
            LOGGER.debug(
                'Found Programming Language fact: %s', programming_language
            )
            return str(programming_language)

        return None

    async def analyze_container_image_versions(
        self,
        org: str,
        repo_name: str,
        image_family: str,
        image_types: list[str],
        major_minor_version: str,
        target_version: str,
        ci_workflow_file: str,
    ) -> dict[str, typing.Any]:
        """Analyze container image versions for updates (generic).

        Args:
            org: GitHub organization name
            repo_name: Repository name
            image_family: Image family name (e.g., "python3", "node", "golang")
            image_types: List of image type suffixes (e.g., ["service"])
            major_minor_version: Major.minor version (e.g., "3.9", "18.20")
            target_version: Full target version (e.g., "3.9.18-4", "18.20.4")
            ci_workflow_file: CI workflow file path

        Returns:
            Analysis results with version information and update requirements
        """
        try:
            import semver

            # Extract current version from Dockerfile using dynamic pattern
            dockerfile_version = await self._extract_container_image_version(
                org, repo_name, image_family, image_types, major_minor_version
            )

            # Check if CI workflow exists
            has_ci_workflow = await self._check_workflow_file_exists(
                org, repo_name, ci_workflow_file
            )

            LOGGER.debug(
                'Container image analysis for %s/%s: '
                'Family=%s, Dockerfile=%s, CI=%s, Target=%s',
                org,
                repo_name,
                image_family,
                dockerfile_version,
                has_ci_workflow,
                target_version,
            )

            requires_dockerfile_update = False
            if dockerfile_version:
                try:
                    from imbi_automations import utils

                    requires_dockerfile_update = (
                        utils.Utils.compare_versions_with_build_numbers(
                            dockerfile_version, target_version
                        )
                    )

                    if requires_dockerfile_update:
                        LOGGER.debug(
                            'Version %s older than target %s, update needed',
                            dockerfile_version,
                            target_version,
                        )
                    else:
                        LOGGER.debug(
                            'Version %s is current or newer than target %s',
                            dockerfile_version,
                            target_version,
                        )
                except (ValueError, semver.VersionError) as exc:
                    LOGGER.warning(
                        'Failed to parse version %s: %s',
                        dockerfile_version,
                        exc,
                    )

            return {
                'image_family': image_family,
                'current_dockerfile_version': dockerfile_version,
                'target_version': target_version,
                'major_minor_version': major_minor_version,
                'ci_workflow_file': ci_workflow_file,
                'has_ci_workflow': has_ci_workflow,
                'requires_dockerfile_update': requires_dockerfile_update,
                'analysis_successful': True,
            }

        except (httpx.HTTPError, ValueError, KeyError) as exc:
            LOGGER.error(
                'Failed to analyze container image versions for %s/%s: %s',
                org,
                repo_name,
                exc,
            )
            return {
                'image_family': image_family,
                'current_dockerfile_version': None,
                'target_version': target_version,
                'major_minor_version': major_minor_version,
                'ci_workflow_file': ci_workflow_file,
                'has_ci_workflow': False,
                'requires_dockerfile_update': False,
                'analysis_successful': False,
                'error': str(exc),
            }

    async def _extract_container_image_version(
        self,
        org: str,
        repo_name: str,
        image_family: str,
        image_types: list[str],
        major_minor_version: str,
    ) -> str | None:
        """Extract container image version from Dockerfile FROM line.

        Args:
            org: GitHub organization name
            repo_name: Repository name
            image_family: Image family (e.g., "python3", "node")
            image_types: Image type suffixes (e.g., ["service", "consumer"])
            major_minor_version: Version prefix (e.g., "3.9", "18.20")

        Returns:
            Version string (e.g., "3.9.16-14") or None if not found
        """
        try:
            response = await self.get(
                f'/repos/{org}/{repo_name}/contents/Dockerfile'
            )
            if response.status_code == http.HTTPStatus.NOT_FOUND:
                LOGGER.debug('Dockerfile not found in %s/%s', org, repo_name)
                return None

            response.raise_for_status()
            content_data = response.json()

            # Decode base64 content
            import base64

            content = base64.b64decode(content_data['content']).decode('utf-8')

            # Build dynamic regex pattern
            import re

            types_pattern = '|'.join(image_types)
            escaped_version = re.escape(major_minor_version)
            version_pattern = f'{escaped_version}\\.\\d+(?:-\\d+)?'
            regex_pattern = (
                f'FROM.*{image_family}-({types_pattern}):({version_pattern})'
            )

            match = re.search(regex_pattern, content)

            if match:
                version = match.group(2)
                image_type = match.group(1)
                LOGGER.debug(
                    'Found %s-%s version %s in Dockerfile for %s/%s',
                    image_family,
                    image_type,
                    version,
                    org,
                    repo_name,
                )
                return version
            else:
                LOGGER.debug(
                    'No %s %s image found in Dockerfile for %s/%s',
                    image_family,
                    major_minor_version,
                    org,
                    repo_name,
                )
                return None

        except (httpx.HTTPError, ValueError, KeyError) as exc:
            LOGGER.warning(
                'Failed to extract %s version for %s/%s: %s',
                image_family,
                org,
                repo_name,
                exc,
            )
            return None

    async def _check_workflow_file_exists(
        self, org: str, repo_name: str, workflow_file: str
    ) -> bool:
        """Check if workflow file exists (supports patterns and exact paths).

        Args:
            org: GitHub organization name
            repo_name: Repository name
            workflow_file: Workflow file path or pattern
                (e.g., "ci.yml" or "python-.*-ci.yml")

        Returns:
            True if workflow file exists, False otherwise
        """
        try:
            # Check if this looks like a regex pattern
            if any(
                char in workflow_file
                for char in ['*', '+', '?', '[', ']', '(', ')', '|', '^', '$']
            ):
                return await self._check_workflow_pattern_exists(
                    org, repo_name, workflow_file
                )
            else:
                # Exact file path check
                response = await self.get(
                    f'/repos/{org}/{repo_name}/contents/{workflow_file}'
                )
                return response.status_code == 200
        except (httpx.HTTPError, ValueError, KeyError):
            return False

    async def _check_workflow_pattern_exists(
        self, org: str, repo_name: str, pattern: str
    ) -> bool:
        """Check if any workflow files match the given pattern.

        Args:
            org: GitHub organization name
            repo_name: Repository name
            pattern: Regex pattern to match against workflow files

        Returns:
            True if any files match the pattern, False otherwise
        """
        try:
            import re

            # Get all files in .github/workflows directory
            response = await self.get(
                f'/repos/{org}/{repo_name}/contents/.github/workflows'
            )
            if response.status_code == http.HTTPStatus.NOT_FOUND:
                LOGGER.debug(
                    'No .github/workflows directory found in %s/%s',
                    org,
                    repo_name,
                )
                return False

            response.raise_for_status()
            workflow_files = response.json()

            # Compile the pattern
            try:
                regex = re.compile(pattern)
            except re.error as exc:
                LOGGER.warning('Invalid regex pattern "%s": %s', pattern, exc)
                return False

            # Check each file against the pattern
            for file_info in workflow_files:
                if file_info.get('type') == 'file':
                    file_path = f'.github/workflows/{file_info["name"]}'
                    if regex.match(file_path):
                        LOGGER.debug(
                            'Found matching workflow file: %s (pattern: %s)',
                            file_path,
                            pattern,
                        )
                        return True

            LOGGER.debug(
                'No workflow files match pattern "%s" in %s/%s',
                pattern,
                org,
                repo_name,
            )
            return False

        except (httpx.HTTPError, ValueError, KeyError) as exc:
            LOGGER.debug(
                'Failed to check workflow pattern "%s" for %s/%s: %s',
                pattern,
                org,
                repo_name,
                exc,
            )
            return False

    async def get_repository_environments(
        self, org: str, repo: str
    ) -> list[models.GitHubEnvironment]:
        """Get all environments for a repository.

        Args:
            org: Organization name
            repo: Repository name

        Returns:
            List of GitHubEnvironment objects

        Raises:
            httpx.HTTPError: If API request fails

        """
        try:
            response = await self.get(f'/repos/{org}/{repo}/environments')
            response.raise_for_status()

            data = response.json()
            environments = []

            if 'environments' in data:
                for env_data in data['environments']:
                    environments.append(
                        models.GitHubEnvironment.model_validate(env_data)
                    )

            LOGGER.debug(
                'Found %d environments for repository %s/%s: %s',
                len(environments),
                org,
                repo,
                [env.name for env in environments],
            )

            return environments

        except httpx.HTTPError as exc:
            if exc.response.status_code == http.HTTPStatus.NOT_FOUND:
                LOGGER.debug('Repository %s/%s not found (404)', org, repo)
                raise errors.GitHubNotFoundError(
                    f'Repository {org}/{repo} not found'
                ) from exc
            else:
                LOGGER.error(
                    'Failed to get environments for %s/%s: %s', org, repo, exc
                )
                raise

    async def create_environment(
        self, org: str, repo: str, environment_name: str
    ) -> models.GitHubEnvironment:
        """Create a new environment for a repository.

        Args:
            org: Organization name
            repo: Repository name
            environment_name: Name of the environment to create

        Returns:
            Created GitHubEnvironment object

        Raises:
            httpx.HTTPError: If API request fails

        """
        try:
            response = await self.put(
                f'/repos/{org}/{repo}/environments/{environment_name}'
            )
            response.raise_for_status()

            env_data = response.json()
            environment = models.GitHubEnvironment.model_validate(env_data)

            LOGGER.info(
                'Created environment "%s" for repository %s/%s',
                environment_name,
                org,
                repo,
            )

            return environment

        except httpx.HTTPError as exc:
            LOGGER.error(
                'Failed to create environment "%s" for %s/%s: %s',
                environment_name,
                org,
                repo,
                exc,
            )
            raise

    async def delete_environment(
        self, org: str, repo: str, environment_name: str
    ) -> bool:
        """Delete an environment from a repository.

        Args:
            org: Organization name
            repo: Repository name
            environment_name: Name of the environment to delete

        Returns:
            True if environment was deleted successfully

        Raises:
            httpx.HTTPError: If API request fails

        """
        try:
            response = await self.delete(
                f'/repos/{org}/{repo}/environments/{environment_name}'
            )
            response.raise_for_status()

            LOGGER.info(
                'Deleted environment "%s" from repository %s/%s',
                environment_name,
                org,
                repo,
            )

            return True

        except httpx.HTTPError as exc:
            if exc.response.status_code == http.HTTPStatus.NOT_FOUND:
                LOGGER.warning(
                    'Environment "%s" not found in %s/%s (already deleted?)',
                    environment_name,
                    org,
                    repo,
                )
                return True  # Consider it successful if already gone
            else:
                LOGGER.error(
                    'Failed to delete environment "%s" from %s/%s: %s',
                    environment_name,
                    org,
                    repo,
                    exc,
                )
                raise

    async def sync_project_environments(
        self, org: str, repo: str, imbi_environments: list[str]
    ) -> dict[str, typing.Any]:
        """Synchronize environments between Imbi project and GitHub repository.

        This function ensures that the GitHub repository environments match the
        environments defined in the Imbi project. It will:
        1. Remove GitHub environments that don't exist in Imbi
        2. Create GitHub environments that exist in Imbi but not in GitHub

        Args:
            org: GitHub organization name
            repo: GitHub repository name
            imbi_environments: List of environment names from Imbi project

        Returns:
            Dictionary with sync results including:
            - success: bool - Whether sync completed successfully
            - created: list[str] - Environments created in GitHub
            - deleted: list[str] - Environments deleted from GitHub
            - errors: list[str] - Any errors encountered
            - total_operations: int - Total number of operations performed

        """
        # Import here to avoid circular imports
        from imbi_automations import environment_sync

        return await environment_sync.sync_project_environments(
            org, repo, imbi_environments, self
        )

    async def create_pull_request(
        self,
        context: 'models.WorkflowContext',
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = 'main',
    ) -> str:
        """Create a pull request and return the PR URL.

        Args:
            context: Workflow context containing GitHub repository info
            title: Pull request title
            body: Pull request description
            head_branch: Source branch name
            base_branch: Target branch name (default: 'main')

        Returns:
            Pull request URL

        Raises:
            httpx.HTTPError: If pull request creation fails

        """
        if not context.github_repository:
            raise ValueError('No GitHub repository in workflow context')

        org = context.github_repository.owner.login
        repo = context.github_repository.name

        LOGGER.debug(
            'Creating pull request for %s/%s: %s -> %s',
            org,
            repo,
            head_branch,
            base_branch,
        )

        payload = {
            'title': title,
            'body': body,
            'head': head_branch,
            'base': base_branch,
        }

        response = await self.post(f'/repos/{org}/{repo}/pulls', json=payload)
        response.raise_for_status()

        pr_data = response.json()
        pr_url = pr_data['html_url']

        LOGGER.info(
            'Created pull request #%d for %s/%s: %s',
            pr_data['number'],
            org,
            repo,
            pr_url,
        )

        return pr_url
