import argparse
import enum
import logging
import re
import typing

import jinja2

from imbi_automations import github, gitlab, imbi, models

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
        )

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
            await self._execute_workflow_run(imbi_project=project)

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
                github_repository = await self._get_github_repository(
                    imbi_project
                )
                if github_repository:
                    LOGGER.debug(
                        'Found GitHub repository: %s',
                        github_repository.full_name,
                    )
            elif self.gitlab and not gitlab_project:
                gitlab_project = await self._get_gitlab_project(imbi_project)

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

        # Check if workflow requires GitHub repository but we don't have one
        if self._workflow_requires_github() and not github_repository:
            LOGGER.info(
                'Skipping project %d (%s - %s) - no GitHub repository',
                imbi_project.id,
                imbi_project.name,
                imbi_project.project_type_slug,
            )
            return

        # Check if workflow requires GitLab project but we don't have one
        if self._workflow_requires_gitlab() and not gitlab_project:
            LOGGER.info(
                'Skipping project %d (%s) - no GitLab project',
                imbi_project.id,
                imbi_project.name,
            )
            return

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

        await self.workflow_engine.execute(run)

    def _workflow_requires_github(self) -> bool:
        """Check if workflow requires GitHub repository context."""
        for action in self.workflow.configuration.actions:
            # Check if any templates reference github_repository
            for kwargs in [
                action.value.kwargs,
                action.target.kwargs if action.target else None,
            ]:
                if kwargs:
                    for value in kwargs.model_dump().values():
                        if (
                            isinstance(value, str)
                            and 'github_repository' in value
                        ):
                            return True
            # Check if any client calls are to GitHub
            if action.value.client == 'github':
                return True
            if action.target and action.target.client == 'github':
                return True
        return False

    def _workflow_requires_gitlab(self) -> bool:
        """Check if workflow requires GitLab project context."""
        for action in self.workflow.configuration.actions:
            # Check if any templates reference gitlab_project
            for kwargs in [
                action.value.kwargs,
                action.target.kwargs if action.target else None,
            ]:
                if kwargs:
                    for value in kwargs.model_dump().values():
                        if (
                            isinstance(value, str)
                            and 'gitlab_project' in value
                        ):
                            return True
            # Check if any client calls are to GitLab
            if action.value.client == 'gitlab':
                return True
            if action.target and action.target.client == 'gitlab':
                return True
        return False


class WorkflowEngine:
    def __init__(
        self,
        github_client: github.GitHub | None = None,
        gitlab_client: gitlab.GitLab | None = None,
        imbi_client: imbi.Imbi | None = None,
    ) -> None:
        self.github = github_client
        self.gitlab = gitlab_client
        self.imbi = imbi_client

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

    def _create_template_context(
        self, run: models.WorkflowRun
    ) -> dict[str, typing.Any]:
        """Create template context from workflow run data."""
        context = {'workflow': run.workflow, 'actions': self.action_results}

        if run.github_repository:
            context['github_repository'] = run.github_repository
        if run.gitlab_project:
            context['gitlab_project'] = run.gitlab_project
        if run.imbi_project:
            context['imbi_project'] = run.imbi_project

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
                LOGGER.debug('Rendering template for %s: %s', key, value)
                LOGGER.debug(
                    'Available context keys: %s', list(context.keys())
                )
                if 'actions' in context:
                    LOGGER.debug(
                        'Available actions: %s',
                        list(context['actions'].keys()),
                    )
                template = self.jinja_env.from_string(value)
                rendered_value = template.render(context)
                # Try to convert back to original type if it was a number
                if rendered_value.isdigit():
                    rendered[key] = int(rendered_value)
                elif rendered_value.replace('.', '').isdigit():
                    rendered[key] = float(rendered_value)
                else:
                    rendered[key] = rendered_value
                LOGGER.debug('Rendered %s: %s → %s', key, value, rendered[key])
            else:
                rendered[key] = value

        return rendered

    def _get_client(self, client_name: str) -> typing.Any:
        """Get client instance by name."""
        clients = {
            'github': self.github,
            'gitlab': self.gitlab,
            'imbi': self.imbi,
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
        """Execute a single workflow action."""

        # Get value via client method call
        value_client = self._get_client(action.value.client)
        value_method = getattr(value_client, action.value.method)
        value_kwargs = self._render_template_kwargs(
            action.value.kwargs, context
        )

        LOGGER.debug(
            'Calling %s.%s with kwargs: %s',
            action.value.client,
            action.value.method,
            value_kwargs,
        )

        result = await value_method(**value_kwargs)

        # Apply value mapping if configured
        mapped_result = self._apply_value_mapping(result, action.value_mapping)

        LOGGER.debug(
            'Action %s result: %s (mapped: %s)',
            action.name,
            result,
            mapped_result,
        )

        # Store result for future template references
        self.action_results[action.name] = {'result': mapped_result}

        # Update context for any subsequent template rendering
        context['actions'] = self.action_results

        # Execute target if configured
        if action.target:
            target_client = self._get_client(action.target.client)
            target_method = getattr(target_client, action.target.method)
            target_kwargs = self._render_template_kwargs(
                action.target.kwargs, context
            )

            LOGGER.debug(
                'Calling %s.%s with kwargs: %s',
                action.target.client,
                action.target.method,
                target_kwargs,
            )

            await target_method(**target_kwargs)

        return mapped_result

    async def execute(self, run: models.WorkflowRun) -> None:
        """Execute a complete workflow run."""
        project_info = (
            f'{run.imbi_project.name} ({run.imbi_project.project_type})'
            if run.imbi_project
            else 'Unknown Project'
        )
        LOGGER.debug(
            'Executing workflow: %s for project %s',
            run.workflow.configuration.name,
            project_info,
        )

        # Clear previous action results
        self.action_results = ActionResults()

        # Create template context
        context = self._create_template_context(run)

        # Execute each action sequentially
        for action in run.workflow.configuration.actions:
            try:
                LOGGER.debug(
                    'Executing action: %s for project %s',
                    action.name,
                    project_info,
                )
                await self._execute_action(action, context)
            except Exception as exc:
                LOGGER.error(
                    'Action %s failed for project %s: %s',
                    action.name,
                    project_info,
                    exc,
                )
                raise

        LOGGER.info(
            'Workflow completed successfully for project %s', project_info
        )
