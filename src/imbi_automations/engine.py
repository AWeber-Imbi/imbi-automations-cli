import argparse
import asyncio
import enum
import logging
import pathlib
import re
import subprocess
import typing
from collections import Counter

import httpx
import jinja2

from imbi_automations import (
    claude_code,
    environment_sync,
    git,
    github,
    gitlab,
    imbi,
    models,
    utils,
)

LOGGER = logging.getLogger(__name__)


class ActionResults:
    """Container for action results with dict and attribute access."""

    def __init__(self) -> None:
        self._results: dict[str, typing.Any] = {}

    def __getitem__(self, key: str) -> typing.Any:
        return self._results[key]

    def __setitem__(self, key: str, value: typing.Any) -> None:
        self._results[key] = value
        # Also store with normalized name for attribute access
        normalized_key = key.replace('-', '_')
        if normalized_key != key:
            setattr(self, normalized_key, value)

    def __contains__(self, key: str) -> bool:
        return key in self._results

    def keys(self) -> typing.KeysView[str]:
        return self._results.keys()

    def get(self, key: str, default: typing.Any = None) -> typing.Any:
        return self._results.get(key, default)

    def __iter__(self) -> typing.Iterator[str]:
        return iter(self._results)


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
        self.workflow_engine = WorkflowEngine(
            github_client=self.github,
            gitlab_client=self.gitlab,
            imbi_client=self.imbi,
            claude_code_config=configuration.claude_code,
            anthropic_config=configuration.anthropic,
        )

        # Initialize workflow execution counter
        self.workflow_stats = Counter()

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

        # Output workflow execution statistics
        self._output_workflow_stats()

    async def _process_github_repositories(self) -> None: ...

    async def _process_github_organization(self) -> None: ...

    async def _process_github_project(self) -> None: ...

    async def _process_gitlab_repositories(self) -> None: ...

    async def _process_gitlab_group(self) -> None: ...

    async def _process_gitlab_project(self) -> None: ...

    async def _process_imbi_project_types(self) -> None:
        """Iterate over all Imbi projects for a specific project type."""
        if not self.imbi:
            raise RuntimeError(
                'Imbi client is required for project type iteration'
            )

        project_type_slug = self.args.project_type
        LOGGER.info(
            'Processing Imbi projects for project type: %s', project_type_slug
        )

        projects = await self.imbi.get_projects_by_type(project_type_slug)
        LOGGER.info(
            'Found %d projects with project type %s',
            len(projects),
            project_type_slug,
        )

        # Apply cheap filters FIRST (project_facts, github_id)
        projects = self._filter_projects_by_basic_criteria(projects)

        # Apply start-from-project filtering SECOND (on smaller dataset)
        if (
            hasattr(self.args, 'start_from_project')
            and self.args.start_from_project
        ):
            projects = self._filter_projects_from_start(
                projects, self.args.start_from_project
            )

        # Apply expensive GitHub filtering LAST (smallest dataset)
        projects = await self._filter_projects_by_github_criteria(projects)

        for project in projects:
            try:
                execution_result = await self._execute_workflow_run(
                    imbi_project=project
                )

                # Stop processing if rate limited
                if execution_result == 'skipped_rate_limited':
                    LOGGER.error(
                        'GitHub API rate limit exceeded. Stopping execution. '
                        'Wait for rate limit reset before resuming with '
                        '--start-from-project %s',
                        project.slug,
                    )
                    break

            except (RuntimeError, httpx.HTTPError, ValueError) as e:
                LOGGER.error(
                    'Failed to process project %d (%s): %s - %s',
                    project.id,
                    project.name,
                    type(e).__name__,
                    str(e),
                )
                # Continue processing other projects

    async def _process_imbi_project(self) -> None:
        """Process a single Imbi project."""
        project = await self.imbi.get_project(self.args.project_id)
        try:
            await self._execute_workflow_run(imbi_project=project)
        except (RuntimeError, httpx.HTTPError, ValueError) as e:
            LOGGER.error(
                'Failed to process project %d (%s): %s - %s',
                project.id,
                project.name,
                type(e).__name__,
                str(e),
            )
            raise  # Re-raise for single project processing

    async def _process_imbi_projects(self) -> None:
        """Iterate over all Imbi projects and execute workflow runs."""
        projects = await self.imbi.get_all_projects()
        LOGGER.debug('Found %d total active projects', len(projects))

        # Apply cheap filters FIRST (project_types, facts, github_id)
        projects = self._filter_projects_by_basic_criteria(projects)

        # Apply start-from-project filtering SECOND (on smaller dataset)
        if (
            hasattr(self.args, 'start_from_project')
            and self.args.start_from_project
        ):
            projects = self._filter_projects_from_start(
                projects, self.args.start_from_project
            )

        # Apply expensive GitHub filtering LAST (smallest dataset)
        projects = await self._filter_projects_by_github_criteria(projects)

        LOGGER.info('Processing %d filtered projects', len(projects))

        for project in projects:
            try:
                execution_result = await self._execute_workflow_run(
                    imbi_project=project
                )

                # Stop processing if rate limited
                if execution_result == 'skipped_rate_limited':
                    LOGGER.error(
                        'GitHub API rate limit exceeded. Stopping execution. '
                        'Wait for rate limit reset before resuming with '
                        '--start-from-project %s',
                        project.slug,
                    )
                    break

            except (RuntimeError, httpx.HTTPError, ValueError) as e:
                LOGGER.error(
                    'Failed to process project %d (%s): %s - %s',
                    project.id,
                    project.name,
                    type(e).__name__,
                    str(e),
                )
                # Continue processing other projects

    def _filter_projects_from_start(
        self, projects: list[models.ImbiProject], start_from_slug: str
    ) -> list[models.ImbiProject]:
        """Filter projects to start from a specific project slug.

        Args:
            projects: List of Imbi projects
            start_from_slug: Project slug to start from (exclusive)

        Returns:
            Filtered list of projects starting after the specified slug

        """
        original_count = len(projects)

        # Find the index of the start_from_project
        start_index = None
        for i, project in enumerate(projects):
            if project.slug == start_from_slug:
                start_index = i + 1  # Start from the next project
                break

        if start_index is None:
            LOGGER.warning(
                'Start project slug "%s" not found in project list, '
                'processing all %d projects',
                start_from_slug,
                original_count,
            )
            return projects

        filtered_projects = projects[start_index:]
        skipped_count = original_count - len(filtered_projects)

        LOGGER.debug(
            'Starting from project "%s": skipping %d projects, '
            'processing %d projects',
            start_from_slug,
            skipped_count,
            len(filtered_projects),
        )

        return filtered_projects

    async def _filter_projects_by_workflow(
        self, projects: list[models.ImbiProject]
    ) -> list[models.ImbiProject]:
        """Filter projects based on workflow filter criteria.

        Args:
            projects: List of Imbi projects to filter

        Returns:
            Filtered list of projects that match workflow criteria

        """
        if not self.workflow.configuration.filter:
            return projects  # No filter means all projects match

        original_count = len(projects)
        LOGGER.debug(
            'Applying workflow filters to %d projects', original_count
        )
        filtered_projects = []

        for project in projects:
            # Apply basic filters first (fast)
            if not self._project_matches_basic_filters(project):
                continue

            # Apply GitHub-based filters (slower, requires API calls)
            if await self._project_matches_github_filters(project):
                filtered_projects.append(project)

        filtered_count = len(filtered_projects)
        excluded_count = original_count - filtered_count

        if excluded_count > 0:
            LOGGER.debug(
                'Workflow filter excluded %d projects, processing %d projects',
                excluded_count,
                filtered_count,
            )

        return filtered_projects

    def _filter_projects_by_basic_criteria(
        self, projects: list[models.ImbiProject]
    ) -> list[models.ImbiProject]:
        """Filter projects by cheap criteria (no GitHub API calls).

        Args:
            projects: List of Imbi projects to filter

        Returns:
            Filtered list of projects that match basic criteria

        """
        if not self.workflow.configuration.filter:
            return projects  # No filter means all projects match

        original_count = len(projects)
        filtered_projects = [
            project
            for project in projects
            if self._project_matches_basic_filters(project)
        ]

        filtered_count = len(filtered_projects)
        excluded_count = original_count - filtered_count

        if excluded_count > 0:
            LOGGER.debug(
                'Applied basic filters: %d → %d projects',
                original_count,
                filtered_count,
            )

        return filtered_projects

    async def _filter_projects_by_github_criteria(
        self, projects: list[models.ImbiProject]
    ) -> list[models.ImbiProject]:
        """Filter projects by GitHub-based criteria (GitHub API calls).

        Args:
            projects: List of Imbi projects to filter

        Returns:
            Filtered list of projects that match GitHub criteria

        """
        workflow_filter = self.workflow.configuration.filter
        if (
            not workflow_filter
            or not workflow_filter.exclude_github_workflow_status
        ):
            return projects  # No GitHub filters to apply

        original_count = len(projects)
        filtered_projects = []

        LOGGER.debug('Applying GitHub filters to %d projects', original_count)

        for project in projects:
            if await self._project_matches_github_filters(project):
                filtered_projects.append(project)

        filtered_count = len(filtered_projects)
        excluded_count = original_count - filtered_count

        if excluded_count > 0:
            LOGGER.info(
                'Applied GitHub filters: %d → %d projects',
                original_count,
                filtered_count,
            )

        return filtered_projects

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
            LOGGER.debug('No GitHub client available')
            return None

        LOGGER.debug(
            'Looking up GitHub repository for Imbi project %d (%s)',
            imbi_project.id,
            imbi_project.name,
        )

        # Try GitHub identifier first
        if imbi_project.identifiers and imbi_project.identifiers.get('github'):
            github_id = imbi_project.identifiers['github']
            LOGGER.debug('Found GitHub identifier: %s', github_id)
            repository = await self.github.get_repository_by_id(github_id)
            if repository:
                return repository
            LOGGER.debug(
                'GitHub identifier %s failed, trying fallback methods',
                github_id,
            )

        # Fall back to GitHub link URL
        if (
            imbi_project.links
            and self.configuration.imbi.github_link in imbi_project.links
        ):
            github_url = imbi_project.links[
                self.configuration.imbi.github_link
            ]
            LOGGER.debug('Found GitHub link: %s', github_url)
            # Extract org/repo from GitHub URL
            match = re.match(r'https://[^/]+/([^/]+)/([^/]+)/?$', github_url)
            if match:
                org, repo_name = match.groups()
                LOGGER.debug(
                    'Extracted org=%s, repo=%s from URL', org, repo_name
                )
                repository = await self.github.get_repository(org, repo_name)
                if repository:
                    return repository

        # Final fallback: try project-type-slug/project-slug pattern
        org = imbi_project.project_type_slug
        repo_name = imbi_project.slug
        LOGGER.debug(
            'Trying fallback org=%s, repo=%s based on project slugs',
            org,
            repo_name,
        )
        repository = await self.github.get_repository(org, repo_name)
        if repository:
            LOGGER.debug(
                'Found repository via slug fallback: %s/%s', org, repo_name
            )
            return repository

        LOGGER.debug(
            'All GitHub lookup methods failed. Links: %s, Looking for: %s',
            list(imbi_project.links.keys()) if imbi_project.links else None,
            self.configuration.imbi.github_link,
        )

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
        # Ensure we have all required project references for the workflow

        # If we have Imbi project but missing GitHub/GitLab, try to get them
        if imbi_project:
            if self.github and not github_repository:
                LOGGER.debug(
                    'Attempting to get GitHub repository for Imbi project %d',
                    imbi_project.id,
                )
                try:
                    github_repository = await self._get_github_repository(
                        imbi_project
                    )
                    if github_repository:
                        LOGGER.debug(
                            'Found GitHub repository: %s',
                            github_repository.full_name,
                        )
                except models.GitHubRateLimitError as exc:
                    LOGGER.warning(
                        'GitHub API rate limited for Imbi project %d (%s): %s',
                        imbi_project.id,
                        imbi_project.name,
                        exc,
                    )
                    return 'skipped_rate_limited'
                except models.GitHubNotFoundError:
                    # Repository access denied or other auth issues
                    pass  # Handled by "no GitHub repository" check below
                except (
                    httpx.HTTPError,
                    httpx.RequestError,
                    ValueError,
                    RuntimeError,
                ) as exc:
                    LOGGER.warning(
                        'GitHub API error for Imbi project %d (%s): %s',
                        imbi_project.id,
                        imbi_project.name,
                        exc,
                    )
                    return 'skipped_github_api_error'
            elif self.gitlab and not gitlab_project:
                try:
                    gitlab_project = await self._get_gitlab_project(
                        imbi_project
                    )
                except (
                    httpx.HTTPError,
                    httpx.RequestError,
                    ValueError,
                    RuntimeError,
                ) as exc:
                    LOGGER.warning(
                        'Failed to lookup GitLab project for '
                        'Imbi project %d (%s): %s',
                        imbi_project.id,
                        imbi_project.name,
                        exc,
                    )

        # If we have GitHub repository but missing Imbi project, get it
        if github_repository and not imbi_project and self.imbi:
            imbi_project = await self._get_imbi_project(
                github_repository=github_repository
            )

        # If we have GitLab project but missing Imbi project, get it
        if gitlab_project and not imbi_project and self.imbi:
            imbi_project = await self._get_imbi_project(
                gitlab_project=gitlab_project
            )

        # Validate we have required project references for the workflow
        if not imbi_project:
            raise RuntimeError(
                'Imbi project is required for workflow execution'
            )

        # Project filtering is now done upfront in processing methods

        # Check if workflow requires GitHub repository but we don't have one
        if self._workflow_requires_github() and not github_repository:
            LOGGER.warning(
                'Skipping project %d (%s - %s) - no GitHub repository found',
                imbi_project.id,
                imbi_project.name,
                imbi_project.project_type_slug,
            )
            return 'skipped_no_github_repository'

        # Check if workflow requires GitLab project but we don't have one
        if self._workflow_requires_gitlab() and not gitlab_project:
            LOGGER.info(
                'Skipping project %d (%s) - no GitLab project',
                imbi_project.id,
                imbi_project.name,
            )
            return 'skipped_no_gitlab_project'

        run = models.WorkflowRun(
            workflow=self.workflow,
            github_repository=github_repository,
            gitlab_project=gitlab_project,
            imbi_project=imbi_project,
        )

        # Log context availability for debugging
        LOGGER.debug(
            'Context: imbi=%s, github=%s, gitlab=%s',
            imbi_project.id if imbi_project else None,
            github_repository.full_name if github_repository else None,
            gitlab_project.path_with_namespace if gitlab_project else None,
        )

        # Execute workflow and track results
        try:
            execution_result = await self.workflow_engine.execute(run)

            # Track based on execution result
            if execution_result == 'skipped_rate_limited':
                self.workflow_stats['skipped_rate_limited'] += 1
            elif execution_result == 'skipped_github_api_error':
                self.workflow_stats['skipped_github_api_error'] += 1
            elif execution_result == 'skipped_no_github_repository':
                self.workflow_stats['skipped_no_github_repository'] += 1
            elif execution_result == 'skipped_no_gitlab_project':
                self.workflow_stats['skipped_no_gitlab_project'] += 1
            elif execution_result == 'skipped_remote_conditions':
                self.workflow_stats['skipped_remote_conditions'] += 1
            elif execution_result == 'skipped_conditions':
                self.workflow_stats['skipped_conditions'] += 1
            elif execution_result == 'skipped_no_repository':
                self.workflow_stats['skipped_no_repository'] += 1
            elif execution_result == 'successful_no_changes':
                self.workflow_stats['successful_no_changes'] += 1
            elif execution_result == 'successful_changes_pushed':
                self.workflow_stats['successful_changes_pushed'] += 1
            elif execution_result == 'successful_pr_created':
                self.workflow_stats['successful_pr_created'] += 1
            else:
                # Fallback for any other 'successful' variants
                self.workflow_stats['successful'] += 1

        except (RuntimeError, httpx.HTTPError, ValueError) as exc:
            self.workflow_stats['errored'] += 1
            project_info = (
                f'{imbi_project.name} ({imbi_project.project_type})'
                if imbi_project
                else 'Unknown Project'
            )
            LOGGER.error(
                'Workflow execution failed for project %s: %s - %s',
                project_info,
                type(exc).__name__,
                str(exc),
            )

    def _workflow_requires_github(self) -> bool:
        """Check if workflow requires GitHub repository context."""
        for action in self.workflow.configuration.actions:
            # Check if any templates reference github_repository
            kwargs_to_check = []

            if action.value:
                kwargs_to_check.append(action.value.kwargs)

            if action.target and isinstance(
                action.target, models.WorkflowActionTarget
            ):
                kwargs_to_check.append(action.target.kwargs)

            for kwargs in kwargs_to_check:
                if kwargs:
                    for value in kwargs.model_dump().values():
                        if (
                            isinstance(value, str)
                            and 'github_repository' in value
                        ):
                            return True

            # Check if any client calls are to GitHub
            if action.value and action.value.client == 'github':
                return True
            if (
                action.target
                and isinstance(action.target, models.WorkflowActionTarget)
                and action.target.client == 'github'
            ):
                return True
        return False

    def _workflow_requires_gitlab(self) -> bool:
        """Check if workflow requires GitLab project context."""
        for action in self.workflow.configuration.actions:
            # Check if any templates reference gitlab_project
            kwargs_to_check = []

            if action.value:
                kwargs_to_check.append(action.value.kwargs)

            if action.target and isinstance(
                action.target, models.WorkflowActionTarget
            ):
                kwargs_to_check.append(action.target.kwargs)

            for kwargs in kwargs_to_check:
                if kwargs:
                    for value in kwargs.model_dump().values():
                        if (
                            isinstance(value, str)
                            and 'gitlab_project' in value
                        ):
                            return True

            # Check if any client calls are to GitLab
            if action.value and action.value.client == 'gitlab':
                return True
            if (
                action.target
                and isinstance(action.target, models.WorkflowActionTarget)
                and action.target.client == 'gitlab'
            ):
                return True
        return False

    def _project_matches_basic_filters(
        self, imbi_project: models.ImbiProject
    ) -> bool:
        """Check if an Imbi project matches basic workflow filter criteria.

        This includes project_ids, project_types, project_facts, and
        requires_github_identifier filters. GitHub API-based filters are
        handled separately.

        Args:
            imbi_project: Imbi project to check against filter

        Returns:
            True if project matches basic filter criteria, False otherwise
        """
        workflow_filter = self.workflow.configuration.filter
        if not workflow_filter:
            return True  # No filter means all projects match

        # Check project_ids filter
        if (
            workflow_filter.project_ids
            and imbi_project.id not in workflow_filter.project_ids
        ):
            LOGGER.debug(
                'Project %d (%s) excluded by project_ids filter',
                imbi_project.id,
                imbi_project.name,
            )
            return False

        # Check project_types filter
        if (
            workflow_filter.project_types
            and imbi_project.project_type_slug
            not in workflow_filter.project_types
        ):
            LOGGER.debug(
                'Project %d (%s) excluded by project_types filter - type: %s',
                imbi_project.id,
                imbi_project.name,
                imbi_project.project_type_slug,
            )
            return False

        # Check project_facts filter
        if workflow_filter.project_facts:
            project_facts = imbi_project.facts or {}
            for (
                fact_name,
                expected_value,
            ) in workflow_filter.project_facts.items():
                actual_value = project_facts.get(fact_name)

                # Convert to string for comparison (facts can be various types)
                actual_str = (
                    str(actual_value) if actual_value is not None else None
                )

                if actual_str != expected_value:
                    LOGGER.debug(
                        'Project %d (%s) excluded by project_facts filter - '
                        '%s: expected "%s", got "%s"',
                        imbi_project.id,
                        imbi_project.name,
                        fact_name,
                        expected_value,
                        actual_str,
                    )
                    return False

        # Check requires_github_identifier filter
        if workflow_filter.requires_github_identifier:
            has_github_id = (
                imbi_project.identifiers
                and imbi_project.identifiers.get('github') is not None
            )
            if not has_github_id:
                LOGGER.debug(
                    'Project %d (%s) excluded by requires_github_identifier',
                    imbi_project.id,
                    imbi_project.name,
                )
                return False

        LOGGER.debug(
            'Project %d (%s) matches basic filter criteria',
            imbi_project.id,
            imbi_project.name,
        )
        return True

    async def _project_matches_github_filters(
        self, imbi_project: models.ImbiProject
    ) -> bool:
        """Check if an Imbi project matches GitHub-based workflow filters.

        Args:
            imbi_project: Imbi project to check against GitHub filters

        Returns:
            True if project matches GitHub filter criteria, False otherwise
        """
        workflow_filter = self.workflow.configuration.filter
        if (
            not workflow_filter
            or not workflow_filter.exclude_github_workflow_status
        ):
            return True  # No GitHub filters to check

        # Get GitHub repository for this project
        try:
            github_repository = await self._get_github_repository(imbi_project)
            if not github_repository:
                LOGGER.debug(
                    'Project %d (%s) excluded - no GitHub repository found',
                    imbi_project.id,
                    imbi_project.name,
                )
                return False

            # Check workflow status
            if self.github:
                org, repo = github_repository.full_name.split('/', 1)
                workflow_status = await self.github.get_latest_workflow_status(
                    org, repo
                )

                if (
                    workflow_status
                    in workflow_filter.exclude_github_workflow_status
                ):
                    LOGGER.debug(
                        'Project %d (%s) excluded by workflow status filter - '
                        'status: %s (excluded: %s)',
                        imbi_project.id,
                        imbi_project.name,
                        workflow_status,
                        workflow_filter.exclude_github_workflow_status,
                    )
                    return False

        except (
            models.GitHubRateLimitError,
            models.GitHubNotFoundError,
            Exception,
        ) as exc:
            LOGGER.debug(
                'Project %d (%s) GitHub filter check failed: %s',
                imbi_project.id,
                imbi_project.name,
                exc,
            )
            # On error, include the project (don't exclude due to API issues)
            return True

        LOGGER.debug(
            'Project %d (%s) matches GitHub filter criteria',
            imbi_project.id,
            imbi_project.name,
        )
        return True

    def _output_workflow_stats(self) -> None:
        """Output workflow execution statistics."""
        total_workflows = sum(self.workflow_stats.values())

        if total_workflows == 0:
            LOGGER.info('No workflows were processed')
            return

        LOGGER.info('')
        LOGGER.info('=== Workflow Execution Statistics ===')
        LOGGER.info('Total projects processed: %d', total_workflows)
        LOGGER.info('')

        # Output each stat category in logical order
        stat_types = [
            # Successful outcomes
            'successful_pr_created',
            'successful_changes_pushed',
            'successful_no_changes',
            'successful',  # Fallback category
            # Error outcomes
            'errored',
            # Skip reasons - API issues first
            'skipped_rate_limited',
            'skipped_github_api_error',
            'skipped_no_github_repository',
            'skipped_no_gitlab_project',
            'skipped_remote_conditions',
            'skipped_conditions',
            'skipped_no_repository',
        ]
        for stat_type in stat_types:
            count = self.workflow_stats[stat_type]
            if count > 0:
                percentage = (count / total_workflows) * 100
                display_name = stat_type.replace('_', ' ').title()
                LOGGER.info(
                    '  %s: %d (%.1f%%)', display_name, count, percentage
                )

        LOGGER.info('')

        LOGGER.info('=====================================')


