"""Imbi actions for workflow execution."""

from imbi_automations import mixins, models


class ImbiActions(mixins.WorkflowLoggerMixin):
    """Executes Imbi project management system operations.

    Provides integration with Imbi API for project data access.
    """

    def __init__(
        self,
        configuration: models.Configuration,
        context: models.WorkflowContext,
        verbose: bool,
    ) -> None:
        super().__init__(verbose)
        self._set_workflow_logger(context.workflow)
        self.configuration = configuration
        self.context = context

    async def execute(self, action: models.WorkflowImbiAction) -> None:
        match action.command:
            case models.WorkflowImbiCommands.set_project_fact:
                raise NotImplementedError(
                    'Imbi set_project_fact not yet supported'
                )
            case _:
                raise RuntimeError(f'Unsupported command: {action.command}')
