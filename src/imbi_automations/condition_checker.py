import logging
import pathlib
import re
import typing

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

    def check(
        self,
        context: models.WorkflowContext,
        condition_type: models.WorkflowConditionType,
        conditions: list[models.WorkflowCondition],
    ) -> bool:
        """Run the condition checks"""
        if not conditions:
            return True

        results = []

        base_path = context.working_directory / 'repository'

        for condition in conditions:
            if condition.file_contains and condition.file:
                results.append(self._check_file_contains(base_path, condition))
            elif condition.file_exists:
                results.append(
                    self._check_file_pattern_exists(
                        base_path, condition.file_exists
                    )
                )
            elif condition.file_not_exists:
                results.append(
                    not self._check_file_pattern_exists(
                        base_path, condition.file_not_exists
                    )
                )
        if condition_type == models.WorkflowConditionType.any:
            return any(results)
        return all(results)

    async def check_remote(
        self,
        context: models.WorkflowContext,
        condition_type: models.WorkflowConditionType,
        conditions: list[models.WorkflowCondition],
    ) -> bool:
        """Run the condition checks"""
        if not conditions:
            return True
        results = []
        for condition in conditions:
            self.logger.debug('%r', condition.model_dump())
            client = await self._check_remote_client(condition)
            file_path = (
                condition.remote_file
                or condition.remote_file_exists
                or condition.remote_file_not_exists
            )
            content = await client.get_file_contents(context, file_path)
            if condition.remote_file_contains:
                results.append(condition.remote_file_contains in content or '')
            elif condition.remote_file_exists:
                results.append(content is not None)
            elif condition.remote_file_not_exists:
                results.append(content is None)
        if condition_type == models.WorkflowConditionType.any:
            return any(results)
        return all(results)

    def _check_file_contains(
        self, base_path: pathlib.Path, condition: models.WorkflowCondition
    ) -> bool:
        """Check if a file exists in the repository"""
        file_path = base_path / condition.file
        if not file_path.is_file():
            self.logger.debug(
                'File %s does not exist for contains check', condition.file
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
        return condition.file_contains in file_content

    @staticmethod
    def _check_file_pattern_exists(
        base_path: pathlib.Path, file: str | typing.Pattern
    ) -> bool:
        """Check if a file exists using either exact path or regex pattern.

        Args:
            base_path: Repository base path
            file: File path string or compiled regex pattern

        Returns:
            True if file exists (string) or pattern matches any file (regex)

        """
        if isinstance(file, str):
            return (base_path / file).exists()

        try:
            pattern = re.compile(file)
        except re.error as exc:
            raise RuntimeError(f'Invalid regex pattern "{file}"') from exc

        for file_path in base_path.rglob('*'):
            relative_path = file_path.relative_to(base_path)
            if pattern.search(str(relative_path)):
                return True
        return False

    async def _check_remote_client(
        self, condition: models.WorkflowCondition
    ) -> clients.GitHub | clients.GitLab:
        """Return the appropriate client for the condition

        :raises: RuntimeError

        """
        if (
            condition.remote_client
            == models.WorkflowConditionRemoteClient.github
        ):
            if not self.github:
                raise RuntimeError(
                    'Remote Action invoked for GitHub, '
                    'but GitHub is not configured'
                )
            return self.github
        elif (
            condition.remote_client
            == models.WorkflowConditionRemoteClient.gitlab
        ):
            if not self.gitlab:
                raise RuntimeError(
                    'Remote Action invoked for GitLab, '
                    'but GitLab is not configured'
                )
            return self.github
        raise RuntimeError('Unsupported remote client for condition')
