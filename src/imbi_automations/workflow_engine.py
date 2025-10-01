import datetime
import logging
import pathlib
import shutil
import tempfile

from imbi_automations import (
    claude,
    clients,
    condition_checker,
    docker,
    file_actions,
    git,
    mixins,
    models,
    prompts,
    shell,
    template_action,
    workflow_filter,
)

LOGGER = logging.getLogger(__name__)
BASE_PATH = pathlib.Path(__file__).parent


class WorkflowEngine(mixins.WorkflowLoggerMixin):
    """Workflow engine for running workflow actions."""

    def __init__(
        self,
        configuration: models.Configuration,
        workflow: models.Workflow,
        verbose: bool = False,
    ) -> None:
        super().__init__(verbose)
        self.claude: claude.Claude | None = None
        self.condition_checker = condition_checker.ConditionChecker(
            configuration, verbose
        )
        self.github = clients.GitHub.get_instance(config=configuration.github)
        self.configuration = configuration
        self.last_error_path: pathlib.Path | None = None
        self.workflow = workflow
        self.workflow_filter = workflow_filter.Filter(
            configuration, workflow, verbose
        )
        self._set_workflow_logger(workflow)

        if not self.configuration.claude_code.enabled and (
            self._needs_claude_code
            or workflow.configuration.github.create_pull_request
        ):
            raise RuntimeError(
                'Workflow requires Claude Code, but it is not enabled'
            )

    async def execute(
        self,
        project: models.ImbiProject,
        github_repository: models.GitHubRepository | None = None,
        gitlab_project: models.GitLabProject | None = None,
    ) -> bool:
        """Execute the workflow."""
        working_directory = tempfile.TemporaryDirectory()
        context = self._setup_workflow_run(
            project, working_directory.name, github_repository, gitlab_project
        )

        self.claude = claude.Claude(
            self.configuration,
            context.working_directory,
            self.configuration.commit_author,
            self.verbose,
        )

        if not await self.condition_checker.check_remote(
            context,
            self.workflow.configuration.condition_type,
            self.workflow.configuration.conditions,
        ):
            self.logger.info(
                'Remote workflow conditions not met for %s',
                context.imbi_project.name,
            )
            return False

        if self.workflow.configuration.git.clone:
            context.starting_commit = await git.clone_repository(
                context.working_directory,
                self._git_clone_url(github_repository, gitlab_project),
                self.workflow.configuration.git.starting_branch,
                self.workflow.configuration.git.depth,
            )

        if not self.condition_checker.check(
            context,
            self.workflow.configuration.condition_type,
            self.workflow.configuration.conditions,
        ):
            self.logger.info(
                'Workflow conditions not met for %s', context.imbi_project.name
            )
            return False

        try:
            for action in self.workflow.configuration.actions:
                await self._execute_action(context, action)
                if action.committable:
                    if (
                        self.configuration.ai_commits
                        and self.configuration.claude_code.enabled
                    ):
                        await self.claude.commit(context, action)
                    else:
                        await self._fallback_commit(context, action)
        except RuntimeError as exc:
            self.logger.error(
                'Error executing action "%s": %s', action.name, exc
            )
            if self.configuration.preserve_on_error:
                self._preserve_error_state(context, working_directory)
            working_directory.cleanup()
            return False

        if (
            self.workflow.configuration.github.create_pull_request
            and self.configuration.claude_code.enabled
        ):
            await self._create_pull_request(context)
        else:
            await git.push_changes(
                working_directory=context.working_directory / 'repository',
                remote='origin',
                branch='main',
                set_upstream=True,
            )

        working_directory.cleanup()
        return True

    async def _create_pull_request(
        self, context: models.WorkflowContext
    ) -> None:
        """Create a pull request by creating a branch and pushing changes."""
        repository_dir = context.working_directory / 'repository'

        branch_name = f'imbi-automations/{context.workflow.slug}'

        # Delete remote branch if replace_branch is enabled
        if context.workflow.configuration.github.replace_branch:
            self._log_verbose_info(
                'Deleting remote branch %s if exists for %s '
                '(replace_branch=True)',
                branch_name,
                context.imbi_project.slug,
            )
            await git.delete_remote_branch_if_exists(
                working_directory=repository_dir, branch_name=branch_name
            )

        self._log_verbose_info(
            'Creating pull request branch: %s for %s',
            branch_name,
            context.imbi_project.slug,
        )

        # Create and checkout new branch
        await git.create_branch(
            working_directory=repository_dir,
            branch_name=branch_name,
            checkout=True,
        )

        # Push the new branch to remote
        await git.push_changes(
            working_directory=repository_dir,
            remote='origin',
            branch=branch_name,
            set_upstream=True,
        )

        self._log_verbose_info(
            'Successfully pushed branch %s for pull request for %s',
            branch_name,
            context.imbi_project.slug,
        )

        summary = await git.get_commits_since(
            working_directory=repository_dir,
            starting_commit=context.starting_commit,
        )
        self.logger.debug('%i commits made in workflow', len(summary.commits))

        prompt = prompts.render(
            context,
            BASE_PATH / 'prompts' / 'pull-request-summary.md.j2',
            summary=summary.model_dump_json(indent=2),
        )
        self.logger.debug('Prompt: %s', prompt)

        body = await self.claude.query(prompt)
        pr_url = await self.github.create_pull_request(
            context=context,
            title=f'imbi-automations: {context.workflow.configuration.name}',
            body=body,
            head_branch=branch_name,
        )
        self._log_verbose_info(
            'Created pull request for %s: %s',
            context.imbi_project.slug,
            pr_url,
        )

    async def _execute_action(
        self,
        context: models.WorkflowContext,
        action: (
            models.WorkflowCallableAction
            | models.WorkflowClaudeAction
            | models.WorkflowDockerAction
            | models.WorkflowFileAction
            | models.WorkflowGitAction
            | models.WorkflowGitHubAction
            | models.WorkflowShellAction
            | models.WorkflowTemplateAction
            | models.WorkflowUtilityAction
        ),
    ) -> None:
        """Execute an action."""
        if action.filter and not await self.workflow_filter.filter_project(
            context.imbi_project, action.filter
        ):
            self.logger.debug('Skipping %s due to project filter', action.name)
            return

        if not self.condition_checker.check(
            context,
            self.workflow.configuration.condition_type,
            action.conditions,
        ):
            self.logger.debug(
                'Skipping %s due to failed condition check', action.name
            )
            return
        elif not await self.condition_checker.check_remote(
            context,
            self.workflow.configuration.condition_type,
            action.conditions,
        ):
            self._log_verbose_info(
                'Skipping action %s due to failed condition check', action.name
            )
            return

        match action.type:
            case models.WorkflowActionTypes.callable:
                await self._execute_action_callable(context, action)
            case models.WorkflowActionTypes.claude:
                await self._execute_action_claude(context, action)
            case models.WorkflowActionTypes.docker:
                await self._execute_action_docker(context, action)
            case models.WorkflowActionTypes.file:
                await self._execute_action_file(context, action)
            case models.WorkflowActionTypes.git:
                await self._execute_action_git(context, action)
            case models.WorkflowActionTypes.github:
                await self._execute_action_github(context, action)
            case models.WorkflowActionTypes.shell:
                await self._execute_action_shell(context, action)
            case models.WorkflowActionTypes.template:
                await self._execute_action_template(context, action)
            case models.WorkflowActionTypes.utility:
                await self._execute_action_utility(context, action)
            case _:
                raise RuntimeError(f'Unsupported action type: {action.type}')

    async def _execute_action_callable(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowCallableAction,
    ) -> None:
        """Execute the callable action."""
        raise NotImplementedError('Callable actions not yet supported')

    async def _execute_action_claude(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowClaudeAction,
    ) -> None:
        """Execute the Claude Code action."""
        await self.claude.execute(context, action)

    async def _execute_action_docker(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowDockerAction,
    ) -> None:
        """Execute the docker action."""
        docker_executor = docker.Docker(verbose=self.verbose)
        await docker_executor.execute(context, action)

    async def _execute_action_file(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowFileAction,
    ) -> None:
        """Execute the file action."""
        file_executor = file_actions.FileActions(verbose=self.verbose)
        await file_executor.execute(context, action)

    @staticmethod
    async def _execute_action_git(
        context: models.WorkflowContext, action: models.WorkflowGitAction
    ) -> None:
        match action.command:
            case models.WorkflowGitActionCommand.extract:
                if (
                    not await git.extract_file_from_commit(
                        working_directory=context.working_directory
                        / 'repository',
                        source_file=action.source,
                        destination_file=context.working_directory
                        / 'extracted'
                        / action.destination,
                        commit_keyword=action.commit_keyword,
                        search_strategy=action.search_strategy
                        or 'before_last_match',
                    )
                    and not action.ignore_errors
                ):
                    raise RuntimeError(
                        f'Git extraction failed for {action.source}'
                    )
            case _:
                raise RuntimeError(f'Unsupported command: {action.command}')

    async def _execute_action_github(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowGitHubAction,
    ) -> None:
        """Execute the github action."""
        match action.command:
            case models.WorkflowGitHubCommand.sync_environments:
                raise NotImplementedError(
                    'GitHub sync environments not yet supported'
                )
            case _:
                raise RuntimeError(f'Unsupported command: {action.command}')

    async def _execute_action_shell(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowShellAction,
    ) -> None:
        """Execute the shell action."""
        shell_executor = shell.Shell(verbose=self.verbose)
        await shell_executor.execute(context, action)

    async def _execute_action_template(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowTemplateAction,
    ) -> None:
        """Execute the template action."""
        await template_action.execute(context, action)

    async def _execute_action_utility(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowUtilityAction,
    ) -> None:
        """Execute the utility action."""
        match action.command:
            case models.WorkflowUtilityCommands.docker_tag:
                raise NotImplementedError(
                    'Utility docker_tag not yet supported'
                )
            case models.WorkflowUtilityCommands.dockerfile_from:
                raise NotImplementedError(
                    'Utility dockerfile_from not yet supported'
                )
            case models.WorkflowUtilityCommands.compare_semver:
                raise NotImplementedError(
                    'Utility compare_semver not yet supported'
                )
            case models.WorkflowUtilityCommands.parse_python_constraints:
                raise NotImplementedError(
                    'Utility parse_python_constraints not yet supported'
                )
            case _:
                raise RuntimeError(f'Unsupported command: {action.command}')

    async def _fallback_commit(
        self, context: models.WorkflowContext, action: models.WorkflowAction
    ) -> None:
        """Fallback commit implementation without Claude.

        - Stages all pending changes
        - Creates a commit with required format and trailer
        """
        repo_dir = context.working_directory / 'repository'

        # Stage all changes including deletions
        await git.add_files(working_directory=repo_dir, files=['--all'])

        # Build commit message
        slug = context.workflow.slug or ''
        message = (
            f'imbi-automations: {slug} {action.name}\n\n'
            '🤖 Generated with [Imbi Automations](https://github.com/AWeber-Imbi/).'
        )

        try:
            commit_sha = await git.commit_changes(
                working_directory=repo_dir,
                message=message,
                commit_author=self.configuration.commit_author,
            )
        except RuntimeError as exc:
            self.logger.error('Fallback commit failed: %s', exc)
            raise
        else:
            if commit_sha:
                self.logger.info(
                    'Committed changes (fallback): %s', commit_sha
                )
            else:
                self.logger.info('No changes to commit (fallback)')

    def get_last_error_path(self) -> pathlib.Path | None:
        """Return path where error state was last preserved.

        Returns:
            Path to error directory, or None if no error preserved

        """
        return self.last_error_path

    def _preserve_error_state(
        self,
        context: models.WorkflowContext,
        working_directory: tempfile.TemporaryDirectory,
    ) -> None:
        """Preserve working directory state on error for debugging.

        Args:
            context: Workflow execution context
            working_directory: Temporary directory to preserve

        """
        timestamp = datetime.datetime.now(tz=datetime.UTC).strftime(
            '%Y%m%d-%H%M%S'
        )
        workflow_slug = context.workflow.slug or 'unknown'
        project_slug = context.imbi_project.slug

        # Create error directory: errors/<workflow>/<project>-<timestamp>
        error_path = (
            self.configuration.error_dir
            / workflow_slug
            / f'{project_slug}-{timestamp}'
        )

        try:
            error_path.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                working_directory.name,
                error_path,
                dirs_exist_ok=True,
                symlinks=True,
            )
            self.last_error_path = error_path
            self.logger.info(
                'Preserved error state to %s for debugging', error_path
            )
        except OSError as exc:
            self.last_error_path = None
            self.logger.error(
                'Failed to preserve error state to %s: %s', error_path, exc
            )

    def _git_clone_url(
        self,
        github_repository: models.GitHubRepository | None = None,
        gitlab_project: models.GitLabProject | None = None,
    ) -> str:
        if github_repository:
            if (
                self.workflow.configuration.git.clone_type
                == models.WorkflowGitCloneType.ssh
            ):
                return github_repository.ssh_url
            return github_repository.clone_url
        elif gitlab_project:
            if (
                self.workflow.configuration.git.clone_type
                == models.WorkflowGitCloneType.ssh
            ):
                return gitlab_project.ssh_url_to_repo
            return gitlab_project.http_url_to_repo
        raise ValueError('No repository provided')

    @property
    def _needs_claude_code(self) -> bool:
        """Will return True if any action requires Claude Code."""
        return any(
            action.type == models.WorkflowActionTypes.claude
            for action in self.workflow.configuration.actions
        )

    def _setup_workflow_run(
        self,
        project: models.ImbiProject,
        working_directory: str,
        github_repository: models.GitHubRepository | None = None,
        gitlab_project: models.GitLabProject | None = None,
    ) -> models.WorkflowContext:
        working_directory = pathlib.Path(working_directory)

        # Create the symlink of the workflow to the working directory
        workflow_path = working_directory / 'workflow'
        workflow_path.symlink_to(self.workflow.path.resolve())
        if not workflow_path.is_symlink():
            raise RuntimeError(
                f'Unable to create symlink for workflow: {workflow_path}'
            )

        # Ensure the extracted directory exists
        (working_directory / 'extracted').mkdir(exist_ok=True)

        return models.WorkflowContext(
            workflow=self.workflow,
            github_repository=github_repository,
            gitlab_project=gitlab_project,
            imbi_project=project,
            starting_commit=None,
            working_directory=working_directory,
        )
