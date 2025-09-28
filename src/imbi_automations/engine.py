import logging
import pathlib
import tempfile

from imbi_automations import (
    claude,
    clients,
    condition_checker,
    file_actions,
    git,
    mixins,
    models,
    prompts,
    shell,
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
        self.workflow = workflow
        self._set_workflow_logger(workflow)

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
            return False

        if self.workflow.configuration.git.clone:
            context.starting_commit = await git.clone_repository(
                context.working_directory,
                self._git_clone_url(github_repository, gitlab_project),
                self.workflow.configuration.git.starting_branch,
                1 if self.workflow.configuration.git.shallow else None,
            )

        if not self.condition_checker.check(
            context,
            self.workflow.configuration.condition_type,
            self.workflow.configuration.conditions,
        ):
            return False

        try:
            for action in self.workflow.configuration.actions:
                await self._execute_action(context, action)
                if action.committable:
                    await self.claude.commit(context, action)
        except RuntimeError as exc:
            self.logger.error('Error executing action: %s', exc)
            working_directory.cleanup()
            return False

        if self.workflow.configuration.create_pull_request:
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

        branch_name = f'imbi-automations/{context.workflow.path.name}'

        self._log_verbose_info('Creating pull request branch: %s', branch_name)

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
            'Successfully pushed branch %s for pull request', branch_name
        )

        summary = await git.get_commits_since(
            working_directory=repository_dir,
            starting_commit=context.starting_commit,
        )
        self.logger.debug('%i commits made in workflow', len(summary.commits))

        prompt = prompts.render(
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
        self._log_verbose_info('Created pull request: %s', pr_url)

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

    async def _execute_action_claude(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowClaudeAction,
    ) -> None:
        """Execute the Claude Code action."""
        await self.claude.execute(context, action)

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
                await git.extract_file_from_commit(
                    working_directory=context.working_directory / 'repository',
                    source_file=action.source,
                    destination_file=context.working_directory
                    / 'extracted'
                    / action.destination,
                    commit_keyword=action.commit_keyword,
                    search_strategy=action.search_strategy
                    or 'before_last_match',
                )
            case _:
                raise RuntimeError(f'Unsupported command: {action.command}')

    async def _execute_action_callable(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowCallableAction,
    ) -> None:
        """Execute the callable action."""
        raise NotImplementedError('Callable actions not yet supported')

    async def _execute_action_docker(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowDockerAction,
    ) -> None:
        """Execute the docker action."""
        match action.command:
            case models.WorkflowDockerActionCommand.build:
                raise NotImplementedError('Docker build not yet supported')
            case models.WorkflowDockerActionCommand.extract:
                raise NotImplementedError('Docker extract not yet supported')
            case models.WorkflowDockerActionCommand.pull:
                raise NotImplementedError('Docker pull not yet supported')
            case models.WorkflowDockerActionCommand.push:
                raise NotImplementedError('Docker push not yet supported')
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
        raise NotImplementedError('Template actions not yet supported')

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

    def _setup_workflow_run(
        self,
        project: models.ImbiProject,
        working_directory: str,
        github_repository: models.GitHubRepository | None = None,
        gitlab_project: models.GitLabProject | None = None,
    ) -> models.WorkflowContext:
        working_directory = pathlib.Path(working_directory)

        # Create the symlink of the workflow to the working directory
        (working_directory / 'workflow').symlink_to(
            self.workflow.path.resolve()
        )

        # Ensure the extracted directory exists
        (working_directory / 'extracted').mkdir(exist_ok=True)

        return models.WorkflowContext(
            workflow=self.workflow,
            github_repository=github_repository,
            gitlab_project=gitlab_project,
            imbi_project=project,
            working_directory=working_directory,
        )
