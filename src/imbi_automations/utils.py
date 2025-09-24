import logging
import pathlib
import re
import tomllib
import typing

import pydantic

LOGGER = logging.getLogger(__name__)


class Utils:
    """Utility client for file operations and other utility functions."""

    @staticmethod
    def compare_versions_with_build_numbers(
        current_version: str, target_version: str
    ) -> bool:
        """Compare versions including build numbers.

        Handles semantic versions with optional build numbers in the format:
        "major.minor.patch" or "major.minor.patch-build"

        Args:
            current_version: Current version (e.g., "3.9.18-0")
            target_version: Target version (e.g., "3.9.18-4")

        Returns:
            True if current_version is older than target_version

        Examples:
            compare_versions_with_build_numbers("3.9.18-0", "3.9.18-4") → True
            compare_versions_with_build_numbers("3.9.17-4", "3.9.18-0") → True
            compare_versions_with_build_numbers("3.9.18-4", "3.9.18-0") → False

        """
        import semver

        # Split versions into semantic version and build number
        if '-' in current_version:
            current_sem, current_build_str = current_version.rsplit('-', 1)
            try:
                current_build = int(current_build_str)
            except ValueError:
                current_build = 0
        else:
            current_sem = current_version
            current_build = 0

        if '-' in target_version:
            target_sem, target_build_str = target_version.rsplit('-', 1)
            try:
                target_build = int(target_build_str)
            except ValueError:
                target_build = 0
        else:
            target_sem = target_version
            target_build = 0

        # Compare semantic versions first
        current_version_obj = semver.Version.parse(current_sem)
        target_version_obj = semver.Version.parse(target_sem)
        sem_comparison = current_version_obj.compare(target_version_obj)

        if sem_comparison < 0:
            # Current semantic version is older
            return True
        elif sem_comparison > 0:
            # Current semantic version is newer
            return False
        else:
            # Semantic versions are equal, compare build numbers
            return current_build < target_build

    async def append_file(self, file: str, value: str) -> str:
        """Append a value to a file.

        Args:
            file: Path to the file to append to
            value: Content to append to the file

        Returns:
            Status string: 'success' or 'failed'

        """
        try:
            file_path = pathlib.Path(file)

            # Create parent directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Append the value to the file
            with open(file_path, 'a', encoding='utf-8') as f:  # noqa: ASYNC230
                f.write(value)

            LOGGER.debug('Successfully appended to file: %s', file)
            return 'success'

        except (OSError, UnicodeDecodeError) as exc:
            LOGGER.error('Failed to append to file %s: %s', file, exc)
            return 'failed'


def sanitize(url: str | pydantic.AnyUrl) -> str:
    """Mask passwords in URLs for security.

    Args:
        url: Input string that may contain URLs with passwords

    Returns:
        Text with passwords in URLs replaced with asterisks

    """
    pattern = re.compile(r'(\w+?://[^:@]+:)([^@]+)(@)')
    return pattern.sub(r'\1******\3', str(url))


def load_toml(toml_file: typing.TextIO) -> dict:
    """Load TOML data from a file-like object

    Args:
        toml_file: The file-like object to load as TOML

    Raises:
        tomllib.TOMLDecodeError: If TOML parsing fails

    """
    return tomllib.loads(toml_file.read())
