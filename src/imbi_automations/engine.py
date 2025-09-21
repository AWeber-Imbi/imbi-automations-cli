import argparse
import asyncio
import enum
import logging
import re

from imbi_automations import github, gitlab, imbi, models

LOGGER = logging.getLogger(__name__)


class AutomationIterator(enum.Enum):
    github_repositories = 1
    github_organization = 2
    github_project = 3
    gitlab_repositories = 4
    gitlab_group = 5
    gitlab_project = 6
    imbi_project_types = 7
    imbi_project = 8
    imbi_projects = 9


class AutomationEngine:
    def __init__(
        self,
        args: argparse.Namespace,
        configuration: models.Configuration,
        iterator: AutomationIterator,
        workflow: models.Workflow,
    ) -> None:
        self.args = args
        self.configuration = configuration
        self.iterator = iterator
        self.workflow = workflow

        self.github: github.GitHub | None = (
            github.GitHub(configuration.github)
            if configuration.github
            else None
        )
        self.gitlab: gitlab.GitLab | None = (
            gitlab.GitLab(configuration.gitlab)
            if configuration.gitlab
            else None
        )
        self.imbi: imbi.Imbi | None = (
            imbi.Imbi(configuration.imbi) if configuration.imbi else None
        )
        self.workflow_engine = WorkflowEngine()

    async def run(self) -> None:
        match self.iterator:
            case AutomationIterator.github_repositories:
                await self._process_github_repositories()
            case AutomationIterator.github_organization:
                await self._process_github_organization()
            case AutomationIterator.github_project:
                await self._process_github_project()
            case AutomationIterator.gitlab_repositories:
                await self._process_gitlab_repositories()
            case AutomationIterator.gitlab_group:
                await self._process_gitlab_group()
            case AutomationIterator.gitlab_project:
                await self._process_gitlab_project()
            case AutomationIterator.imbi_project_types:
                await self._process_imbi_project_types()
            case AutomationIterator.imbi_project:
                await self._process_imbi_project()
            case AutomationIterator.imbi_projects:
                await self._process_imbi_projects()

    async def _process_github_repositories(self) -> None: ...

    async def _process_github_organization(self) -> None: ...

    async def _process_github_project(self) -> None: ...

    async def _process_gitlab_repositories(self) -> None: ...

    async def _process_gitlab_group(self) -> None: ...

    async def _process_gitlab_project(self) -> None: ...

    async def _process_imbi_project_types(self) -> None:
        """Iterate over all Imbi projects for a specific project type."""
        ...

    async def _process_imbi_project(self) -> None:
        """Process a single Imbi project."""
        project = await self.imbi.get_project(self.args.imbi_project_id)
        await self._execute_workflow_run(imbi_project=project)

    async def _process_imbi_projects(self) -> None:
        """Iterate over all Imbi projects and execute workflow runs."""
        projects = await self.imbi.get_all_projects()
        LOGGER.info('Processing %d Imbi projects', len(projects))

        for project in projects:
            LOGGER.debug(
                'Processing project: %s (%s)', project.name, project.slug
            )
            try:
                await self._execute_workflow_run(imbi_project=project)
            except Exception as exc:  # noqa: BLE001
                LOGGER.error(
                    'Failed to process project %s (%d): %s',
                    project.name,
                    project.id,
                    exc,
                )

    async def _get_github_repository(
        self, imbi_project: models.ImbiProject
    ) -> models.GitHubRepository | None:
        """Get GitHub repository for an Imbi project.

        Args:
            imbi_project: Imbi project to find GitHub repository for

        Returns:
            GitHubRepository object or None if not found

        """
        if not self.github:
            return None

        # Try GitHub identifier first
        if imbi_project.identifiers and imbi_project.identifiers.get('github'):
            return await self.github.get_repository_by_id(
                imbi_project.identifiers['github']
            )

        # Fall back to GitHub link URL
        if (
            imbi_project.links
            and self.configuration.imbi.github_link in imbi_project.links
        ):
            github_url = imbi_project.links[
                self.configuration.imbi.github_link
            ]
            # Extract org/repo from GitHub URL
            match = re.match(r'https://[^/]+/([^/]+)/([^/]+)/?$', github_url)
            if match:
                org, repo_name = match.groups()
                return await self.github.get_repository(org, repo_name)

        return None

    async def _get_imbi_project(
        self,
        github_repository: models.GitHubRepository | None = None,
        gitlab_project: models.GitLabProject | None = None,
    ) -> models.ImbiProject | None:
        """Get Imbi project for a GitHub repository or GitLab project.

        Args:
            github_repository: GitHub repository to find Imbi project for
            gitlab_project: GitLab project to find Imbi project for

        Returns:
            ImbiProject object or None if not found

        """
        if not self.imbi:
            return None

        if github_repository:
            # Try custom property first
            if (
                github_repository.custom_properties
                and 'imbi_project_id' in github_repository.custom_properties
            ):
                project_id = github_repository.custom_properties[
                    'imbi_project_id'
                ]
                return await self.imbi.get_project(project_id=project_id)

            # Fall back to URL search
            projects = await self.imbi.search_projects_by_github_url(
                github_repository.html_url
            )
            if projects:
                return projects[0]  # Take first match

        elif gitlab_project:
            # Try GitLab identifier first
            if gitlab_project.id:
                # Search by GitLab project ID - would need a method for this
                # For now, fall back to URL search
                pass

            # Fall back to URL search by GitLab web URL
            if hasattr(gitlab_project, 'web_url') and gitlab_project.web_url:
                # Would need search_projects_by_gitlab_url method
                # For now, return None
                pass

        return None

    async def _get_gitlab_project(
        self, imbi_project: models.ImbiProject
    ) -> models.GitLabProject | None:
        """Get GitLab project for an Imbi project.

        Args:
            imbi_project: Imbi project to find GitLab project for

        Returns:
            GitLabProject object or None if not found

        """
        if not self.gitlab:
            return None

        # Try GitLab identifier first
        if imbi_project.identifiers and imbi_project.identifiers.get('gitlab'):
            return await self.gitlab.get_project(
                imbi_project.identifiers['gitlab']
            )

        # Fall back to GitLab link URL
        if (
            imbi_project.links
            and self.configuration.imbi.gitlab_link in imbi_project.links
        ):
            gitlab_url = imbi_project.links[
                self.configuration.imbi.gitlab_link
            ]
            # Extract project path from GitLab URL
            match = re.match(r'https://[^/]+/(.+?)/?$', gitlab_url)
            if match:
                project_path = match.group(1)
                return await self.gitlab.get_project_by_path(project_path)

        return None

    async def _execute_workflow_run(
        self,
        github_repository: models.GitHubRepository | None = None,
        gitlab_project: models.GitLabProject | None = None,
        imbi_project: models.ImbiProject | None = None,
    ) -> None:
        if self.github and not github_repository and not imbi_project:
            raise RuntimeError(
                'GitHub repository or Imbi project must be provided'
            )
        elif self.github and github_repository and not imbi_project:
            imbi_project = await self._get_imbi_project(
                github_repository=github_repository
            )
        elif self.github and not github_repository and imbi_project:
            github_repository = await self._get_github_repository(imbi_project)
        elif self.gitlab and gitlab_project and not imbi_project:
            imbi_project = await self._get_imbi_project(
                gitlab_project=gitlab_project
            )
        elif self.gitlab and not gitlab_project and imbi_project:
            gitlab_project = await self._get_gitlab_project(imbi_project)

        run = models.WorkflowRun(
            workflow=self.workflow,
            github_repository=github_repository,
            gitlab_project=gitlab_project,
            imbi_project=imbi_project,
        )
        await self.workflow_engine.execute(run)


class WorkflowEngine:
    def __init__(self) -> None: ...

    async def execute(self, run: models.WorkflowRun) -> None:
        LOGGER.debug('Would execute workflow run: %s', run)
        print(run.model_dump_json(indent=2))  # noqa: T201 (debugging)
        await asyncio.sleep(1)
