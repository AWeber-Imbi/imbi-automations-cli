import argparse
import enum
import logging
import pathlib
import re
import subprocess
import typing

import jinja2

from imbi_automations import git, github, gitlab, imbi, models

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
        if not self.imbi:
            raise RuntimeError(
                'Imbi client is required for project type iteration'
            )

        project_type_slug = self.args.imbi_project_type
        LOGGER.info(
            'Processing Imbi projects for project type: %s', project_type_slug
        )

        projects = await self.imbi.get_projects_by_type(project_type_slug)
        LOGGER.info(
            'Found %d projects with project type %s',
            len(projects),
            project_type_slug,
        )

        for project in projects:
            await self._execute_workflow_run(imbi_project=project)

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

        # Check if project matches workflow filter criteria
        if not self._project_matches_filter(imbi_project):
            LOGGER.info(
                'Skipping project %d (%s) - does not match workflow filter',
                imbi_project.id,
                imbi_project.name,
            )
            return

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

    def _project_matches_filter(
        self, imbi_project: models.ImbiProject
    ) -> bool:
        """Check if an Imbi project matches the workflow filter criteria.

        Args:
            imbi_project: Imbi project to check against filter

        Returns:
            True if project matches filter criteria (or no filter),
            False otherwise
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

        LOGGER.debug(
            'Project %d (%s) matches filter criteria',
            imbi_project.id,
            imbi_project.name,
        )
        return True


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
                LOGGER.debug('Rendering template for %s: %s', key, value)
                LOGGER.debug(
                    'Available context keys: %s', list(context.keys())
                )
                if 'actions' in context:
                    LOGGER.debug(
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
                            LOGGER.debug(
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
        """Execute a single workflow action based on its type."""
        LOGGER.debug(
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

        # Execute target if configured (only for callable actions)
        if action.target and isinstance(
            action.target, models.WorkflowActionTarget
        ):
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
            LOGGER.warning(
                'Templates directory not found for action %s: %s',
                action.name,
                templates_dir,
            )
            self.action_results[action.name] = {'result': 'no_templates'}
            context['actions'] = self.action_results
            return 'no_templates'

        LOGGER.info(
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
                    LOGGER.debug(
                        'Copied template file: %s → %s',
                        rel_path,
                        target_rel_path,
                    )

                except (OSError, PermissionError, FileNotFoundError) as exc:
                    error_msg = f'Failed to copy {rel_path}: {exc}'
                    errors.append(error_msg)
                    LOGGER.error(error_msg)

        # Note: Git operations moved to end of workflow execution

        # Determine result status
        if errors:
            if copied_files:
                status = 'partial'
                LOGGER.warning(
                    'Templates action %s completed with errors: '
                    '%d copied, %d failed',
                    action.name,
                    len(copied_files),
                    len(errors),
                )
            else:
                status = 'failed'
                LOGGER.error(
                    'Templates action %s failed: %s',
                    action.name,
                    '; '.join(errors),
                )
        else:
            status = 'success'
            LOGGER.info(
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

        LOGGER.debug(
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

                LOGGER.info(
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

                LOGGER.info('Removed file %s', action.source)

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

            LOGGER.debug(
                'Rendered template %s to %s', template_file.name, target_file
            )

        except Exception as exc:
            raise RuntimeError(
                f'Failed to render template {template_file.name}: {exc}'
            ) from exc

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
            LOGGER.debug(
                'Condition file_exists "%s": %s', condition.file_exists, result
            )
            return result

        if condition.file_not_exists:
            file_path = working_directory / condition.file_not_exists
            result = not file_path.exists()
            LOGGER.debug(
                'Condition file_not_exists "%s": %s',
                condition.file_not_exists,
                result,
            )
            return result

        # If no conditions are specified, consider it as True
        LOGGER.debug('Empty condition evaluated as True')
        return True

    async def _evaluate_conditions(self, run: models.WorkflowRun) -> bool:
        """Evaluate all workflow conditions.

        Args:
            run: Workflow run containing configuration and working directory

        Returns:
            True if all conditions are met according to condition_type logic
        """
        if not run.workflow.configuration.conditions:
            LOGGER.debug('No conditions specified, proceeding with workflow')
            return True

        if not run.working_directory:
            LOGGER.warning(
                'Cannot evaluate conditions without working directory '
                '(clone_repository=true required)'
            )
            return True  # Allow workflow to proceed if no working directory

        LOGGER.debug(
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
            LOGGER.debug('Condition %d result: %s', i + 1, result)

        # Apply condition_type logic
        if (
            run.workflow.configuration.condition_type
            == models.WorkflowConditionType.all
        ):
            overall_result = all(condition_results)
            LOGGER.debug('All conditions must pass: %s', overall_result)
        else:  # any
            overall_result = any(condition_results)
            LOGGER.debug('Any condition must pass: %s', overall_result)

        return overall_result

    async def _commit_workflow_changes(
        self, run: models.WorkflowRun, project_info: str
    ) -> None:
        """Commit all changes made during workflow execution.

        Args:
            run: Workflow run containing working directory and action results
            project_info: Project information string for logging
        """
        try:
            # Collect all files to commit from actions
            all_copied_files = []
            file_operations = []
            template_actions = []

            for action_name in self.action_results:
                action_data = self.action_results[action_name]
                result = action_data.get('result', {})

                if isinstance(result, dict):
                    # Handle template actions (copied files)
                    if 'copied_files' in result:
                        copied_files = result['copied_files']
                        if copied_files:
                            all_copied_files.extend(copied_files)
                            template_actions.append(action_name)

                    # Handle file operations (renames, removes)
                    if 'operation' in result:
                        file_operations.append(result)

                        # For renames, track the new file for git add
                        if (
                            result['operation'] == 'rename'
                            and 'destination' in result
                        ):
                            all_copied_files.append(result['destination'])

            if not all_copied_files and not file_operations:
                LOGGER.debug('No files to commit for project %s', project_info)
                return

            operation_summary = []
            if template_actions:
                operation_summary.append(
                    f'{len(template_actions)} template actions'
                )
            if file_operations:
                operation_summary.append(
                    f'{len(file_operations)} file operations'
                )

            LOGGER.debug(
                'Committing changes from %s for project %s',
                ' and '.join(operation_summary),
                project_info,
            )

            # Handle file operations that need special git handling
            for operation in file_operations:
                if operation['operation'] == 'rename':
                    # For renames, remove old file from git tracking
                    source_file = operation['source']
                    LOGGER.debug('Removing old file from git: %s', source_file)
                    await git.remove_files(
                        run.working_directory, [source_file]
                    )

                elif operation['operation'] == 'remove':
                    # For removes, we need to remove the file from git tracking
                    source_file = operation['source']
                    LOGGER.debug('Removing file from git: %s', source_file)
                    await git.remove_files(
                        run.working_directory, [source_file]
                    )

            # Add files to git staging area (new files and renamed files)
            if all_copied_files:
                await git.add_files(run.working_directory, all_copied_files)

            # Create commit message in specified format
            workflow_name = run.workflow.configuration.name
            workflow_description = (
                run.workflow.configuration.description
                or 'No description provided'
            )

            commit_message = (
                f'imbi-automations: {workflow_name}\n\n{workflow_description}'
            )

            # Add skip-checks trailer if ci_skip_checks is enabled
            if run.workflow.configuration.ci_skip_checks:
                commit_message += '\n\nskip-checks: true'

            # Commit changes
            commit_sha = await git.commit_changes(
                working_directory=run.working_directory,
                message=commit_message,
                author_name='Imbi Automations',
                author_email='noreply@aweber.com',
            )

            if commit_sha:
                LOGGER.info(
                    'Successfully committed workflow changes for '
                    'project %s: %s',
                    project_info,
                    commit_sha,
                )

                # Push changes to remote repository
                try:
                    await git.push_changes(
                        working_directory=run.working_directory,
                        remote='origin',
                        branch=None,  # Push current branch
                    )
                    LOGGER.info(
                        'Successfully pushed workflow changes for project %s',
                        project_info,
                    )
                except (OSError, subprocess.CalledProcessError) as exc:
                    LOGGER.error(
                        'Failed to push workflow changes for project %s: %s',
                        project_info,
                        exc,
                    )
                    # Don't re-raise - commit succeeded, push failure secondary
            else:
                LOGGER.info(
                    'No changes to commit for project %s '
                    '(files already up-to-date)',
                    project_info,
                )

        except (OSError, subprocess.CalledProcessError) as exc:
            LOGGER.error(
                'Failed to commit workflow changes for project %s: %s',
                project_info,
                exc,
            )
            # Don't re-raise - workflow should complete even if commit fails

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

        # Handle repository cloning if required
        if run.workflow.configuration.clone_repository:
            await self._setup_repository_clone(run)

        # Evaluate workflow conditions
        if not await self._evaluate_conditions(run):
            LOGGER.info(
                'Skipping workflow execution for project %s - '
                'conditions not met',
                project_info,
            )
            return

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

        # Commit all template changes at the end of workflow
        if run.working_directory:
            await self._commit_workflow_changes(run, project_info)

        LOGGER.info(
            'Workflow completed successfully for project %s', project_info
        )

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

        LOGGER.info('Cloning repository %s for workflow execution', repo_name)

        try:
            working_directory = await git.clone_repository(
                clone_url=clone_url,
                branch=branch,
                depth=1,  # Shallow clone for faster performance
            )

            # Update the WorkflowRun with the working directory
            run.working_directory = working_directory

            LOGGER.debug(
                'Repository cloned to working directory: %s', working_directory
            )

        except Exception as exc:
            LOGGER.error('Failed to clone repository %s: %s', repo_name, exc)
            raise
