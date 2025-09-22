"""Git Related Functionality"""

import asyncio
import logging
import pathlib

LOGGER = logging.getLogger(__name__)


async def _run_git_command(
    command: list[str],
    cwd: pathlib.Path,
    timeout: int = 3600,  # noqa: ASYNC109
) -> tuple[int, str, str]:
    """
    Run a git command and return return code, stdout, stderr.

    Args:
        command: Git command and arguments
        cwd: Working directory
        timeout: Timeout in seconds (None for no timeout)

    """
    LOGGER.debug('Running git command: %s', ' '.join(command))

    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except TimeoutError:
        LOGGER.warning(
            'Git command timed out after %d seconds: %s',
            timeout,
            ' '.join(command),
        )
        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            process.kill()
            await process.wait()
        return -1, '', f'Command timed out after {timeout} seconds'
    else:
        stdout_str = stdout.decode('utf-8')
        stderr_str = stderr.decode('utf-8')

        if stdout_str:
            LOGGER.debug('STDOUT: %s', stdout_str)
        if stderr_str:
            LOGGER.debug('STDERR: %s', stderr_str)

        return process.returncode, stdout_str, stderr_str
