import logging
import re
import tomllib
import typing

import pydantic

LOGGER = logging.getLogger(__name__)


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
