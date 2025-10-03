"""Main automation controller for executing workflows across projects.

The controller implements an iterator pattern for processing different
target types (GitHub repositories, GitLab projects, Imbi projects) with
workflow execution, concurrency control, and comprehensive error handling.
"""

import argparse
import asyncio
import collections
import enum
import json
import logging
import pathlib

import async_lru

from imbi_automations import (
    clients,
    mixins,
    models,
    per_project_logging,
    workflow_engine,
    workflow_filter,
)

LOGGER = logging.getLogger(__name__)


class AutomationIterator(enum.Enum):
    """Enumeration of automation target types.

    Defines supported iteration patterns for GitHub repositories, GitLab
    projects, and Imbi project types and projects.
    """

    github_repositories = 1
    github_organization = 2
    github_project = 3
    gitlab_repositories = 4
    gitlab_group = 5
    gitlab_project = 6
    imbi_project_type = 7
    imbi_project = 8
    imbi_projects = 9


class Automation(mixins.WorkflowLoggerMixin):
    """Main automation controller for executing workflows across projects.

    Orchestrates workflow execution with iterator pattern support for
    different target types, project filtering, concurrency control, and
    resumable processing.
    """

    def __init__(
        self,
        args: argparse.Namespace,
        configuration: models.Configuration,
        workflow: models.Workflow,
    ) -> None:
        super().__init__(args.verbose)
        self.args = args
        self.cache: dict[
            str, dict[int, models.GitHubRepository | models.GitLabProject]
        ] = {}
        self.configuration = configuration
        self.counter = collections.Counter()
        self.logger = LOGGER
        self.workflow = workflow
        self.workflow_engine = workflow_engine.WorkflowEngine(
            configuration=self.configuration,
            workflow=workflow,
            verbose=args.verbose,
        )
        self.workflow_filter = workflow_filter.Filter(
            configuration, workflow, args.verbose
        )
        self._set_workflow_logger(workflow)

    @property
    def iterator(self) -> AutomationIterator:
        """Determine the iterator type based on CLI arguments.

        Returns:
            AutomationIterator enum value corresponding to the target type

        """
        if self.args.project_id:
            return AutomationIterator.imbi_project
        elif self.args.project_type:
            return AutomationIterator.imbi_project_type
        elif self.args.all_projects:
            return AutomationIterator.imbi_projects
        elif self.args.github_repository:
            return AutomationIterator.github_project
        elif self.args.github_organization:
            return AutomationIterator.github_organization
        elif self.args.all_github_repositories:
            return AutomationIterator.github_repositories
        elif self.args.gitlab_repository:
            return AutomationIterator.gitlab_project
        elif self.args.gitlab_group:
            return AutomationIterator.gitlab_group
        elif self.args.all_gitlab_repositories:
            return AutomationIterator.gitlab_repositories
        else:
            raise ValueError('No valid target argument provided')

    async def run(self) -> bool:
        match self.iterator:
            case AutomationIterator.github_repositories:
                return await self._process_github_repositories()
            case AutomationIterator.github_organization:
                return await self._process_github_organization()
            case AutomationIterator.github_project:
                return await self._process_github_project()
            case AutomationIterator.gitlab_repositories:
                return await self._process_gitlab_repositories()
            case AutomationIterator.gitlab_group:
                return await self._process_gitlab_group()
            case AutomationIterator.gitlab_project:
                return await self._process_gitlab_project()
            case AutomationIterator.imbi_project_type:
                return await self._process_imbi_project_type()
            case AutomationIterator.imbi_project:
                return await self._process_imbi_project()
            case AutomationIterator.imbi_projects:
                return await self._process_imbi_projects()

    async def _filter_projects(
        self, projects: list[models.ImbiProject]
    ) -> list[models.ImbiProject]:
        """Filter projects based on workflow configuration

        project_ids: set[int] = pydantic.Field(default_factory=set)
        project_types: set[str] = pydantic.Field(default_factory=set)
        project_facts: dict[str, str] = pydantic.Field(default_factory=dict)
        project_environments: set[str] = pydantic.Field(default_factory=set)
        requires_github_identifier: bool = False
        exclude_github_workflow_status: set[str] = pydantic.Field(
            default_factory=set
        )

        """
        if not self.workflow_filter:
            return projects

        original_count = len(projects)
        semaphore = asyncio.Semaphore(self.args.max_concurrency)

        async def filter_project(
            project: models.ImbiProject,
        ) -> models.ImbiProject | None:
            async with semaphore:
                return await self.workflow_filter.filter_project(
                    project, self.workflow.configuration.filter
                )

        projects = [
            project
            for project in await asyncio.gather(
                *[filter_project(project) for project in projects]
            )
            if project is not None
        ]
        self.logger.debug(
            'Filtered %d projects out of %d total',
            original_count - len(projects),
            original_count,
        )
        return projects

    @async_lru.alru_cache(maxsize=1024)
    async def _get_github_repository(
        self, project: models.ImbiProject
    ) -> models.GitHubRepository | None:
        if not self.configuration.github:
            return None
        client = clients.GitHub.get_instance(config=self.configuration)
        return await client.get_repository(project)

    @async_lru.alru_cache(maxsize=1024)
    async def _get_gitlab_project(
        self, project: models.ImbiProject
    ) -> models.GitLabProject | None:
        if not self.configuration.gitlab:
            return None
        client = clients.GitLab.get_instance(config=self.configuration)
        return await client.get_project(project)

    async def _process_github_repositories(self) -> bool: ...

    async def _process_github_organization(self) -> bool: ...

    async def _process_github_project(self) -> bool: ...

    async def _process_gitlab_repositories(self) -> bool: ...

    async def _process_gitlab_group(self) -> bool: ...

    async def _process_gitlab_project(self) -> bool: ...

    async def _process_imbi_project(self) -> bool:
        client = clients.Imbi.get_instance(config=self.configuration.imbi)
        project = await client.get_project(self.args.project_id)
        return await self._process_workflow_from_imbi_project(project)

    async def _process_imbi_project_type(self) -> bool:
        # Validate project type slug if cache available
        self._validate_project_type_slug(self.args.project_type)

        client = clients.Imbi.get_instance(config=self.configuration.imbi)
        projects = await client.get_projects_by_type(self.args.project_type)
        self.logger.debug('Found %d total active projects', len(projects))
        return await self._process_imbi_projects_common(projects)

    def _validate_project_type_slug(self, slug: str) -> None:
        """Validate project type slug against cache if available.

        Args:
            slug: Project type slug to validate

        Raises:
            ValueError: If slug is invalid

        """
        cache_file = (
            pathlib.Path.home() / '.imbi-automations' / 'fact-cache.json'
        )

        if not cache_file.exists():
            return  # Skip validation if no cache

        try:
            from imbi_automations import fact_registry

            registry = fact_registry.FactRegistry()
            registry._cache_file = cache_file
            registry._load_from_cache()

            if not registry.project_type_slugs:
                return

            if slug not in registry.project_type_slugs:
                # Find similar for suggestions
                similar = [
                    s
                    for s in registry.project_type_slugs
                    if s.startswith(slug[:3])
                ][:3]
                error_msg = f'Invalid project type slug: "{slug}"'
                if similar:
                    error_msg += f'. Did you mean: {", ".join(similar)}?'
                raise ValueError(error_msg)

        except (OSError, json.JSONDecodeError, KeyError):
            # Cache error, skip validation
            pass

    async def _process_imbi_projects(self) -> bool:
        client = clients.Imbi.get_instance(config=self.configuration.imbi)
        projects = await client.get_all_projects()
        return await self._process_imbi_projects_common(projects)

    async def _process_imbi_projects_common(
        self, projects: list[models.ImbiProject]
    ) -> bool:
        self.logger.debug('Found %d total active projects', len(projects))
        filtered = await self._filter_projects(projects)

        semaphore = asyncio.Semaphore(self.args.max_concurrency)

        async def limited_process(project: models.ImbiProject) -> bool:
            async with semaphore:
                return await self._process_workflow_from_imbi_project(project)

        if self.args.exit_on_error:
            tasks = []
            async with asyncio.TaskGroup() as task_group:
                for project in filtered:
                    tasks.append(
                        task_group.create_task(limited_process(project))
                    )
            results = [task.result() for task in tasks]
        else:
            results = await asyncio.gather(
                *[
                    asyncio.create_task(limited_process(project))
                    for project in filtered
                ]
            )
        return all(results)

    async def _process_workflow_from_imbi_project(
        self, project: models.ImbiProject
    ) -> bool:
        # Set up per-project log capture if error preservation is enabled
        log_capture = None
        token = None
        if self.configuration.preserve_on_error:
            log_capture = per_project_logging.ProjectLogCapture(project.id)
            token = log_capture.start()

        try:
            github_repository = await self._get_github_repository(project)
            gitlab_project = await self._get_gitlab_project(project)
            self._log_verbose_info(
                'Processing %s (%i)', project.name, project.id
            )

            success = await self.workflow_engine.execute(
                project, github_repository, gitlab_project
            )

            if not success:
                # Write debug logs to error directory
                if log_capture:
                    error_path = self.workflow_engine.get_last_error_path()
                    if error_path:
                        log_capture.write_to_file(error_path / 'debug.log')
                        self.logger.info(
                            'Wrote debug logs to %s', error_path / 'debug.log'
                        )

                if self.args.exit_on_error:
                    raise RuntimeError(
                        f'Workflow execution failed for {project.name} '
                        f'({project.id}) - check logs above for details'
                    )
                # Error details already logged by workflow_engine
                return False

            self._log_verbose_info(
                'Completed processing %s (%i)', project.name, project.id
            )
            return True
        finally:
            # Always cleanup log capture to prevent memory leaks
            if log_capture and token:
                log_capture.cleanup(token)
