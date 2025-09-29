import logging

import httpx

from imbi_automations import errors, models

from . import http

LOGGER = logging.getLogger(__name__)


class GitHub(http.BaseURLHTTPClient):
    def __init__(
        self,
        config: models.Configuration,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(transport)
        self._base_url = f'https://{config.github.hostname}'
        self.add_header(
            'Authorization',
            f'Bearer {config.github.api_key.get_secret_value()}',
        )
        self.add_header('X-GitHub-Api-Version', '2022-11-28')
        self.add_header('Accept', 'application/vnd.github+json')
        self.configuration = config

    async def get_repository(
        self, project: models.ImbiProject
    ) -> models.GitHubRepository | None:
        """Get a repository by name/slug in a specific organization."""
        project_id = project.identifiers.get(
            self.configuration.imbi.github_identifier
        )
        if project_id:
            return await self._get_repository_by_id(project_id)
        project_link = project.links.get(self.configuration.imbi.github_link)
        if project_link:
            return await self.get_repository_by_url(project_link)
        return None

    async def _get_repository_by_id(
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

    async def get_file_contents(
        self, context: 'models.WorkflowContext', file_path: str
    ) -> str | None:
        """Get file contents from GitHub repository.

        Args:
            context: Workflow context containing GitHub repository info
            file_path: Path to the file in the repository

        Returns:
            File contents as string, or None if file doesn't exist

        Raises:
            ValueError: If no GitHub repository in context
            httpx.HTTPError: If API request fails (other than 404)

        """
        if not context.github_repository:
            raise ValueError('No GitHub repository in workflow context')

        org = context.github_repository.owner.login
        repo = context.github_repository.name

        LOGGER.debug(
            'Getting file contents for %s from %s/%s', file_path, org, repo
        )

        try:
            response = await self.get(
                f'/repos/{org}/{repo}/contents/{file_path}'
            )
            response.raise_for_status()

            file_data = response.json()

            # Handle file vs directory response
            if isinstance(file_data, list):
                # Path points to directory, not file
                LOGGER.debug(
                    'Path %s is a directory in %s/%s, not a file',
                    file_path,
                    org,
                    repo,
                )
                return None

            # Check if it's a file
            if file_data.get('type') != 'file':
                LOGGER.debug(
                    'Path %s is not a file in %s/%s (type: %s)',
                    file_path,
                    org,
                    repo,
                    file_data.get('type'),
                )
                return None

            # Decode file content
            import base64

            content = file_data.get('content', '')
            if content:
                try:
                    decoded_content = base64.b64decode(content).decode('utf-8')
                    LOGGER.debug(
                        'Retrieved %d bytes from %s in %s/%s',
                        len(decoded_content),
                        file_path,
                        org,
                        repo,
                    )
                    return decoded_content
                except (ValueError, UnicodeDecodeError) as exc:
                    LOGGER.warning(
                        'Failed to decode file %s from %s/%s: %s',
                        file_path,
                        org,
                        repo,
                        exc,
                    )
                    return None

            return ''  # Empty file

        except httpx.HTTPError as exc:
            if exc.response.status_code == 404:
                LOGGER.debug(
                    'File %s not found in %s/%s', file_path, org, repo
                )
                return None
            else:
                LOGGER.error(
                    'Failed to get file %s from %s/%s: %s',
                    file_path,
                    org,
                    repo,
                    exc,
                )
                raise
