"""GitHub operations for workflow execution."""

from imbi_automations import mixins, models


class GitHubActions(mixins.WorkflowLoggerMixin):
    """GitHub executor for workflow actions."""

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

    async def execute(self, action: models.WorkflowGitHubAction) -> None:
        match action.command:
            case models.WorkflowGitHubCommand.sync_environments:
                raise NotImplementedError(
                    'GitHub sync environments not yet supported'
                )
            case _:
                raise RuntimeError(f'Unsupported command: {action.command}')
