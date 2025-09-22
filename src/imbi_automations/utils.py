import logging
import pathlib
import re
import tomllib
import typing

import pydantic

LOGGER = logging.getLogger(__name__)


class Utils:
    """Utility client for file operations and other utility functions."""

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

        except Exception as exc:  # noqa: BLE001
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
