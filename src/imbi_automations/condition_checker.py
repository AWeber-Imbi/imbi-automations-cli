from imbi_automations import clients, mixins, models


class ConditionChecker(mixins.WorkflowLoggerMixin):
    """Class for checking conditions."""

    def __init__(
        self, configuration: models.Configuration, verbose: bool
    ) -> None:
        super().__init__(verbose)
        self.configuration = configuration
        self.github: clients.GitHub | None = None
        if configuration.github:
            self.github = clients.GitHub.get_instance(
                config=configuration.github
            )
        self.gitlab: clients.GitLab | None = None
        if configuration.gitlab:
            self.gitlab = clients.GitLab.get_instance(
                config=configuration.gitlab
            )

    async def check(
        self,
        context: models.WorkflowContext,
        conditions: list[models.WorkflowCondition],
    ) -> bool:
        """Run the condition checks"""
        if not conditions:
            return True
        for condition in conditions:
            if condition.file_contains:
                raise NotImplementedError(
                    'File contains conditions not yet supported'
                )
            if condition.file_exists:
                raise NotImplementedError(
                    'File exists conditions not yet supported'
                )
            if condition.file_not_exists:
                raise NotImplementedError(
                    'File not exists conditions not yet supported'
                )
            if condition.remote_file_contains:
                raise NotImplementedError(
                    'Remote file contains conditions not yet supported'
                )
            if condition.remote_file_exists:
                raise NotImplementedError(
                    'Remote file exists conditions not yet supported'
                )
            if condition.remote_file_not_exists:
                raise NotImplementedError(
                    'Remote file not exists conditions not yet supported'
                )
        return True
