"""Callable operations for workflow execution."""

from imbi_automations import mixins, models


class CallableAction(mixins.WorkflowLoggerMixin):
    """Callable executor for workflow actions."""

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

    async def execute(self, action: models.WorkflowCallableAction) -> None:
        raise NotImplementedError('Callable actions not yet supported')
