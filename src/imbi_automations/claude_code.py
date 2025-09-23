"""Claude Code integration for workflow actions."""

import asyncio
import logging
import os
import pathlib
import subprocess
import time
import typing

from imbi_automations import models

LOGGER = logging.getLogger(__name__)


class ClaudeCode:
    """Claude Code client for executing AI-powered code transformations."""

    def __init__(
        self,
        config: models.ClaudeCodeConfiguration,
        working_directory: pathlib.Path,
    ) -> None:
        """Initialize Claude Code client.

        Args:
            config: Claude Code configuration
            working_directory: Repository working directory for execution

        """
        self.config = config
        self.working_directory = working_directory

    async def execute_prompt(
        self,
        prompt_content: str,
        timeout_seconds: int = 600,
        max_retries: int = 3,
    ) -> dict[str, typing.Any]:
        """Execute Claude Code with the specified prompt.

        Args:
            prompt_content: Prompt text to send to Claude Code
            timeout_seconds: Timeout in seconds (default: 600)
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            Dictionary with execution results:
            - status: 'success' or 'failed'
            - stdout: Command output
            - stderr: Error output
            - return_code: Process exit code
            - execution_time: Time taken in seconds
            - attempts: Number of attempts made

        """
        start_time = time.time()
        last_error = None

        for attempt in range(1, max_retries + 1):
            LOGGER.debug(
                'Claude Code attempt %d/%d (timeout: %ds)',
                attempt,
                max_retries,
                timeout_seconds,
            )

            try:
                return_code, stdout, stderr = await self._run_claude_command(
                    prompt_content, timeout_seconds
                )

                execution_time = time.time() - start_time

                if return_code == 0:
                    LOGGER.debug(
                        'Claude Code succeeded on attempt %d (%.2fs)',
                        attempt,
                        execution_time,
                    )

                    # Log stdout and stderr for debugging even on success
                    if stdout.strip():
                        LOGGER.debug('Claude Code stdout:\n%s', stdout)
                    if stderr.strip():
                        LOGGER.debug('Claude Code stderr:\n%s', stderr)

                    return {
                        'status': 'success',
                        'stdout': stdout,
                        'stderr': stderr,
                        'return_code': return_code,
                        'execution_time': execution_time,
                        'attempts': attempt,
                    }

                last_error = f'Exit code {return_code}: {stderr or stdout}'
                LOGGER.warning(
                    'Claude Code attempt %d/%d failed: %s',
                    attempt,
                    max_retries,
                    last_error,
                )

                # Wait before retry (progressive delay)
                if attempt < max_retries:
                    await asyncio.sleep(attempt)

            except (
                TimeoutError,
                OSError,
                subprocess.CalledProcessError,
            ) as exc:
                last_error = str(exc)
                LOGGER.error(
                    'Claude Code attempt %d/%d error: %s',
                    attempt,
                    max_retries,
                    last_error,
                )

                # Wait before retry
                if attempt < max_retries:
                    await asyncio.sleep(attempt)

        # All attempts failed
        execution_time = time.time() - start_time
        LOGGER.error(
            'Claude Code failed after %d attempts (%.2fs): %s',
            max_retries,
            execution_time,
            last_error,
        )

        return {
            'status': 'failed',
            'stdout': '',
            'stderr': last_error or 'Unknown error',
            'return_code': -1,
            'execution_time': execution_time,
            'attempts': max_retries,
        }

    async def _run_claude_command(
        self, prompt_content: str, timeout_seconds: int
    ) -> tuple[int, str, str]:
        """Execute Claude Code command with prompt content.

        Args:
            prompt_content: Complete prompt content to send
            timeout_seconds: Timeout in seconds

        Returns:
            Tuple of (return_code, stdout, stderr)

        """
        # Prepend base prompt if configured
        final_prompt = prompt_content
        if self.config.base_prompt and self.config.base_prompt.exists():
            try:
                base_content = self.config.base_prompt.read_text(
                    encoding='utf-8'
                )
                final_prompt = base_content + '\n\n' + prompt_content
                LOGGER.debug(
                    'Prepended base prompt from %s', self.config.base_prompt
                )
            except (OSError, UnicodeDecodeError) as exc:
                LOGGER.warning(
                    'Failed to read base prompt %s: %s',
                    self.config.base_prompt,
                    exc,
                )

        # Build Claude Code command
        command = [
            str(self.config.executable),
            '--permission-mode',
            'acceptEdits',
            '--mcp-config',
            '{"mcpServers": {}}',
            '--strict-mcp-config',
        ]

        LOGGER.debug(
            'Running Claude Code: %s (cwd: %s)',
            ' '.join(command),
            self.working_directory,
        )

        # Set environment variables for optimal performance
        env = {
            **os.environ,
            'DISABLE_AUTOUPDATER': '1',
            'DISABLE_NON_ESSENTIAL_MODEL_CALLS': '1',
            'CLAUDE_DISABLE_METRICS': '1',
            'CLAUDE_DISABLE_TELEMETRY': '1',
        }

        # Execute command
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=self.working_directory,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=final_prompt.encode('utf-8')),
                timeout=timeout_seconds,
            )

            stdout_str = stdout.decode('utf-8') if stdout else ''
            stderr_str = stderr.decode('utf-8') if stderr else ''

            return process.returncode or 0, stdout_str, stderr_str

        except TimeoutError:
            LOGGER.warning(
                'Claude Code command timed out after %d seconds',
                timeout_seconds,
            )
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except TimeoutError:
                process.kill()
                await process.wait()

            return -1, '', f'Command timed out after {timeout_seconds} seconds'
