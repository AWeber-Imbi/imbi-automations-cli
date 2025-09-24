"""Docker operations for workflow actions."""

import logging
import pathlib
import re
import subprocess

LOGGER = logging.getLogger(__name__)


async def extract_docker_image_from_dockerfile(
    dockerfile_path: pathlib.Path,
) -> str | None:
    """Extract Docker image name from Dockerfile FROM line.

    Args:
        dockerfile_path: Path to Dockerfile

    Returns:
        Docker image name or None if not found

    """
    try:
        content = dockerfile_path.read_text(encoding='utf-8')

        # Look for FROM line with image name
        from_match = re.search(r'^FROM\s+([^\s]+)', content, re.MULTILINE)

        if from_match:
            image_name = from_match.group(1)
            LOGGER.debug(
                'Extracted Docker image from %s: %s',
                dockerfile_path,
                image_name,
            )
            return image_name
        else:
            LOGGER.warning(
                'No FROM line found in Dockerfile: %s', dockerfile_path
            )
            return None

    except (OSError, UnicodeDecodeError) as exc:
        LOGGER.error('Failed to read Dockerfile %s: %s', dockerfile_path, exc)
        return None


async def extract_file_from_docker_image(
    image_name: str, source_path: str, timeout_seconds: int = 60
) -> str | None:
    """Extract file content from a Docker image.

    Args:
        image_name: Docker image name (e.g., "python3-service:3.12.10-5")
        source_path: Path to file inside the container
        timeout_seconds: Timeout for Docker command

    Returns:
        File content as string, or None if extraction fails

    """
    LOGGER.debug(
        'Extracting file %s from Docker image %s', source_path, image_name
    )

    # Use docker run to extract file content
    command = [
        'docker',
        'run',
        '--rm',
        '--entrypoint=cat',
        image_name,
        source_path,
    ]

    try:
        # Use asyncio subprocess for non-blocking execution
        import asyncio

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout_seconds
        )

        stdout_str = stdout.decode('utf-8') if stdout else ''
        stderr_str = stderr.decode('utf-8') if stderr else ''
        returncode = process.returncode or 0

        if returncode == 0:
            LOGGER.debug(
                'Successfully extracted %d bytes from %s in image %s',
                len(stdout_str),
                source_path,
                image_name,
            )
            return stdout_str
        else:
            # Check if it's a "file not found" error vs other Docker issues
            if 'no such file or directory' in stderr_str.lower():
                LOGGER.debug(
                    'File %s not found in Docker image %s',
                    source_path,
                    image_name,
                )
                return None
            elif 'unable to find image' in stderr_str.lower() or 'not found' in stderr_str.lower():
                LOGGER.error(
                    'Docker image %s not available locally or accessible: %s',
                    image_name,
                    stderr_str,
                )
                error_msg = f'Docker image not available: {image_name}'
                raise RuntimeError(f'Docker extraction failed: {error_msg}')
            else:
                LOGGER.error(
                    'Docker extraction failed for %s from %s: %s',
                    source_path,
                    image_name,
                    stderr_str or stdout_str,
                )
                error_msg = stderr_str or stdout_str
                raise RuntimeError(f'Docker extraction failed: {error_msg}')

    except TimeoutError:
        LOGGER.error(
            'Docker extraction timed out after %d seconds for %s from %s',
            timeout_seconds,
            source_path,
            image_name,
        )
        raise RuntimeError(
            f'Docker extraction timed out after {timeout_seconds} seconds'
        ) from None

    except (OSError, subprocess.SubprocessError) as exc:
        LOGGER.error(
            'Docker command failed for %s from %s: %s',
            source_path,
            image_name,
            exc,
        )
        raise RuntimeError(f'Docker command failed: {exc}') from exc


def parse_constraints_file(content: str) -> list[str]:
    """Parse constraints file content to extract package names.

    Args:
        content: Content of constraints file

    Returns:
        List of package names (without version constraints)

    """
    packages = []
    for line in content.split('\n'):
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith('#'):
            continue

        # Extract package name (before ==, >=, <=, etc.)
        package_match = re.match(r'^([a-zA-Z0-9_.-]+)', line)
        if package_match:
            package_name = package_match.group(1)
            packages.append(package_name)

    LOGGER.debug(
        'Parsed %d packages from constraints file: %s',
        len(packages),
        packages[:10] if len(packages) > 10 else packages,  # Show first 10
    )

    return packages
