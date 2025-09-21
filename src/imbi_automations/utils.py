import logging
import pathlib
import re
import tomllib

import pydantic

from imbi_automations import models

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


def ensure_directory_exists(directory_path: pathlib.Path) -> None:
    """Ensure a directory exists, creating it and parent directories if needed.

    Args:
        directory_path: Path to the directory to create

    Raises:
        OSError: If directory creation fails

    """
    if not directory_path.exists():
        try:
            directory_path.mkdir(parents=True, exist_ok=True)
            LOGGER.debug('Created directory: %s', directory_path)
        except OSError as exc:
            LOGGER.error(
                'Failed to create directory %s: %s', directory_path, exc
            )
            raise


def load_configuration(config_file: pathlib.Path) -> models.Configuration:
    """Load configuration from config file

    Args:
        config_file: Path to the main configuration file

    Returns:
        Configuration object with merged data

    Raises:
        tomllib.TOMLDecodeError: If TOML parsing fails
        pydantic.ValidationError: If configuration validation fails

    """
    with config_file.open('rb') as f:
        config_data = tomllib.load(f)
    return models.Configuration.model_validate(config_data)
