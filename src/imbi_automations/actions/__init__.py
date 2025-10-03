""" """

import logging

from imbi_automations import mixins, models

from . import (
    callablea,
    claude,
    docker,
    filea,
    git,
    github,
    shell,
    template,
    utility,
)

LOGGER = logging.getLogger(__name__)


class Actions(mixins.WorkflowLoggerMixin):
    def __init__(
        self, configuration: models.Configuration, verbose: bool = False
    ) -> None:
        super().__init__(verbose)
        self.logger = LOGGER
        self.configuration = configuration

    async def execute(
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
        self._set_workflow_logger(context.workflow)
        match action.type:
            case models.WorkflowActionTypes.callable:
                obj = callablea.CallableAction(
                    self.configuration, context, self.verbose
                )
            case models.WorkflowActionTypes.claude:
                obj = claude.ClaudeAction(
                    self.configuration, context, self.verbose
                )
            case models.WorkflowActionTypes.docker:
                obj = docker.DockerActions(
                    self.configuration, context, self.verbose
                )
            case models.WorkflowActionTypes.file:
                obj = filea.FileActions(
                    self.configuration, context, self.verbose
                )
            case models.WorkflowActionTypes.git:
                obj = git.GitActions(self.configuration, context, self.verbose)
            case models.WorkflowActionTypes.github:
                obj = github.GitHubActions(
                    self.configuration, context, self.verbose
                )
            case models.WorkflowActionTypes.shell:
                obj = shell.ShellAction(
                    self.configuration, context, self.verbose
                )
            case models.WorkflowActionTypes.template:
                obj = template.TemplateAction(
                    self.configuration, context, self.verbose
                )
            case models.WorkflowActionTypes.utility:
                obj = utility.UtilityActions(
                    self.configuration, context, self.verbose
                )
            case _:
                raise RuntimeError(f'Unsupported action type: {action.type}')

        await obj.execute(action)


__all__ = ['Actions']
