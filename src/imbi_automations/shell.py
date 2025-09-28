import asyncio
import logging
import pathlib
import shlex
import subprocess
import tempfile

from imbi_automations import mixins, models, prompts

LOGGER = logging.getLogger(__name__)


class Shell(mixins.WorkflowLoggerMixin):
    """Shell command executor for workflow actions."""

    def __init__(self, verbose: bool = False) -> None:
        super().__init__(verbose)
        self.logger = LOGGER

    async def execute(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowShellAction,
    ) -> None:
        """Execute a shell command with optional template rendering.

        Args:
            context: Workflow context for template rendering
            action: Shell action containing the command to execute

        Raises:
            subprocess.CalledProcessError: If command execution fails
            ValueError: If cmd syntax is invalid or template rendering fails

        """
        self._set_workflow_logger(context.workflow)

        # Render command if it contains templating
        command_str = self._render_command(action.command, context)

        self._log_verbose_info('Executing shell command: %s', command_str)

        # Parse command string into arguments using shell-like parsing
        try:
            command_args = shlex.split(command_str)
        except ValueError as exc:
            raise ValueError(f'Invalid shell command syntax: {exc}') from exc

        if not command_args:
            raise ValueError('Empty command after template rendering')

        # Set working directory to repository if it exists
        cwd = None
        if context.working_directory:
            repository_dir = context.working_directory / 'repository'
            if repository_dir.exists():
                cwd = repository_dir
            else:
                cwd = context.working_directory

        try:
            # Execute command asynchronously
            process = await asyncio.create_subprocess_exec(
                *command_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            stdout, stderr = await process.communicate()

            # Decode output
            stdout_str = stdout.decode('utf-8') if stdout else ''
            stderr_str = stderr.decode('utf-8') if stderr else ''

            self._log_verbose_info(
                'Shell command completed with exit code %d', process.returncode
            )

            if stdout_str:
                self.logger.debug('Command stdout: %s', stdout_str)
            if stderr_str:
                self.logger.debug('Command stderr: %s', stderr_str)

            if process.returncode != 0:
                if action.ignore_errors:
                    self.logger.info(
                        'Shell command failed with exit code %d (ignored): %s',
                        process.returncode,
                        stderr_str or stdout_str,
                    )
                else:
                    self.logger.error(
                        'Shell command failed with exit code %d: %s',
                        process.returncode,
                        stderr_str or stdout_str,
                    )
                    raise subprocess.CalledProcessError(
                        process.returncode,
                        command_args,
                        output=stdout,
                        stderr=stderr,
                    )

        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f'Command not found: {command_args[0]}'
            ) from exc

    def _render_command(
        self, command: str, context: models.WorkflowContext
    ) -> str:
        """Render command template if it contains Jinja2 syntax.

        Args:
            command: Command string that may contain templates
            context: Workflow context for template variables

        Returns:
            Rendered command string

        """
        # Detect if command contains Jinja2 templating syntax
        if self._has_template_syntax(command):
            self.logger.debug('Rendering templated command: %s', command)

            try:
                # Create temporary file for template rendering
                with tempfile.NamedTemporaryFile(
                    mode='w', suffix='.j2', delete=False
                ) as temp_file:
                    temp_file.write(command)
                    temp_file.flush()

                    temp_path = pathlib.Path(temp_file.name)

                    try:
                        rendered = prompts.render(
                            context, temp_path, **context.model_dump()
                        )
                        self.logger.debug('Rendered command: %s', rendered)
                        return rendered
                    finally:
                        temp_path.unlink()  # Clean up temp file

            except Exception as exc:
                raise ValueError(
                    f'Failed to render command template: {exc}'
                ) from exc

        return command

    @staticmethod
    def _has_template_syntax(command: str) -> bool:
        """Check if command contains Jinja2 templating syntax."""
        # Look for common Jinja2 patterns
        template_patterns = [
            '{{',  # Variable substitution
            '{%',  # Control structures
            '{#',  # Comments
        ]

        return any(pattern in command for pattern in template_patterns)
