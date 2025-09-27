import logging
import pathlib
import tempfile

from imbi_automations import claude, git, mixins, models

LOGGER = logging.getLogger(__name__)


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

        if self._needs_claude:
            self.claude = claude.Claude(
                self.configuration.claude_code,
                context.working_directory,
                self.verbose,
            )

        if self.workflow.configuration.git.clone:
            await git.clone_repository(
                context.working_directory,
                self._git_clone_url(github_repository, gitlab_project),
                self.workflow.configuration.git.starting_branch,
                1 if self.workflow.configuration.git.shallow else None,
            )

        try:
            for action in self.workflow.configuration.actions:
                await self._execute_action(context, action)
        except RuntimeError as exc:
            self.logger.error('Error executing action: %s', exc)
            working_directory.cleanup()
            return False

        working_directory.cleanup()
        return True

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
        self._log_verbose_info('Executing action: %s', action.name)
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
        match action.command:
            case models.WorkflowFileActionCommand.append:
                raise NotImplementedError('Append not yet supported')
            case models.WorkflowFileActionCommand.copy:
                raise NotImplementedError('Copy not yet supported')
            case models.WorkflowFileActionCommand.delete:
                raise NotImplementedError('Delete not yet supported')
            case models.WorkflowFileActionCommand.move:
                raise NotImplementedError('Move not yet supported')
            case models.WorkflowFileActionCommand.rename:
                raise NotImplementedError('Rename not yet supported')
            case models.WorkflowFileActionCommand.write:
                raise NotImplementedError('Write not yet supported')
            case _:
                raise RuntimeError(f'Unsupported command: {action.command}')

    async def _execute_action_git(
        self, context: models.WorkflowContext, action: models.WorkflowGitAction
    ) -> None:
        match action.command:
            case models.WorkflowGitActionCommand.extract:
                raise NotImplementedError('Extract not yet supported')
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
        raise NotImplementedError('Shell actions not yet supported')

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

    @property
    async def _needs_claude(self) -> bool:
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
