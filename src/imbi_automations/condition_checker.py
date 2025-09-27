import logging

from imbi_automations import clients, mixins, models

LOGGER = logging.getLogger(__name__)


class ConditionChecker(mixins.WorkflowLoggerMixin):
    """Class for checking conditions."""

    def __init__(
        self, configuration: models.Configuration, verbose: bool
    ) -> None:
        super().__init__(verbose)
        self.configuration = configuration
        self.logger = LOGGER
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
        condition_type: models.WorkflowConditionType,
        conditions: list[models.WorkflowCondition],
    ) -> bool:
        """Run the condition checks"""
        if not conditions:
            return True

        base_path = context.working_directory / 'repository'

        for condition in conditions:
            if condition.file_contains and condition.file:
                file_path = base_path / condition.file
                if not file_path.is_file():
                    self.logger.debug(
                        'File %s does not exist for contains check',
                        condition.file,
                    )
                    return False
                try:
                    file_content = file_path.read_text(encoding='utf-8')
                except (OSError, UnicodeDecodeError) as exc:
                    self.logger.warning(
                        'Failed to read file %s for contains check: %s',
                        condition.file,
                        exc,
                    )
                    return False
                if condition.file_contains not in file_content:
                    self.logger.debug(
                        'File %s does not contain "%s"',
                        condition.file,
                        condition.file_contains,
                    )
                    return False

            if condition.file_exists:
                file_path = base_path / condition.file_exists
                if not file_path.exists():
                    self.logger.debug(
                        'File %s does not exist in repository',
                        condition.file_exists,
                    )
                    return False

            if condition.file_not_exists:
                file_path = base_path / condition.file_not_exists
                if file_path.exists():
                    self.logger.debug(
                        'File %s does exist in repository',
                        condition.file_not_exists,
                    )
                    return False

        return True

    async def check_remote(
        self,
        context: models.WorkflowContext,
        condition_type: models.WorkflowConditionType,
        conditions: list[models.WorkflowCondition],
    ) -> bool:
        """Run the condition checks"""
        if not conditions:
            return True

        for condition in conditions:
            if (
                condition.remote_client
                == models.WorkflowConditionRemoteClient.github
                and not self.github
            ):
                self.logger.warning(
                    'Remote Action invoked for GitHub, '
                    'but GitHub is not configured'
                )
                return False
            elif (
                condition.remote_client
                == models.WorkflowConditionRemoteClient.gitlab
                and not self.gitlab
            ):
                self.logger.warning(
                    'Remote Action invoked for GitLab, '
                    'but GitLab is not configured'
                )
                return False
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
