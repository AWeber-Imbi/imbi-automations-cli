"""Imbi Metadata Cache for loading and caching Imbi data."""

import asyncio
import datetime
import json
import logging
import pathlib
import threading
import typing

import pydantic

from imbi_automations import clients
from imbi_automations.models import configuration, imbi

LOGGER = logging.getLogger(__name__)

# Cache configuration
CACHE_TTL_MINUTES = 15

# Thread-safe singleton lock
_instance_lock = threading.Lock()


class CacheData(pydantic.BaseModel):
    """Cache for data used by the application"""

    last_updated: datetime.datetime = pydantic.Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC)
    )
    environments: list[imbi.ImbiEnvironment]
    project_fact_types: list[imbi.ImbiProjectFactType]
    project_fact_type_enums: list[imbi.ImbiProjectFactTypeEnum]
    project_fact_type_ranges: list[imbi.ImbiProjectFactTypeRange]
    project_types: list[imbi.ImbiProjectType]


class ImbiMetadataCache:
    """Singleton cache for Imbi metadata with automatic refresh."""

    instance: typing.Self | None = None

    def __init__(self, config: configuration.ImbiConfiguration) -> None:
        self.cache_data: CacheData | None = None
        self.cache_file = (
            pathlib.Path.home()
            / '.cache'
            / 'imbi-automations'
            / 'metadata.json'
        )
        self.config = config
        self.imbi_client: clients.Imbi | None = None

    @classmethod
    def get_instance(cls, config: configuration.Configuration) -> typing.Self:
        """Get or create singleton instance (thread-safe).

        Note: This synchronous method is for backward compatibility.
        For new code, prefer using async initialization explicitly.
        """
        if not cls.instance:
            with _instance_lock:
                # Double-check pattern to prevent race condition
                if not cls.instance:
                    cls.instance = cls(config.imbi)
                    # Note: Actual data loading is deferred to first use
                    # to avoid blocking event loop
                    try:
                        asyncio.get_running_loop()
                        # We're in async context - use async init instead
                        LOGGER.warning(
                            'get_instance() called from async context. '
                            'Data will be loaded on first property access.'
                        )
                    except RuntimeError:
                        # No event loop running - load from cache file only
                        # This avoids event loop lifecycle conflicts
                        cls.instance._load_from_file_sync()
        return cls.instance

    def _load_from_file_sync(self) -> None:
        """Load cache data from file synchronously (no API calls)."""
        if self.cache_file.exists():
            with self.cache_file.open('r') as file:
                try:
                    self.cache_data = CacheData.model_validate(json.load(file))
                    LOGGER.debug('Loaded cached Imbi metadata from file')
                except (json.JSONDecodeError, pydantic.ValidationError) as err:
                    LOGGER.warning(
                        'Cache file corrupted, will refresh on first async '
                        'use: %s',
                        err,
                    )
                    # Delete corrupted cache file
                    self.cache_file.unlink(missing_ok=True)
        else:
            LOGGER.debug('No cache file found, will load on first async use')

    def is_cache_expired(self) -> bool:
        """Check if cache has expired (older than CACHE_TTL_MINUTES)."""
        if not self.cache_data:
            return True
        age = (
            datetime.datetime.now(tz=datetime.UTC)
            - self.cache_data.last_updated
        )
        return age > datetime.timedelta(minutes=CACHE_TTL_MINUTES)

    @property
    def environments(self) -> set[str]:
        return {env.name.lower() for env in self.cache_data.environments}

    @property
    def project_fact_type_names(self) -> set[str]:
        return {datum.name for datum in self.cache_data.project_fact_types}

    def project_fact_type_values(self, name: str) -> set[str]:
        fact_type_ids = {
            datum.id
            for datum in self.cache_data.project_fact_types
            if datum.name == name
        }
        LOGGER.debug('Fact Type IDs: %s', fact_type_ids)
        return {
            datum.value
            for datum in self.cache_data.project_fact_type_enums
            if datum.fact_type_id in fact_type_ids
        }

    @property
    def project_type_slugs(self) -> set[str]:
        return {
            project_type.slug for project_type in self.cache_data.project_types
        }

    async def _load_data(self) -> None:
        """Load the Imbi data from the API or cache file."""
        if self.cache_file.exists():
            with self.cache_file.open('r') as file:
                try:
                    self.cache_data = CacheData.model_validate(json.load(file))
                except (json.JSONDecodeError, pydantic.ValidationError) as err:
                    LOGGER.warning(
                        'Cache file corrupted, regenerating: %s', err
                    )
                    # Delete corrupted cache file
                    self.cache_file.unlink(missing_ok=True)
                else:
                    # Check if cache is still fresh
                    if not self.is_cache_expired():
                        LOGGER.debug('Using cached Imbi metadata')
                        return

        # Get or create Imbi client for this event loop
        if not self.imbi_client:
            self.imbi_client = clients.Imbi.get_instance(config=self.config)

        (
            environments,
            project_fact_types,
            project_fact_type_enums,
            project_fact_type_ranges,
            project_types,
        ) = await asyncio.gather(
            self.imbi_client.get_environments(),
            self.imbi_client.get_project_fact_types(),
            self.imbi_client.get_project_fact_type_enums(),
            self.imbi_client.get_project_fact_type_ranges(),
            self.imbi_client.get_project_types(),
        )

        self.cache_data = CacheData(
            environments=environments,
            project_fact_types=project_fact_types,
            project_fact_type_enums=project_fact_type_enums,
            project_fact_type_ranges=project_fact_type_ranges,
            project_types=project_types,
        )
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_file.open('w') as file:
            file.write(self.cache_data.model_dump_json())
