"""Git Related Functionality"""

import asyncio
import contextlib
import logging
import pathlib
import shutil
import tempfile
import typing

LOGGER = logging.getLogger(__name__)


async def _run_git_command(
    command: list[str], cwd: pathlib.Path, timeout_seconds: int = 3600
) -> tuple[int, str, str]:
    """
    Run a git command and return return code, stdout, stderr.

    Args:
        command: Git command and arguments
        cwd: Working directory
        timeout_seconds: Timeout in seconds (None for no timeout)

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
            process.communicate(), timeout=timeout_seconds
        )
    except TimeoutError:
        LOGGER.warning(
            'Git command timed out after %d seconds: %s',
            timeout_seconds,
            ' '.join(command),
        )
        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            process.kill()
            await process.wait()
        return -1, '', f'Command timed out after {timeout_seconds} seconds'
    else:
        stdout_str = stdout.decode('utf-8')
        stderr_str = stderr.decode('utf-8')

        if stdout_str:
            LOGGER.debug('STDOUT: %s', stdout_str)
        if stderr_str:
            LOGGER.debug('STDERR: %s', stderr_str)

        return process.returncode, stdout_str, stderr_str


async def clone_repository(
    clone_url: str, branch: str | None = None, depth: int | None = 1
) -> pathlib.Path:
    """Clone a repository to a temporary directory.

    Args:
        clone_url: Repository clone URL (HTTPS or SSH)
        branch: Specific branch to clone (optional)
        depth: Clone depth (default: 1 for shallow clone, None for full clone)

    Returns:
        Path to the cloned repository directory

    Raises:
        RuntimeError: If git clone fails

    """
    temp_dir = pathlib.Path(tempfile.mkdtemp(prefix='imbi-automations-'))
    repo_dir = temp_dir / 'repository'

    LOGGER.debug('Cloning repository %s to %s', clone_url, repo_dir)

    # Build git clone command
    command = ['git', 'clone']

    if depth is not None:
        command.extend(['--depth', str(depth)])

    if branch:
        command.extend(['--branch', branch])

    command.extend([clone_url, str(repo_dir)])

    try:
        returncode, stdout, stderr = await _run_git_command(
            command,
            cwd=temp_dir,
            timeout_seconds=600,  # 10 minute timeout
        )

        if returncode != 0:
            raise RuntimeError(
                f'Git clone failed (exit code {returncode}): '
                f'{stderr or stdout}'
            )

        LOGGER.debug('Successfully cloned repository to %s', repo_dir)
        return repo_dir

    except Exception as exc:
        # Clean up on failure
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(
            f'Failed to clone repository {clone_url}: {exc}'
        ) from exc


@contextlib.asynccontextmanager
async def clone_repository_context(
    clone_url: str, branch: str | None = None, depth: int | None = 1
) -> typing.AsyncGenerator[pathlib.Path, None]:
    """Context manager for cloning a repository with automatic cleanup.

    Args:
        clone_url: Repository clone URL (HTTPS or SSH)
        branch: Specific branch to clone (optional)
        depth: Clone depth (default: 1 for shallow clone, None for full clone)

    Yields:
        Path to the cloned repository directory

    """
    repo_dir = None
    temp_dir = None

    try:
        repo_dir = await clone_repository(clone_url, branch, depth)
        temp_dir = repo_dir.parent
        yield repo_dir

    except Exception as exc:
        LOGGER.error('Repository cloning failed: %s', exc)
        raise

    finally:
        # Clean up temporary directory
        if temp_dir and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
                LOGGER.debug('Cleaned up temporary directory: %s', temp_dir)
            except OSError as exc:
                LOGGER.warning(
                    'Failed to clean up temporary directory %s: %s',
                    temp_dir,
                    exc,
                )


async def add_files(working_directory: pathlib.Path, files: list[str]) -> None:
    """Add files to git staging area.

    Args:
        working_directory: Git repository working directory
        files: List of file paths relative to working directory

    Raises:
        RuntimeError: If git add fails

    """
    if not files:
        LOGGER.debug('No files to add to git staging area')
        return

    LOGGER.debug('Adding %d files to git staging area', len(files))

    # Use git add with multiple files
    command = ['git', 'add'] + files

    returncode, stdout, stderr = await _run_git_command(
        command, cwd=working_directory, timeout_seconds=60
    )

    if returncode != 0:
        raise RuntimeError(
            f'Git add failed (exit code {returncode}): {stderr or stdout}'
        )

    LOGGER.debug('Successfully added %d files to git staging area', len(files))


async def remove_files(
    working_directory: pathlib.Path, files: list[str]
) -> None:
    """Remove files from git tracking and staging area.

    Args:
        working_directory: Git repository working directory
        files: List of file paths relative to working directory

    Raises:
        RuntimeError: If git rm fails

    """
    if not files:
        LOGGER.debug('No files to remove from git tracking')
        return

    LOGGER.debug('Removing %d files from git tracking', len(files))

    # Use git rm with multiple files
    command = ['git', 'rm'] + files

    returncode, stdout, stderr = await _run_git_command(
        command, cwd=working_directory, timeout_seconds=60
    )

    if returncode != 0:
        raise RuntimeError(
            f'Git rm failed (exit code {returncode}): {stderr or stdout}'
        )

    LOGGER.debug('Successfully removed %d files from git tracking', len(files))


async def commit_changes(
    working_directory: pathlib.Path,
    message: str,
    author_name: str | None = None,
    author_email: str | None = None,
) -> str:
    """Commit staged changes to git repository.

    Args:
        working_directory: Git repository working directory
        message: Commit message
        author_name: Optional commit author name
        author_email: Optional commit author email

    Returns:
        Commit SHA hash

    Raises:
        RuntimeError: If git commit fails

    """
    LOGGER.debug('Committing changes with message: %s', message)

    command = ['git', 'commit', '-m', message]

    # Add author information if provided
    if author_name and author_email:
        command.extend(['--author', f'{author_name} <{author_email}>'])

    returncode, stdout, stderr = await _run_git_command(
        command, cwd=working_directory, timeout_seconds=60
    )

    if returncode != 0:
        # Check if it's just "nothing to commit"
        if 'nothing to commit' in stderr or 'nothing to commit' in stdout:
            LOGGER.info('No changes to commit')
            return ''

        raise RuntimeError(
            f'Git commit failed (exit code {returncode}): {stderr or stdout}'
        )

    # Extract commit SHA from output
    commit_sha = ''
    if stdout:
        # Git commit output typically starts with [branch commit_sha]
        import re

        sha_match = re.search(r'\[.*?([a-f0-9]{7,40})\]', stdout)
        if sha_match:
            commit_sha = sha_match.group(1)

    LOGGER.debug(
        'Successfully committed changes: %s', commit_sha or 'unknown SHA'
    )
    return commit_sha


async def get_git_status(working_directory: pathlib.Path) -> list[str]:
    """Get list of modified/untracked files in git repository.

    Args:
        working_directory: Git repository working directory

    Returns:
        List of file paths that have changes

    """
    command = ['git', 'status', '--porcelain']

    returncode, stdout, stderr = await _run_git_command(
        command, cwd=working_directory, timeout_seconds=30
    )

    if returncode != 0:
        raise RuntimeError(
            f'Git status failed (exit code {returncode}): {stderr or stdout}'
        )

    # Parse porcelain output to extract file paths
    changed_files = []
    for line in stdout.split('\n'):
        if line.strip() and len(line) >= 3:
            # Porcelain format: XY filename (where XY are 2-char status codes)
            file_path = line[3:].strip()
            if file_path:
                changed_files.append(file_path)

    LOGGER.debug('Found %d changed files', len(changed_files))
    return changed_files


async def push_changes(
    working_directory: pathlib.Path,
    remote: str = 'origin',
    branch: str | None = None,
    force: bool = False,
) -> None:
    """Push committed changes to remote repository.

    Args:
        working_directory: Git repository working directory
        remote: Remote name (default: 'origin')
        branch: Branch to push (default: current branch)
        force: Force push (default: False)

    Raises:
        RuntimeError: If git push fails

    """
    command = ['git', 'push']

    if force:
        command.append('--force')

    command.append(remote)

    if branch:
        command.append(branch)

    LOGGER.debug(
        'Pushing changes to %s %s', remote, branch or 'current branch'
    )

    returncode, stdout, stderr = await _run_git_command(
        command,
        cwd=working_directory,
        timeout_seconds=300,  # 5 minute timeout
    )

    if returncode != 0:
        raise RuntimeError(
            f'Git push failed (exit code {returncode}): {stderr or stdout}'
        )

    LOGGER.debug(
        'Successfully pushed changes to %s %s',
        remote,
        branch or 'current branch',
    )


async def create_branch(
    working_directory: pathlib.Path, branch_name: str, checkout: bool = True
) -> None:
    """Create a new git branch.

    Args:
        working_directory: Git repository working directory
        branch_name: Name of the new branch to create
        checkout: Whether to checkout the new branch (default: True)

    Raises:
        RuntimeError: If git branch creation fails

    """
    command = (
        ['git', 'checkout', '-b', branch_name]
        if checkout
        else ['git', 'branch', branch_name]
    )

    LOGGER.debug(
        'Creating branch %s in %s (checkout: %s)',
        branch_name,
        working_directory,
        checkout,
    )

    returncode, stdout, stderr = await _run_git_command(
        command, cwd=working_directory, timeout_seconds=30
    )

    if returncode != 0:
        raise RuntimeError(
            f'Git branch creation failed (exit code {returncode}): '
            f'{stderr or stdout}'
        )

    LOGGER.debug('Successfully created branch %s', branch_name)


async def get_current_branch(working_directory: pathlib.Path) -> str:
    """Get the current git branch name.

    Args:
        working_directory: Git repository working directory

    Returns:
        Current branch name

    Raises:
        RuntimeError: If git branch query fails

    """
    command = ['git', 'branch', '--show-current']

    returncode, stdout, stderr = await _run_git_command(
        command, cwd=working_directory, timeout_seconds=30
    )

    if returncode != 0:
        raise RuntimeError(
            f'Git branch query failed (exit code {returncode}): '
            f'{stderr or stdout}'
        )

    branch_name = stdout.strip()
    LOGGER.debug('Current branch: %s', branch_name)
    return branch_name


async def get_commit_messages_since_branch(
    working_directory: pathlib.Path, base_branch: str = 'main'
) -> list[str]:
    """Get commit messages since branching from base branch.

    Args:
        working_directory: Git repository working directory
        base_branch: Base branch to compare against (default: 'main')

    Returns:
        List of commit messages since branching

    Raises:
        RuntimeError: If git log fails

    """
    command = ['git', 'log', f'{base_branch}..HEAD', '--pretty=format:%s']

    returncode, stdout, stderr = await _run_git_command(
        command, cwd=working_directory, timeout_seconds=30
    )

    if returncode != 0:
        # If base_branch doesn't exist, try origin/main
        if 'unknown revision' in stderr.lower():
            command = [
                'git',
                'log',
                f'origin/{base_branch}..HEAD',
                '--pretty=format:%s',
            ]
            returncode, stdout, stderr = await _run_git_command(
                command, cwd=working_directory, timeout=30
            )

        if returncode != 0:
            raise RuntimeError(
                f'Git log failed (exit code {returncode}): {stderr or stdout}'
            )

    if not stdout.strip():
        return []

    commit_messages = [
        msg.strip() for msg in stdout.split('\n') if msg.strip()
    ]
    LOGGER.debug(
        'Found %d commit messages since %s', len(commit_messages), base_branch
    )
    return commit_messages