class WorkflowEngine:
    def __init__(
        self,
        github_client: github.GitHub | None = None,
        gitlab_client: gitlab.GitLab | None = None,
        imbi_client: imbi.Imbi | None = None,
        claude_code_config: models.ClaudeCodeConfiguration | None = None,
        anthropic_config: models.AnthropicConfiguration | None = None,
    ) -> None:
        self.github = github_client
        self.gitlab = gitlab_client
        self.imbi = imbi_client
        self.utils = utils.Utils()
        self.claude_code: claude_code.ClaudeCode | None = None
        self._claude_code_config = claude_code_config
        self._anthropic_config = anthropic_config

        # Initialize Jinja2 environment
        self.jinja_env = jinja2.Environment(
            variable_start_string='{{',
            variable_end_string='}}',
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,  # Enable autoescape for security
        )

        # Store action results for templating
        self.action_results = ActionResults()

        # Initialize logging - start with base logger
        self._base_logger = LOGGER
        self.logger = self._base_logger

    def set_workflow_logger(self, workflow_path: pathlib.Path) -> None:
        """Set logger name to workflow directory name.

        Args:
            workflow_path: Path to the workflow directory
        """
        workflow_dir_name = workflow_path.name
        self.logger = logging.getLogger(workflow_dir_name)

    def _create_template_context(
        self, run: models.WorkflowRun
    ) -> dict[str, typing.Any]:
        """Create template context from workflow run data."""
        context = {
            'workflow': run.workflow,
            'workflow_run': run,
            'actions': self.action_results,
        }

        if run.github_repository:
            context['github_repository'] = run.github_repository
        if run.gitlab_project:
            context['gitlab_project'] = run.gitlab_project
        if run.imbi_project:
            context['imbi_project'] = run.imbi_project
        if run.working_directory:
            context['working_directory'] = run.working_directory

        return context

    def _render_template_kwargs(
        self,
        kwargs: models.WorkflowActionKwargs,
        context: dict[str, typing.Any],
    ) -> dict[str, typing.Any]:
        """Render Jinja2 templates in action kwargs."""
        rendered = {}

        for key, value in kwargs.model_dump().items():
            if isinstance(value, str) and '{{' in value:
                self.logger.debug('Rendering template for %s: %s', key, value)
                self.logger.debug(
                    'Available context keys: %s', list(context.keys())
                )
                if 'actions' in context:
                    self.logger.debug(
                        'Available actions: %s',
                        list(context['actions'].keys()),
                    )
                # Check if this is a direct reference to an action result
                if value.strip().startswith(
                    '{{ actions['
                ) and value.strip().endswith('].result }}'):
                    # Extract action name and return actual result object
                    import re

                    action_match = re.match(
                        r'\s*{{\s*actions\[[\'"](.*?)[\'"]\]\.result\s*}}\s*',
                        value,
                    )
                    if action_match:
                        action_name = action_match.group(1)
                        if action_name in context.get('actions', {}):
                            rendered[key] = context['actions'][action_name][
                                'result'
                            ]
                            self.logger.debug(
                                'Rendered %s: direct action result → %s',
                                key,
                                type(rendered[key]),
                            )
                            continue

                template = self.jinja_env.from_string(value)
                rendered_value = template.render(context)
                # Try to convert back to original type if it was a number
                if rendered_value.isdigit():
                    rendered[key] = int(rendered_value)
                elif rendered_value.replace('.', '').isdigit():
                    rendered[key] = float(rendered_value)
                else:
                    rendered[key] = rendered_value
                self.logger.debug('Rendered %s → %s', key, rendered[key])
            else:
                rendered[key] = value

        return rendered

    def _get_client(self, client_name: str) -> typing.Any:
        """Get client instance by name."""
        clients = {
            'github': self.github,
            'gitlab': self.gitlab,
            'imbi': self.imbi,
            'utils': self.utils,
            'environment_sync': environment_sync,
        }

        client = clients.get(client_name)
        if not client:
            raise ValueError(f'Client not available: {client_name}')
        return client

    def _apply_value_mapping(
        self, value: typing.Any, mapping: dict[str, str] | None
    ) -> typing.Any:
        """Apply value mapping transformation."""
        if not mapping:
            return value

        str_value = str(value) if value is not None else 'null'
        return mapping.get(str_value, value)

    async def _execute_action(
        self, action: models.WorkflowAction, context: dict[str, typing.Any]
    ) -> typing.Any:
        """Execute a single workflow action based on its type."""
        self.logger.debug(
            'Executing action %s of type %s', action.name, action.type
        )

        # Dispatch to appropriate handler based on action type
        match action.type:
            case models.WorkflowActionTypes.callable:
                return await self._execute_callable_action(action, context)
            case models.WorkflowActionTypes.templates:
                return await self._execute_templates_action(action, context)
            case models.WorkflowActionTypes.file:
                return await self._execute_file_action(action, context)
            case models.WorkflowActionTypes.claude:
                return await self._execute_claude_action(action, context)
            case models.WorkflowActionTypes.shell:
                return await self._execute_shell_action(action, context)
            case models.WorkflowActionTypes.ai_editor:
                return await self._execute_ai_editor_action(action, context)
            case models.WorkflowActionTypes.git_revert:
                return await self._execute_git_revert_action(action, context)
            case models.WorkflowActionTypes.git_extract:
                return await self._execute_git_extract_action(action, context)
            case models.WorkflowActionTypes.docker_extract:
                return await self._execute_docker_extract_action(
                    action, context
                )
            case models.WorkflowActionTypes.add_trailing_whitespace:
                return await self._execute_add_trailing_whitespace_action(action, context)
            case _:
                raise ValueError(f'Unsupported action type: {action.type}')

    async def _execute_callable_action(
        self, action: models.WorkflowAction, context: dict[str, typing.Any]
    ) -> typing.Any:
        """Execute a callable workflow action (client method call)."""

        if not action.value:
            raise RuntimeError(
                f'Callable action {action.name} requires value configuration'
            )

        # Get value via client method call
        value_client = self._get_client(action.value.client)
        value_method = getattr(value_client, action.value.method)
        value_kwargs = self._render_template_kwargs(
            action.value.kwargs, context
        )

        self.logger.debug(
            'Calling %s.%s with kwargs: %s',
            action.value.client,
            action.value.method,
            value_kwargs,
        )

        result = await value_method(**value_kwargs)

        # Apply value mapping if configured
        mapped_result = self._apply_value_mapping(result, action.value_mapping)

        self.logger.debug(
            'Action %s result: %s (mapped: %s)',
            action.name,
            result,
            mapped_result,
        )

        # Store result for future template references
        self.action_results[action.name] = {'result': mapped_result}

        # Update context for any subsequent template rendering
        context['actions'] = self.action_results

        # Execute target if configured (only for callable actions)
        if action.target and isinstance(
            action.target, models.WorkflowActionTarget
        ):
            target_client = self._get_client(action.target.client)
            target_method = getattr(target_client, action.target.method)
            target_kwargs = self._render_template_kwargs(
                action.target.kwargs, context
            )

            self.logger.debug(
                'Calling %s.%s with kwargs: %s',
                action.target.client,
                action.target.method,
                target_kwargs,
            )

            try:
                await target_method(**target_kwargs)
            except (RuntimeError, httpx.HTTPError, ValueError) as e:
                self.logger.error(
                    'Failed to execute action %s: %s - %s',
                    action.name,
                    type(e).__name__,
                    str(e),
                )
                # Log the error but don't re-raise to continue processing
                return None

        return mapped_result

    async def _execute_templates_action(
        self, action: models.WorkflowAction, context: dict[str, typing.Any]
    ) -> typing.Any:
        """Execute templates action by copying files from templates dir."""
        import os
        import shutil

        workflow_run = context['workflow_run']

        if not workflow_run.working_directory:
            raise RuntimeError(
                f'Templates action {action.name} requires cloned repository '
                f'(working_directory)'
            )

        # Get the templates directory path
        templates_dir = workflow_run.workflow.path / 'templates'

        if not templates_dir.exists() or not templates_dir.is_dir():
            self.logger.warning(
                'Templates directory not found for action %s: %s',
                action.name,
                templates_dir,
            )
            self.action_results[action.name] = {'result': 'no_templates'}
            context['actions'] = self.action_results
            return 'no_templates'

        self.logger.info(
            'Copying templates from %s to %s',
            templates_dir,
            workflow_run.working_directory,
        )

        copied_files = []
        errors = []

        # Walk through all files in templates directory
        for root, _dirs, files in os.walk(templates_dir):
            for file in files:
                template_file = pathlib.Path(root) / file

                # Calculate relative path from templates directory
                rel_path = template_file.relative_to(templates_dir)

                # Determine target path
                if template_file.suffix == '.j2':
                    # Remove .j2 extension for Jinja2 templates
                    target_rel_path = rel_path.with_suffix('')
                else:
                    target_rel_path = rel_path

                # Apply target directory if specified
                if isinstance(action.target, str) and action.target != '/':
                    # Target is a subdirectory path
                    target_base_path = pathlib.Path(action.target.lstrip('/'))
                    target_file = (
                        workflow_run.working_directory
                        / target_base_path
                        / target_rel_path
                    )
                else:
                    # Default to repository root
                    target_file = (
                        workflow_run.working_directory / target_rel_path
                    )

                try:
                    # Create target directory if it doesn't exist
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                    if template_file.suffix == '.j2':
                        # Render Jinja2 template
                        await self._render_template_file(
                            template_file, target_file, context
                        )
                    else:
                        # Copy file directly, preserving permissions
                        shutil.copy2(template_file, target_file)

                    copied_files.append(str(target_rel_path))
                    self.logger.debug(
                        'Copied template file: %s → %s',
                        rel_path,
                        target_rel_path,
                    )

                except (OSError, PermissionError, FileNotFoundError) as exc:
                    error_msg = f'Failed to copy {rel_path}: {exc}'
                    errors.append(error_msg)
                    self.logger.error(error_msg)

        # Commit changes if files were copied
        from . import git

        if copied_files:
            try:
                # Stage the copied files
                await git.add_files(
                    workflow_run.working_directory, copied_files
                )

                # Create commit message with proper formatting
                commit_message = f'imbi-automations: {action.name}'
                if len(copied_files) == 1:
                    commit_message += f'\n\nAdded: {copied_files[0]}'
                else:
                    commit_message += '\n\nAdded files:\n'
                    commit_message += '\n'.join(f'- {f}' for f in copied_files)

                # Add ci skip if configured
                if workflow_run.workflow.configuration.ci_skip_checks:
                    commit_message += '\n\n[ci skip]'

                commit_message += (
                    '\n\nAuthored-By: Imbi Automations <noreply@aweber.com>'
                )

                # Commit the changes
                commit_sha = await git.commit_changes(
                    working_directory=workflow_run.working_directory,
                    message=commit_message,
                    author_name='Imbi Automations',
                    author_email='noreply@aweber.com',
                )

                self.logger.info(
                    'Templates action %s committed %d files: %s',
                    action.name,
                    len(copied_files),
                    commit_sha[:8] if commit_sha else 'unknown',
                )

            except (OSError, subprocess.CalledProcessError) as exc:
                self.logger.warning(
                    'Failed to commit templates for action %s: %s',
                    action.name,
                    exc,
                )

        # Determine result status
        if errors:
            if copied_files:
                status = 'partial'
                self.logger.warning(
                    'Templates action %s completed with errors: '
                    '%d copied, %d failed',
                    action.name,
                    len(copied_files),
                    len(errors),
                )
            else:
                status = 'failed'
                self.logger.error(
                    'Templates action %s failed: %s',
                    action.name,
                    '; '.join(errors),
                )
        else:
            status = 'success'
            self.logger.info(
                'Templates action %s completed successfully: %d files copied',
                action.name,
                len(copied_files),
            )

        result = {
            'status': status,
            'copied_files': copied_files,
            'errors': errors,
        }

        self.action_results[action.name] = {'result': result}
        context['actions'] = self.action_results

        return result

    async def _execute_file_action(
        self, action: models.WorkflowAction, context: dict[str, typing.Any]
    ) -> typing.Any:
        """Execute a file workflow action (rename, remove, etc.)."""

        if not action.command:
            raise ValueError(
                f'File action {action.name} missing required command'
            )

        if not action.source:
            raise ValueError(
                f'File action {action.name} missing required source'
            )

        # Get working directory from context
        workflow_run = context.get('workflow_run')
        if not workflow_run or not workflow_run.working_directory:
            raise RuntimeError(
                f'File action {action.name} requires working directory'
            )

        working_directory = workflow_run.working_directory
        source_path = working_directory / action.source

        self.logger.debug(
            'Executing file action %s: %s on %s',
            action.name,
            action.command,
            action.source,
        )

        result = {}

        match action.command:
            case 'rename':
                if not action.destination:
                    raise ValueError(
                        f'Rename action {action.name} missing destination'
                    )

                destination_path = working_directory / action.destination

                # Validate source file exists
                if not source_path.exists():
                    raise FileNotFoundError(
                        f'Source file not found: {action.source}'
                    )

                # Validate destination doesn't exist
                if destination_path.exists():
                    raise FileExistsError(
                        f'Destination file already exists: '
                        f'{action.destination}'
                    )

                # Perform rename
                source_path.rename(destination_path)

                self.logger.info(
                    'Renamed file %s to %s', action.source, action.destination
                )

                result = {
                    'operation': 'rename',
                    'source': action.source,
                    'destination': action.destination,
                    'status': 'success',
                }

            case 'remove':
                # Validate source file exists
                if not source_path.exists():
                    raise FileNotFoundError(
                        f'Source file not found: {action.source}'
                    )

                # Perform remove
                source_path.unlink()

                self.logger.debug('Removed file %s', action.source)

                result = {
                    'operation': 'remove',
                    'source': action.source,
                    'status': 'success',
                }

            case 'regex':
                # Placeholder for future regex implementation
                raise NotImplementedError(
                    'Regex file operations not yet implemented'
                )

            case _:
                raise ValueError(f'Unsupported file command: {action.command}')

        # Commit the file operation
        from . import git

        try:
            changed_files = await git.get_git_status(working_directory)
            if changed_files:
                # Stage changed files
                await git.add_files(working_directory, changed_files)

                # Create commit message
                operation = result.get('operation', action.command)
                commit_message = (
                    f'imbi-automations: {action.name} ({operation})'
                )

                if operation == 'rename':
                    commit_message += (
                        f'\n\nRenamed: {action.source} → {action.destination}'
                    )
                elif operation == 'remove':
                    commit_message += f'\n\nRemoved: {action.source}'
                else:
                    commit_message += '\n\nModified files:\n'
                    commit_message += '\n'.join(
                        f'- {f}' for f in changed_files
                    )

                # Add ci skip if configured
                if workflow_run.workflow.configuration.ci_skip_checks:
                    commit_message += '\n\n[ci skip]'

                commit_message += (
                    '\n\nAuthored-By: Imbi Automations <noreply@aweber.com>'
                )

                # Commit the changes
                commit_sha = await git.commit_changes(
                    working_directory=working_directory,
                    message=commit_message,
                    author_name='Imbi Automations',
                    author_email='noreply@aweber.com',
                )

                self.logger.debug(
                    'File action %s committed changes: %s',
                    action.name,
                    commit_sha[:8] if commit_sha else 'unknown',
                )

                # Add commit info to result
                result['committed'] = True
                result['commit_sha'] = commit_sha
            else:
                result['committed'] = False

        except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
            self.logger.warning(
                'Failed to commit changes for file action %s: %s',
                action.name,
                exc,
            )
            result['committed'] = False
            result['commit_error'] = str(exc)

        # Store result for future template references
        self.action_results[action.name] = {'result': result}
        context['actions'] = self.action_results

        return result

    async def _render_template_file(
        self,
        template_file: pathlib.Path,
        target_file: pathlib.Path,
        context: dict[str, typing.Any],
    ) -> None:
        """Render a Jinja2 template file and write to target location.

        Args:
            template_file: Source .j2 template file
            target_file: Target file path (without .j2 extension)
            context: Template context dictionary
        """
        try:
            # Read template content
            template_content = template_file.read_text(encoding='utf-8')

            # Create Jinja2 template
            template = self.jinja_env.from_string(template_content)

            # Render with context containing WorkflowRun data
            rendered_content = template.render(context)

            # Write rendered content
            target_file.write_text(rendered_content, encoding='utf-8')

            # Copy file permissions from template
            template_stat = template_file.stat()
            target_file.chmod(template_stat.st_mode)

            self.logger.debug(
                'Rendered template %s to %s', template_file.name, target_file
            )

        except (OSError, UnicodeDecodeError, jinja2.TemplateError) as exc:
            raise RuntimeError(
                f'Failed to render template {template_file.name}: {exc}'
            ) from exc

    async def _execute_claude_action(
        self, action: models.WorkflowAction, context: dict[str, typing.Any]
    ) -> typing.Any:
        """Execute a claude workflow action (AI-powered transformation)."""

        if not action.prompt_file:
            raise ValueError(
                f'Claude action {action.name} requires prompt_file'
            )

        workflow_run = context['workflow_run']

        if not workflow_run.working_directory:
            raise RuntimeError(
                f'Claude action {action.name} requires cloned repository '
                f'(working_directory)'
            )

        # Get the prompt file path (relative to workflow directory)
        prompt_file_path = workflow_run.workflow.path / action.prompt_file

        if not prompt_file_path.exists():
            raise FileNotFoundError(
                f'Prompt file not found for action {action.name}: '
                f'{prompt_file_path}'
            )

        # Read and potentially render prompt content
        try:
            if prompt_file_path.suffix == '.j2':
                # Render Jinja2 template
                template_content = prompt_file_path.read_text(encoding='utf-8')
                template = self.jinja_env.from_string(template_content)
                prompt_content = template.render(context)
                self.logger.debug(
                    'Rendered Jinja2 prompt template for action %s',
                    action.name,
                )
            else:
                # Read plain text prompt
                prompt_content = prompt_file_path.read_text(encoding='utf-8')
                self.logger.debug(
                    'Loaded plain text prompt for action %s', action.name
                )

        except (OSError, UnicodeDecodeError) as exc:
            raise RuntimeError(
                f'Failed to read prompt file for action {action.name}: {exc}'
            ) from exc

        # Get Claude Code configuration
        if not self.claude_code:
            raise RuntimeError(
                f'Claude action {action.name} requires Claude Code config'
            )

        # Execute Claude Code with configured timeout and retries
        timeout = action.timeout or 600  # Default 10 minutes
        max_retries = action.max_retries or 3  # Default 3 attempts

        self.logger.debug(
            'Executing Claude Code action %s (timeout: %ds, max_retries: %d)',
            action.name,
            timeout,
            max_retries,
        )

        result = await self.claude_code.execute_prompt(
            prompt_content=prompt_content,
            timeout_seconds=timeout,
            max_retries=max_retries,
        )

        # Check if Claude Code made any changes and commit them if needed
        from . import git

        try:
            changed_files = await git.get_git_status(
                workflow_run.working_directory
            )
            if changed_files:
                self.logger.debug(
                    'Claude action %s modified %d files: %s',
                    action.name,
                    len(changed_files),
                    ', '.join(changed_files),
                )

                # Stage all changed files
                await git.add_files(
                    workflow_run.working_directory, changed_files
                )

                # Create commit message with proper formatting
                commit_message = f'imbi-automations: {action.name}'
                if len(changed_files) == 1:
                    commit_message += f'\n\nModified: {changed_files[0]}'
                else:
                    commit_message += '\n\nModified files:\n'
                    commit_message += '\n'.join(
                        f'- {f}' for f in changed_files
                    )

                # Add ci skip if configured
                if workflow_run.workflow.configuration.ci_skip_checks:
                    commit_message += '\n\n[ci skip]'

                commit_message += (
                    '\n\nAuthored-By: Imbi Automations <noreply@aweber.com>'
                )

                # Commit the changes
                commit_sha = await git.commit_changes(
                    working_directory=workflow_run.working_directory,
                    message=commit_message,
                    author_name='Imbi Automations',
                    author_email='noreply@aweber.com',
                )

                self.logger.debug(
                    'Claude action %s committed changes: %s',
                    action.name,
                    commit_sha[:8] if commit_sha else 'unknown',
                )

                # Add commit info to result
                result['committed'] = True
                result['commit_sha'] = commit_sha
                result['changed_files'] = changed_files
            else:
                result['committed'] = False

        except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
            self.logger.warning(
                'Failed to commit changes for Claude action %s: %s',
                action.name,
                exc,
            )
            result['committed'] = False
            result['commit_error'] = str(exc)

        # Store result for future template references
        self.action_results[action.name] = {'result': result}
        context['actions'] = self.action_results

        self.logger.debug(
            'Claude Code action %s completed: status=%s, attempts=%d, '
            'time=%.2fs',
            action.name,
            result['status'],
            result['attempts'],
            result['execution_time'],
        )

        return result

    async def _execute_shell_action(
        self, action: models.WorkflowAction, context: dict[str, typing.Any]
    ) -> typing.Any:
        """Execute a shell workflow action (run shell commands)."""
        import subprocess

        from . import git

        if not action.command:
            raise ValueError(f'Shell action {action.name} requires command')

        workflow_run = context['workflow_run']

        if not workflow_run.working_directory:
            raise RuntimeError(
                f'Shell action {action.name} requires cloned repository '
                f'(working_directory)'
            )

        # Render the command as a Jinja2 template if it contains templates
        command = action.command
        if '{{' in command:
            self.logger.debug(
                'Rendering shell command template for action %s', action.name
            )
            template = self.jinja_env.from_string(command)
            command = template.render(context)
            self.logger.debug('Rendered command: %s', command)

        self.logger.debug(
            'Executing shell command for action %s: %s', action.name, command
        )

        try:
            # Execute the shell command in the working directory
            result = subprocess.run(  # noqa: ASYNC221, S602
                command,
                shell=True,
                cwd=workflow_run.working_directory,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                check=False,  # Don't raise exception on non-zero exit
            )

            # Store the result
            shell_result = {
                'command': command,
                'returncode': result.returncode,
                'stdout': result.stdout.strip() if result.stdout else '',
                'stderr': result.stderr.strip() if result.stderr else '',
            }

            # Log output for debugging
            if result.stdout:
                self.logger.debug('Shell stdout: %s', result.stdout.strip())
            if result.stderr:
                if result.returncode == 0:
                    self.logger.debug(
                        'Shell command stderr: %s', result.stderr.strip()
                    )
                else:
                    self.logger.warning(
                        'Shell command stderr: %s', result.stderr.strip()
                    )

            if result.returncode != 0:
                self.logger.warning(
                    'Shell command failed with exit code %d: %s',
                    result.returncode,
                    command,
                )
            else:
                self.logger.debug(
                    'Shell command completed successfully: %s', command
                )

            # Check for git changes and commit them if any exist
            try:
                changed_files = await git.get_git_status(
                    workflow_run.working_directory
                )
                if changed_files:
                    self.logger.debug(
                        'Shell action %s modified %d files: %s',
                        action.name,
                        len(changed_files),
                        ', '.join(changed_files),
                    )

                    # Stage all changed files
                    await git.add_files(
                        workflow_run.working_directory, changed_files
                    )

                    # Create commit message with proper formatting
                    commit_message = f'imbi-automations: {action.name}'

                    if len(changed_files) == 1:
                        commit_message += f'\n\nModified: {changed_files[0]}'
                    else:
                        commit_message += '\n\nModified files:\n'
                        commit_message += '\n'.join(
                            f'- {f}' for f in changed_files
                        )

                    # Add ci skip if configured
                    if workflow_run.workflow.configuration.ci_skip_checks:
                        commit_message += '\n\n[ci skip]'

                    commit_message += (
                        '\n\nAuthored-By: Imbi Automations '
                        '<noreply@aweber.com>'
                    )

                    # Commit the changes
                    commit_sha = await git.commit_changes(
                        working_directory=workflow_run.working_directory,
                        message=commit_message,
                        author_name='Imbi Automations',
                        author_email='noreply@aweber.com',
                    )

                    self.logger.debug(
                        'Shell action %s committed changes: %s',
                        action.name,
                        commit_sha[:8] if commit_sha else 'unknown',
                    )

                    # Add commit info to result
                    shell_result['committed'] = True
                    shell_result['commit_sha'] = commit_sha
                    shell_result['changed_files'] = changed_files
                else:
                    self.logger.debug(
                        'Shell action %s made no git changes', action.name
                    )
                    shell_result['committed'] = False

            except (OSError, subprocess.CalledProcessError) as exc:
                self.logger.warning(
                    'Failed to commit changes for shell action %s: %s',
                    action.name,
                    exc,
                )
                shell_result['committed'] = False
                shell_result['commit_error'] = str(exc)

            # Store result for future template references
            self.action_results[action.name] = {'result': shell_result}
            context['actions'] = self.action_results

            return shell_result

        except subprocess.TimeoutExpired as exc:
            error_msg = f'Shell command timed out after 300 seconds: {command}'
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from exc
        except (OSError, subprocess.CalledProcessError) as exc:
            error_msg = f'Failed to execute shell command {command}: {exc}'
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from exc

    async def _execute_ai_editor_action(
        self, action: models.WorkflowAction, context: dict[str, typing.Any]
    ) -> typing.Any:
        """Execute an AI Editor workflow action (fast file transformations)."""

        if not action.prompt_file:
            raise ValueError(
                f'AI Editor action {action.name} requires prompt_file'
            )

        if not action.target_file:
            raise ValueError(
                f'AI Editor action {action.name} requires target_file'
            )

        workflow_run = context['workflow_run']

        if not workflow_run.working_directory:
            raise RuntimeError(
                f'AI Editor action {action.name} requires cloned repository '
                f'(working_directory)'
            )

        # Get the prompt file path (relative to workflow directory)
        prompt_file_path = workflow_run.workflow.path / action.prompt_file

        if not prompt_file_path.exists():
            raise FileNotFoundError(
                f'Prompt file not found for action {action.name}: '
                f'{prompt_file_path}'
            )

        # Read and potentially render prompt content
        try:
            if prompt_file_path.suffix == '.j2':
                # Render Jinja2 template
                template_content = prompt_file_path.read_text(encoding='utf-8')
                template = self.jinja_env.from_string(template_content)
                prompt_content = template.render(context)
                self.logger.debug(
                    'Rendered Jinja2 prompt template for AI Editor action %s',
                    action.name,
                )
            else:
                # Read plain text prompt
                prompt_content = prompt_file_path.read_text(encoding='utf-8')
                self.logger.debug(
                    'Loaded plain text prompt for AI Editor action %s',
                    action.name,
                )

        except (OSError, UnicodeDecodeError) as exc:
            raise RuntimeError(
                f'Failed to read prompt file for action {action.name}: {exc}'
            ) from exc

        # Get Anthropic API key from configuration
        if not self._anthropic_config or not self._anthropic_config.api_key:
            raise RuntimeError(
                f'AI Editor action {action.name} requires Anthropic API key'
            )

        # Initialize AI Editor
        from . import ai_editor

        editor = ai_editor.AIEditor(
            api_key=self._anthropic_config.api_key.get_secret_value(),
            working_directory=workflow_run.working_directory,
        )

        # Execute AI Editor with configured timeout and retries
        timeout = action.timeout or 300  # Default 5 minutes
        max_retries = action.max_retries or 3  # Default 3 attempts

        self.logger.debug(
            'Executing AI Editor action %s on %s (timeout: %ds, retries: %d)',
            action.name,
            action.target_file,
            timeout,
            max_retries,
        )

        result = await editor.execute_prompt(
            prompt_content=prompt_content,
            target_file=action.target_file,
            timeout_seconds=timeout,
            max_retries=max_retries,
        )

        # Check if AI Editor made any changes and commit them if needed
        from . import git

        try:
            changed_files = await git.get_git_status(
                workflow_run.working_directory
            )
            if changed_files and result.get('changed'):
                self.logger.debug(
                    'AI Editor action %s modified %d files: %s',
                    action.name,
                    len(changed_files),
                    ', '.join(changed_files),
                )

                # Stage all changed files
                await git.add_files(
                    workflow_run.working_directory, changed_files
                )

                # Create commit message with proper formatting
                commit_message = f'imbi-automations: {action.name}'
                if len(changed_files) == 1:
                    commit_message += f'\n\nModified: {changed_files[0]}'
                else:
                    commit_message += '\n\nModified files:\n'
                    commit_message += '\n'.join(
                        f'- {f}' for f in changed_files
                    )

                # Add ci skip if configured
                if workflow_run.workflow.configuration.ci_skip_checks:
                    commit_message += '\n\n[ci skip]'

                commit_message += (
                    '\n\nAuthored-By: Imbi Automations <noreply@aweber.com>'
                )

                # Commit the changes
                commit_sha = await git.commit_changes(
                    working_directory=workflow_run.working_directory,
                    message=commit_message,
                    author_name='Imbi Automations',
                    author_email='noreply@aweber.com',
                )

                self.logger.debug(
                    'AI Editor action %s committed changes: %s',
                    action.name,
                    commit_sha[:8] if commit_sha else 'unknown',
                )

                # Add commit info to result
                result['committed'] = True
                result['commit_sha'] = commit_sha
                result['changed_files'] = changed_files
            else:
                result['committed'] = False

        except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
            self.logger.warning(
                'Failed to commit changes for AI Editor action %s: %s',
                action.name,
                exc,
            )
            result['committed'] = False
            result['commit_error'] = str(exc)

        # Store result for future template references
        self.action_results[action.name] = {'result': result}
        context['actions'] = self.action_results

        self.logger.debug(
            'AI Editor action %s completed: status=%s, attempts=%d',
            action.name,
            result['status'],
            result['attempts'],
        )

        return result

    async def _execute_git_revert_action(
        self, action: models.WorkflowAction, context: dict[str, typing.Any]
    ) -> dict[str, typing.Any]:
        """Execute a git-revert workflow action.

        Args:
            action: Git revert action to execute
            context: Workflow execution context

        Returns:
            Dictionary with execution results

        """
        if not action.source:
            raise ValueError(
                f'Git revert action {action.name} missing required source file'
            )

        if not action.keyword:
            raise ValueError(
                f'Git revert action {action.name} missing required keyword'
            )

        # Get working directory from context
        workflow_run = context.get('workflow_run')
        if not workflow_run or not workflow_run.working_directory:
            raise RuntimeError(
                f'Git revert action {action.name} requires working directory'
            )

        strategy = action.strategy or 'before_last_match'

        result = {
            'action': action.name,
            'source': action.source,
            'keyword': action.keyword,
            'strategy': strategy,
            'reverted': False,
            'committed': False,
        }

        try:
            # Find commit before keyword match
            before_commit = await git.find_commit_before_keyword(
                workflow_run.working_directory, action.keyword, strategy
            )

            if not before_commit:
                self.logger.warning(
                    'Git revert action %s: no commit found with keyword "%s"',
                    action.name,
                    action.keyword,
                )
                result['error'] = (
                    f'No commit found with keyword "{action.keyword}"'
                )
                return result

            # Get file content at that commit
            file_content = await git.get_file_at_commit(
                workflow_run.working_directory, action.source, before_commit
            )

            if file_content is None:
                self.logger.warning(
                    'Git revert action %s: file %s missing at commit %s',
                    action.name,
                    action.source,
                    before_commit[:8],
                )
                result['error'] = (
                    f'File {action.source} not found at {before_commit[:8]}'
                )
                return result

            # Write reverted content to target file outside git working directory
            if action.target_path:
                # Save to parent directory (outside git repo) to avoid committing
                target_file = action.target_path
                file_path = workflow_run.working_directory.parent / target_file
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(file_content, encoding='utf-8')
                self.logger.debug(
                    'Git revert action %s: saved content to %s (outside git repo)',
                    action.name,
                    file_path,
                )
            else:
                # Original behavior: overwrite source file in git repo
                file_path = workflow_run.working_directory / action.source
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(file_content, encoding='utf-8')

            self.logger.debug(
                'Git revert action %s: reverted %s to commit %s (%d bytes)',
                action.name,
                action.source,
                before_commit[:8],
                len(file_content),
            )

            result['reverted'] = True
            result['commit_hash'] = before_commit
            result['content_length'] = len(file_content)
            result['content'] = (
                file_content  # Make content available for templates
            )

            if action.target_path:
                # When using target_path, file is saved outside git repo (no commit)
                self.logger.debug(
                    'Git revert action %s: extracted content for template use (not committed)',
                    action.name,
                )
            else:
                # When overwriting source file, commit the changes
                changed_files = await git.get_git_status(
                    workflow_run.working_directory
                )

                if changed_files:
                    await git.add_files(
                        workflow_run.working_directory, [action.source]
                    )

                    commit_message = (
                        f'Apply git revert action: {action.name}\n\n'
                        f'Reverted {action.source} before: {action.keyword}\n'
                        f'Target commit: {before_commit[:8]}\n'
                        f'Strategy: {strategy}'
                    )

                    commit_message += '\n\nAuthored-By: Imbi Automations <noreply@aweber.com>'

                    commit_sha = await git.commit_changes(
                        working_directory=workflow_run.working_directory,
                        message=commit_message,
                        author_name='Imbi Automations',
                        author_email='noreply@aweber.com',
                    )

                    self.logger.debug(
                        'Git revert action %s committed changes: %s',
                        action.name,
                        commit_sha[:8] if commit_sha else 'unknown',
                    )

                    result['committed'] = True
                    result['commit_sha'] = commit_sha
                    result['changed_files'] = changed_files
                else:
                    self.logger.debug(
                        'Git revert action %s: no changes after revert',
                        action.name,
                    )

        except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
            self.logger.error(
                'Git revert action %s failed: %s', action.name, exc
            )
            result['error'] = str(exc)

        # Store result for future template references
        self.action_results[action.name] = {'result': result}
        context['actions'] = self.action_results

        self.logger.debug(
            'Git revert action %s completed: reverted=%s, committed=%s',
            action.name,
            result['reverted'],
            result['committed'],
        )

        return result

    async def _execute_git_extract_action(
        self, action: models.WorkflowAction, context: dict[str, typing.Any]
    ) -> dict[str, typing.Any]:
        """Execute a git-extract workflow action (extracts content without committing).

        Args:
            action: Git extract action to execute
            context: Workflow execution context

        Returns:
            Dictionary with execution results

        """
        if not action.source:
            raise ValueError(
                f'Git extract action {action.name} missing required source file'
            )

        if not action.keyword:
            raise ValueError(
                f'Git extract action {action.name} missing required keyword'
            )

        # Get working directory from context
        workflow_run = context.get('workflow_run')
        if not workflow_run or not workflow_run.working_directory:
            raise RuntimeError(
                f'Git extract action {action.name} requires working directory'
            )

        strategy = action.strategy or 'before_last_match'
        target_path = action.target_path or f'{action.source}.extracted'

        result = {
            'action': action.name,
            'source': action.source,
            'keyword': action.keyword,
            'strategy': strategy,
            'target_path': target_path,
            'extracted': False,
            'committed': False,  # git-extract never commits
        }

        try:
            # Find commit before keyword match
            before_commit = await git.find_commit_before_keyword(
                workflow_run.working_directory, action.keyword, strategy
            )

            if not before_commit:
                self.logger.warning(
                    'Git extract action %s: no commit found with keyword "%s"',
                    action.name,
                    action.keyword,
                )
                result['error'] = (
                    f'No commit found with keyword "{action.keyword}"'
                )
                return result

            # Get file content at that commit
            file_content = await git.get_file_at_commit(
                workflow_run.working_directory, action.source, before_commit
            )

            if file_content is None:
                self.logger.warning(
                    'Git extract action %s: file %s missing at commit %s',
                    action.name,
                    action.source,
                    before_commit[:8],
                )
                result['error'] = (
                    f'File {action.source} not found at {before_commit[:8]}'
                )
                return result

            # Save extracted content outside git working directory
            file_path = workflow_run.working_directory.parent / target_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(file_content, encoding='utf-8')

            self.logger.debug(
                'Git extract action %s: extracted %s from commit %s (%d bytes) → %s',
                action.name,
                action.source,
                before_commit[:8],
                len(file_content),
                target_path,
            )

            result['extracted'] = True
            result['commit_hash'] = before_commit
            result['content_length'] = len(file_content)
            result['content'] = (
                file_content  # Make content available for templates
            )

        except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
            self.logger.error(
                'Git extract action %s failed: %s', action.name, exc
            )
            result['error'] = str(exc)

        # Store result for future template references
        self.action_results[action.name] = {'result': result}
        context['actions'] = self.action_results

        self.logger.debug(
            'Git extract action %s completed: extracted=%s (working file only)',
            action.name,
            result['extracted'],
        )

        return result

    async def _execute_docker_extract_action(
        self, action: models.WorkflowAction, context: dict[str, typing.Any]
    ) -> dict[str, typing.Any]:
        """Execute a docker-extract workflow action.

        Args:
            action: Docker extract action to execute
            context: Workflow execution context

        Returns:
            Dictionary with execution results

        """
        if not action.source_path:
            raise ValueError(
                f'Docker extract action {action.name} missing source_path'
            )

        # Get working directory from context
        workflow_run = context.get('workflow_run')
        if not workflow_run or not workflow_run.working_directory:
            raise RuntimeError(
                f'Docker extract action {action.name} needs working directory'
            )

        dockerfile_path = action.dockerfile_path or 'Dockerfile'
        target_path = (
            action.target_path or pathlib.Path(action.source_path).name
        )

        result = {
            'action': action.name,
            'dockerfile_path': dockerfile_path,
            'source_path': action.source_path,
            'target_path': target_path,
            'extracted': False,
            'committed': False,
        }

        try:
            # Import docker operations
            from imbi_automations import docker

            # Extract Docker image from Dockerfile
            dockerfile_full_path = (
                workflow_run.working_directory / dockerfile_path
            )
            image_name = await docker.extract_docker_image_from_dockerfile(
                dockerfile_full_path
            )

            if not image_name:
                self.logger.warning(
                    'Docker extract action %s: no image found in %s',
                    action.name,
                    dockerfile_path,
                )
                result['error'] = (
                    f'Could not extract image from {dockerfile_path}'
                )
                return result

            # Extract file content from Docker image
            file_content = await docker.extract_file_from_docker_image(
                image_name, action.source_path
            )

            if file_content is None:
                self.logger.warning(
                    'Docker extract action %s: file %s not found in image %s',
                    action.name,
                    action.source_path,
                    image_name,
                )
                result['error'] = (
                    f'File {action.source_path} not found in {image_name}'
                )
                return result

            # Write extracted content outside git working directory to avoid committing
            target_file_path = (
                workflow_run.working_directory.parent / target_path
            )
            target_file_path.parent.mkdir(parents=True, exist_ok=True)
            target_file_path.write_text(file_content, encoding='utf-8')

            self.logger.debug(
                'Docker extract action %s: %s from %s (%d bytes) → %s',
                action.name,
                action.source_path,
                image_name,
                len(file_content),
                target_path,
            )

            result['extracted'] = True
            result['image_name'] = image_name
            result['content'] = file_content
            result['content_length'] = len(file_content)

            # Parse constraints if it looks like a constraints file
            if 'constraints' in action.source_path.lower():
                packages = docker.parse_constraints_file(file_content)
                result['packages'] = packages
                result['package_count'] = len(packages)

            # Note: Docker extract saves working files outside git repo (not committed)
            # The extracted content is available for templates via result['content']
            self.logger.debug(
                'Docker extract action %s: saved working file outside git repo (not committed)',
                action.name,
            )

        except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
            self.logger.error(
                'Docker extract action %s failed: %s', action.name, exc
            )
            result['error'] = str(exc)

        # Store result for future template references
        self.action_results[action.name] = {'result': result}
        context['actions'] = self.action_results

        self.logger.debug(
            'Docker extract action %s completed: extracted=%s, committed=%s',
            action.name,
            result['extracted'],
            result['committed'],
        )

        return result

    async def _execute_add_trailing_whitespace_action(
        self, action: models.WorkflowAction, context: dict[str, typing.Any]
    ) -> dict[str, typing.Any]:
        """Execute an add-trailing-whitespace workflow action.

        Args:
            action: Add trailing whitespace action to execute
            context: Workflow execution context

        Returns:
            Dictionary with execution results

        """
        if not action.source:
            raise ValueError(
                f'Add trailing whitespace action {action.name} missing source file'
            )

        # Get working directory from context
        workflow_run = context.get('workflow_run')
        if not workflow_run or not workflow_run.working_directory:
            raise RuntimeError(
                f'Add trailing whitespace action {action.name} needs working directory'
            )

        result = {
            'action': action.name,
            'source': action.source,
            'modified': False,
            'committed': False,
        }

        try:
            file_path = workflow_run.working_directory / action.source

            if not file_path.exists():
                self.logger.warning(
                    'Add trailing whitespace action %s: file %s does not exist',
                    action.name,
                    action.source,
                )
                result['error'] = f'File {action.source} does not exist'
                return result

            # Read current content
            try:
                content = file_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                # Try different encoding
                content = file_path.read_text(encoding='latin-1')

            # Check if file already ends with newline
            if content.endswith('\n'):
                self.logger.debug(
                    'Add trailing whitespace action %s: file %s already has trailing newline',
                    action.name,
                    action.source,
                )
                result['modified'] = False
                return result

            # Add trailing newline
            new_content = content + '\n'
            file_path.write_text(new_content, encoding='utf-8')

            self.logger.debug(
                'Add trailing whitespace action %s: added trailing newline to %s',
                action.name,
                action.source,
            )

            result['modified'] = True

            # Check if changes were made and commit
            changed_files = await git.get_git_status(
                workflow_run.working_directory
            )

            if changed_files and action.source in changed_files:
                await git.add_files(
                    workflow_run.working_directory, [action.source]
                )

                commit_message = (
                    f'Apply add trailing whitespace action: {action.name}\n\n'
                    f'Added trailing newline to {action.source}'
                )

                commit_message += (
                    '\n\nAuthored-By: Imbi Automations <noreply@aweber.com>'
                )

                commit_sha = await git.commit_changes(
                    working_directory=workflow_run.working_directory,
                    message=commit_message,
                    author_name='Imbi Automations',
                    author_email='noreply@aweber.com',
                )

                self.logger.debug(
                    'Add trailing whitespace action %s committed changes: %s',
                    action.name,
                    commit_sha[:8] if commit_sha else 'unknown',
                )

                result['committed'] = True
                result['commit_sha'] = commit_sha
                result['changed_files'] = [action.source]

        except (OSError, UnicodeDecodeError) as exc:
            self.logger.error(
                'Add trailing whitespace action %s failed: %s',
                action.name,
                exc,
            )
            result['error'] = str(exc)

        # Store result for future template references
        self.action_results[action.name] = {'result': result}
        context['actions'] = self.action_results

        self.logger.debug(
            'Add trailing whitespace action %s completed: modified=%s, committed=%s',
            action.name,
            result['modified'],
            result['committed'],
        )

        return result

    async def _evaluate_condition(
        self,
        condition: models.WorkflowCondition,
        working_directory: pathlib.Path,
    ) -> bool:
        """Evaluate a single workflow condition.

        Args:
            condition: Condition to evaluate
            working_directory: Repository working directory for file checks

        Returns:
            True if condition is met, False otherwise
        """
        if condition.file_exists:
            file_path = working_directory / condition.file_exists
            result = file_path.exists()
            self.logger.debug(
                'Condition file_exists "%s": %s', condition.file_exists, result
            )
            return result

        if condition.file_not_exists:
            file_path = working_directory / condition.file_not_exists
            result = not file_path.exists()
            self.logger.debug(
                'Condition file_not_exists "%s": %s',
                condition.file_not_exists,
                result,
            )
            return result

        if condition.file_contains:
            # Use condition.file if specified, fallback to file_contains
            file_path = working_directory / (
                condition.file or condition.file_contains
            )

            try:
                if file_path.exists() and file_path.is_file():
                    content = file_path.read_text(encoding='utf-8')

                    # Try string containment first (faster)
                    if condition.file_contains in content:
                        self.logger.debug(
                            'Condition file_contains string "%s" in "%s": %s',
                            condition.file_contains,
                            condition.file or condition.file_contains,
                            'True',
                        )
                        return True

                    # If string search fails, try regex
                    try:
                        if re.search(condition.file_contains, content):
                            self.logger.debug(
                                'file_contains regex "%s" in "%s": %s',
                                condition.file_contains,
                                condition.file or condition.file_contains,
                                'True',
                            )
                            return True
                    except re.error:
                        # Regex is invalid, string search already failed
                        pass

                    self.logger.debug(
                        'Condition file_contains "%s" in "%s": False',
                        condition.file_contains,
                        condition.file or condition.file_contains,
                    )
                    return False
                else:
                    self.logger.debug(
                        'Condition file_contains "%s" - file "%s" not found',
                        condition.file_contains,
                        condition.file or condition.file_contains,
                    )
                    return False
            except (OSError, UnicodeDecodeError) as exc:
                self.logger.debug(
                    'Condition file_contains "%s" - error reading "%s": %s',
                    condition.file_contains,
                    condition.file or condition.file_contains,
                    exc,
                )
                return False

        # If no conditions are specified, consider it as True
        self.logger.debug('Empty condition evaluated as True')
        return True

    async def _evaluate_conditions(self, run: models.WorkflowRun) -> bool:
        """Evaluate all workflow conditions.

        Args:
            run: Workflow run containing configuration and working directory

        Returns:
            True if all conditions are met according to condition_type logic
        """
        if not run.workflow.configuration.conditions:
            self.logger.debug('No conditions specified, proceeding')
            return True

        if not run.working_directory:
            self.logger.warning(
                'Cannot evaluate conditions without working directory '
                '(clone_repository=true required)'
            )
            return True  # Allow workflow to proceed if no working directory

        self.logger.debug(
            'Evaluating %d conditions with %s logic',
            len(run.workflow.configuration.conditions),
            run.workflow.configuration.condition_type,
        )

        condition_results = []
        for i, condition in enumerate(run.workflow.configuration.conditions):
            result = await self._evaluate_condition(
                condition, run.working_directory
            )
            condition_results.append(result)
            self.logger.debug('Condition %d result: %s', i + 1, result)

        # Apply condition_type logic
        if (
            run.workflow.configuration.condition_type
            == models.WorkflowConditionType.all
        ):
            overall_result = all(condition_results)
            self.logger.debug('All conditions must pass: %s', overall_result)
        else:  # any
            overall_result = any(condition_results)
            self.logger.debug('Any condition must pass: %s', overall_result)

        return overall_result

    def _evaluate_action_condition(
        self, condition: str, context: dict[str, typing.Any]
    ) -> bool:
        """Evaluate an action condition against the current context.

        Args:
            condition: Condition string to evaluate
                (e.g., "actions['failing-sonarqube'].result == 'failure'")
            context: Template context containing action results

        Returns:
            True if condition is met, False otherwise

        """
        try:
            # Create a safe evaluation environment
            safe_globals = {
                '__builtins__': {},
                'actions': context.get('actions', {}),
            }

            # Evaluate the condition
            result = eval(condition, safe_globals)  # noqa: S307
            self.logger.debug(
                'Action condition "%s" evaluated to: %s', condition, result
            )
            return bool(result)

        except (ValueError, KeyError, AttributeError) as exc:
            self.logger.error(
                'Failed to evaluate action condition "%s": %s', condition, exc
            )
            return False

    async def _evaluate_remote_condition(
        self,
        condition: models.WorkflowCondition,
        github_repository: models.GitHubRepository | None,
    ) -> bool:
        """Evaluate a remote condition using GitHub API before cloning.

        Args:
            condition: Workflow condition to evaluate
            github_repository: GitHub repository information

        Returns:
            True if condition is met, False otherwise
        """
        if not github_repository:
            self.logger.debug(
                'No GitHub repository available for remote conditions'
            )
            return True

        # Extract owner and repo from repository
        owner = github_repository.owner.login
        repo = github_repository.name

        # Check remote_file_exists condition
        if condition.remote_file_exists:
            try:
                result = await self._check_remote_file_exists(
                    owner, repo, condition.remote_file_exists
                )
                self.logger.debug(
                    'Remote condition remote_file_exists "%s": %s',
                    condition.remote_file_exists,
                    result,
                )
                return result
            except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                # Don't warn about 404s, they're expected
                if 'Not Found (HTTP 404)' not in str(exc):
                    self.logger.warning(
                        'Failed to check remote_file_exists "%s": %s',
                        condition.remote_file_exists,
                        exc,
                    )
                return True  # Graceful degradation

        # Check remote_file_not_exists condition
        if condition.remote_file_not_exists:
            try:
                exists = await self._check_remote_file_exists(
                    owner, repo, condition.remote_file_not_exists
                )
                result = not exists
                self.logger.debug(
                    'Remote condition remote_file_not_exists "%s": %s',
                    condition.remote_file_not_exists,
                    result,
                )
                return result
            except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                # Don't warn about 404s, they're expected
                if 'Not Found (HTTP 404)' not in str(exc):
                    self.logger.warning(
                        'Failed to check remote_file_not_exists "%s": %s',
                        condition.remote_file_not_exists,
                        exc,
                    )
                return True  # Graceful degradation

        # Check remote_file_contains condition
        if condition.remote_file_contains:
            file_path = condition.remote_file or condition.remote_file_contains
            try:
                content = await self._get_remote_file_content(
                    owner, repo, file_path
                )
                if content is None:
                    self.logger.debug(
                        'Remote file "%s" not found for remote_file_contains',
                        file_path,
                    )
                    return False

                # Use same string/regex logic as local file_contains
                if condition.remote_file_contains in content:
                    self.logger.debug(
                        'Remote file_contains string "%s" in "%s": True',
                        condition.remote_file_contains,
                        file_path,
                    )
                    return True

                # Try regex if string search fails
                try:
                    if re.search(condition.remote_file_contains, content):
                        self.logger.debug(
                            'Remote file_contains regex "%s" in "%s": True',
                            condition.remote_file_contains,
                            file_path,
                        )
                        return True
                except re.error:
                    # Invalid regex, string search already failed
                    pass

                self.logger.debug(
                    'Remote file_contains "%s" in "%s": False',
                    condition.remote_file_contains,
                    file_path,
                )
                return False

            except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                # Don't warn about 404s, they're expected
                if 'Not Found (HTTP 404)' not in str(exc):
                    self.logger.warning(
                        'Failed to check remote_file_contains "%s": %s',
                        condition.remote_file_contains,
                        file_path,
                        exc,
                    )
                return True  # Graceful degradation

        # If no remote conditions are specified, return True
        return True

    async def _check_remote_file_exists(
        self, owner: str, repo: str, file_path: str
    ) -> bool:
        """Check if a file exists in the remote repository using GitHub API.

        Args:
            owner: Repository owner
            repo: Repository name
            file_path: Path to check

        Returns:
            True if file exists, False otherwise
        """
        try:
            # Use gh CLI to check file existence
            cmd = [
                'gh',
                'api',
                f'repos/{owner}/{repo}/contents/{file_path}',
                '--silent',
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            await process.wait()

            # File exists if command succeeds (exit code 0)
            return process.returncode == 0

        except (RuntimeError, httpx.HTTPError, ValueError) as exc:
            self.logger.debug(
                'Error checking remote file existence for %s: %s',
                file_path,
                exc,
            )
            raise

    async def _get_remote_file_content(
        self, owner: str, repo: str, file_path: str
    ) -> str | None:
        """Get content of a file from the remote repository using GitHub API.

        Args:
            owner: Repository owner
            repo: Repository name
            file_path: Path to the file

        Returns:
            File content as string, or None if file doesn't exist
        """
        try:
            # Use gh CLI to get file content
            cmd = [
                'gh',
                'api',
                f'repos/{owner}/{repo}/contents/{file_path}',
                '--jq',
                '.content',
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode()
                # Check if it's a 404 Not Found error
                is_404 = (
                    'Not Found (HTTP 404)' in error_msg
                    or process.returncode == 22
                )
                if is_404:
                    return None
                raise RuntimeError(
                    f'gh CLI failed with exit code {process.returncode}: '
                    f'{error_msg}'
                )

            # Decode base64 content
            import base64

            encoded_content = stdout.decode().strip()
            if not encoded_content:
                return ''

            # GitHub API returns base64-encoded content
            try:
                content = base64.b64decode(encoded_content).decode('utf-8')
                return content
            except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                raise RuntimeError(
                    f'Failed to decode file content: {exc}'
                ) from exc

        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            self.logger.debug(
                'Error getting remote file content for %s: %s', file_path, exc
            )
            raise

    async def _evaluate_remote_conditions(
        self, run: models.WorkflowRun
    ) -> bool:
        """Evaluate all remote workflow conditions before cloning.

        Args:
            run: Workflow run containing configuration

        Returns:
            True if all remote conditions are met according to condition_type
        """
        if not run.workflow.configuration.conditions:
            self.logger.debug('No conditions specified, proceeding')
            return True

        # Filter for remote conditions only
        remote_conditions = []
        for condition in run.workflow.configuration.conditions:
            if any(
                [
                    condition.remote_file_exists,
                    condition.remote_file_not_exists,
                    condition.remote_file_contains,
                ]
            ):
                remote_conditions.append(condition)

        if not remote_conditions:
            self.logger.debug(
                'No remote conditions specified, proceeding with workflow'
            )
            return True

        self.logger.debug(
            'Evaluating %d remote conditions with %s logic',
            len(remote_conditions),
            run.workflow.configuration.condition_type,
        )

        condition_results = []
        for condition in remote_conditions:
            try:
                result = await self._evaluate_remote_condition(
                    condition, run.github_repository
                )
                condition_results.append(result)
            except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                self.logger.warning(
                    'Remote condition evaluation failed: %s, treating as True',
                    exc,
                )
                condition_results.append(True)  # Graceful degradation

        # Apply condition type logic
        condition_type = run.workflow.configuration.condition_type
        if condition_type == models.WorkflowConditionType.all:
            final_result = all(condition_results)
        else:  # any
            final_result = any(condition_results)

        self.logger.debug(
            'Remote conditions evaluation result: %s (passed: %d/%d)',
            final_result,
            sum(condition_results),
            len(condition_results),
        )

        return final_result

    async def _evaluate_action_conditions(
        self, action: models.WorkflowAction, context: dict[str, typing.Any]
    ) -> bool:
        """Evaluate action-level rich conditions.

        Args:
            action: Workflow action with conditions
            context: Template context containing workflow run data

        Returns:
            True if all conditions are met according to condition_type logic
        """
        if not action.conditions:
            return True

        workflow_run = context['workflow_run']

        self.logger.debug(
            'Evaluating %d action conditions for %s with %s logic',
            len(action.conditions),
            action.name,
            action.condition_type,
        )

        condition_results = []
        for condition in action.conditions:
            try:
                # Check if it's a remote condition
                if any(
                    [
                        condition.remote_file_exists,
                        condition.remote_file_not_exists,
                        condition.remote_file_contains,
                    ]
                ):
                    result = await self._evaluate_remote_condition(
                        condition, workflow_run.github_repository
                    )
                else:
                    # Local condition - requires working directory
                    if not workflow_run.working_directory:
                        self.logger.warning(
                            'Cannot evaluate local condition for action %s '
                            'without working directory',
                            action.name,
                        )
                        result = True  # Allow action to proceed
                    else:
                        result = await self._evaluate_condition(
                            condition, workflow_run.working_directory
                        )

                condition_results.append(result)

            except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                self.logger.warning(
                    'Action condition evaluation failed for %s: %s',
                    action.name,
                    exc,
                )
                condition_results.append(True)  # Graceful degradation

        # Apply condition type logic
        if action.condition_type == models.WorkflowConditionType.all:
            final_result = all(condition_results)
        else:  # any
            final_result = any(condition_results)

        self.logger.debug(
            'Action conditions for %s: %s (passed: %d/%d)',
            action.name,
            final_result,
            sum(condition_results),
            len(condition_results),
        )

        return final_result

    async def _create_pull_request(
        self, run: models.WorkflowRun, project_info: str
    ) -> None:
        """Create a pull request for workflow changes.

        Args:
            run: Workflow run containing repository and workflow information
            project_info: Project information string for logging

        """
        try:
            if not run.github_repository:
                self.logger.warning(
                    'Cannot create pull request for %s - no GitHub repo',
                    project_info,
                )
                return

            # Get current branch name
            current_branch = await git.get_current_branch(
                run.working_directory
            )

            # Get commit messages for PR description
            commit_messages = await git.get_commit_messages_since_branch(
                run.working_directory, 'main'
            )

            # Build PR description
            pr_title = run.workflow.configuration.name
            pr_description = (
                run.workflow.configuration.description
                or 'Automated workflow execution'
            )

            if commit_messages:
                pr_description += '\n\n## Changes Made:\n'
                for msg in commit_messages:
                    pr_description += f'- {msg}\n'

            pr_description += '\n🤖 Generated by imbi-automations'

            # Create pull request using gh CLI
            command = [
                'gh',
                'pr',
                'create',
                '--title',
                pr_title,
                '--body',
                pr_description,
                '--base',
                'main',
                '--head',
                current_branch,
            ]

            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=run.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode('utf-8') if stdout else ''
            stderr_str = stderr.decode('utf-8') if stderr else ''

            if process.returncode == 0:
                # Extract PR URL from gh output
                pr_url = stdout_str.strip()
                self.logger.info(
                    'Successfully created pull request for project %s: %s',
                    project_info,
                    pr_url,
                )
            else:
                self.logger.error(
                    'Failed to create pull request for project %s: %s',
                    project_info,
                    stderr_str or stdout_str,
                )

        except (TimeoutError, OSError, subprocess.CalledProcessError) as exc:
            self.logger.error(
                'Error creating pull request for project %s: %s',
                project_info,
                exc,
            )
            # Don't re-raise - workflow completes even if PR creation fails

    async def execute(self, run: models.WorkflowRun) -> str:
        """Execute a complete workflow run."""
        # Set logger to workflow directory name for this execution
        self.set_workflow_logger(run.workflow.path)

        project_info = (
            f'{run.imbi_project.name} ({run.imbi_project.project_type})'
            if run.imbi_project
            else 'Unknown Project'
        )
        self.logger.debug(
            'Executing workflow: %s for project %s',
            run.workflow.configuration.name,
            project_info,
        )

        # Clear previous action results
        self.action_results = ActionResults()

        # Evaluate remote conditions before cloning
        if not await self._evaluate_remote_conditions(run):
            self.logger.info(
                'Skipping workflow execution for project %s - '
                'remote conditions not met',
                project_info,
            )
            return 'skipped_remote_conditions'

        # Handle repository cloning if required
        if run.workflow.configuration.clone_repository:
            try:
                await self._setup_repository_clone(run)
            except RuntimeError as exc:
                self.logger.warning(
                    'Skipping workflow execution for project %s - %s',
                    project_info,
                    exc,
                )
                return 'skipped_no_repository'

        # Initialize Claude Code client if config and working directory exist
        if self._claude_code_config and run.working_directory:
            self.claude_code = claude_code.ClaudeCode(
                config=self._claude_code_config,
                working_directory=run.working_directory,
            )
            self.logger.debug(
                'Initialized Claude Code client for workflow execution'
            )

        # Evaluate workflow conditions
        if not await self._evaluate_conditions(run):
            self.logger.info(
                'Skipping workflow execution for project %s - '
                'conditions not met',
                project_info,
            )
            return 'skipped_conditions'

        # Note: Feature branch creation moved to after actions execute
        # Only create branch if there are actual changes to commit

        # Create template context
        context = self._create_template_context(run)

        # Execute each action sequentially
        for action in run.workflow.configuration.actions:
            try:
                # Check legacy string condition if specified
                if action.condition and not self._evaluate_action_condition(
                    action.condition, context
                ):
                    self.logger.debug(
                        'Skipping action %s for project %s - '
                        'string condition not met: %s',
                        action.name,
                        project_info,
                        action.condition,
                    )
                    continue

                # Check rich conditions if specified
                if not await self._evaluate_action_conditions(action, context):
                    self.logger.debug(
                        'Skipping action %s for project %s - '
                        'rich conditions not met',
                        action.name,
                        project_info,
                    )
                    continue

                self.logger.debug(
                    'Executing action: %s for project %s',
                    action.name,
                    project_info,
                )
                await self._execute_action(action, context)
            except (OSError, subprocess.CalledProcessError) as exc:
                self.logger.error(
                    'Action %s failed for project %s: %s',
                    action.name,
                    project_info,
                    exc,
                )
                raise

        # Check if any changes were made during workflow execution
        changes_made = False
        pr_created = False

        if run.working_directory:
            try:
                from . import git

                # Check if any actions created commits during execution
                # Actions like shell, ai-editor, etc. create their own commits
                commits_made = any(
                    result.get('result', {}).get('committed', False)
                    for result in self.action_results._results.values()
                    if isinstance(result.get('result'), dict)
                )

                # Also check for any remaining uncommitted changes
                changed_files = await git.get_git_status(run.working_directory)

                if commits_made or changed_files:
                    changes_made = True
                    if commits_made and not changed_files:
                        self.logger.debug(
                            'Actions created commits for project %s',
                            project_info,
                        )
                    else:
                        self.logger.debug(
                            'Found %d changed files for project %s: %s',
                            len(changed_files),
                            project_info,
                            ', '.join(changed_files[:5]),  # Show first 5 files
                        )

                    # Create feature branch if pull request is requested
                    if run.workflow.configuration.create_pull_request:
                        # Convert workflow name to kebab-case
                        workflow_name = run.workflow.configuration.name
                        kebab_name = workflow_name.lower().replace(' ', '-')
                        branch_name = f'ia-{kebab_name}'

                        # Delete remote branch if it exists to avoid conflicts
                        await git.delete_remote_branch_if_exists(
                            run.working_directory, branch_name
                        )

                        await git.create_branch(
                            run.working_directory, branch_name
                        )
                        self.logger.info(
                            'Created feature branch %s for PR workflow',
                            branch_name,
                        )

                    # Push changes to remote repository
                    if run.workflow.configuration.create_pull_request:
                        # Get current branch name for upstream tracking
                        current_branch = await git.get_current_branch(
                            run.working_directory
                        )
                        await git.push_changes(
                            run.working_directory,
                            branch=current_branch,
                            set_upstream=True,
                        )
                    else:
                        await git.push_changes(run.working_directory)

                    self.logger.debug(
                        'Pushed all workflow changes to remote for project %s',
                        project_info,
                    )

                    # Create pull request if requested
                    if run.workflow.configuration.create_pull_request:
                        await self._create_pull_request(run, project_info)
                        pr_created = True
                else:
                    self.logger.debug(
                        'No changes detected for project %s, skipping git ops',
                        project_info,
                    )

            except (OSError, subprocess.CalledProcessError) as exc:
                self.logger.warning(
                    'Failed to push workflow changes for project %s: %s',
                    project_info,
                    exc,
                )
                # Don't re-raise - workflow completes even if push fails

        # Enhanced completion messaging based on what actually happened
        if changes_made:
            if pr_created:
                self.logger.info(
                    'Workflow completed successfully for project %s - '
                    'changes pushed and pull request created',
                    project_info,
                )
                return 'successful_pr_created'
            else:
                self.logger.info(
                    'Workflow completed successfully for project %s - '
                    'changes pushed to main branch',
                    project_info,
                )
                return 'successful_changes_pushed'
        else:
            self.logger.info(
                'Workflow completed successfully for project %s - '
                'no changes needed',
                project_info,
            )
            return 'successful_no_changes'

    async def _setup_repository_clone(self, run: models.WorkflowRun) -> None:
        """Set up repository cloning for workflows that require it.

        Args:
            run: Workflow run containing repository information

        Raises:
            RuntimeError: If no clonable repository is available

        """
        clone_url = None
        repo_name = 'unknown'

        # Determine which repository to clone (prefer GitHub, fallback GitLab)
        if run.github_repository:
            clone_url = (
                run.github_repository.ssh_url
            )  # Use SSH instead of HTTPS
            repo_name = run.github_repository.full_name
            branch = run.github_repository.default_branch
        elif run.gitlab_project:
            clone_url = (
                run.gitlab_project.ssh_url_to_repo
            )  # Use SSH instead of HTTPS
            repo_name = run.gitlab_project.path_with_namespace
            branch = run.gitlab_project.default_branch

        if not clone_url:
            raise RuntimeError(
                'No repository available for cloning. Workflow requires '
                'either '
                'GitHub repository or GitLab project to be available.'
            )

        self.logger.debug('Cloning repository %s', repo_name)

        try:
            working_directory = await git.clone_repository(
                clone_url=clone_url,
                branch=branch,
                depth=1 if run.workflow.configuration.shallow_clone else None,
            )

            # Update the WorkflowRun with the working directory
            run.working_directory = working_directory

            self.logger.debug(
                'Repository cloned to working directory: %s', working_directory
            )

        except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
            self.logger.error('Failed to clone %s: %s', repo_name, exc)
            raise
