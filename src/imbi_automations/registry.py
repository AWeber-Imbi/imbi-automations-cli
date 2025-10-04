"""Imbi Data Registry, tool for loading and caching Imbi data"""

import asyncio
import datetime
import json
import logging
import pathlib
import typing

import pydantic

from imbi_automations import clients
from imbi_automations.models import configuration, imbi

LOGGER = logging.getLogger(__name__)


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


class Registry:
    instance: typing.Self | None = None

    def __init__(self, config: configuration.ImbiConfiguration) -> None:
        self.cache_data: CacheData | None = None
        self.cache_file = (
            pathlib.Path.home()
            / '.cache'
            / 'imbi-automations'
            / 'registry.json'
        )
        self.imbi_client = clients.Imbi.get_instance(config=config)

    @classmethod
    def get_instance(cls, config: configuration.Configuration) -> typing.Self:
        if not cls.instance:
            cls.instance = cls(config.imbi)
            loop = asyncio.get_event_loop()
            loop.run_until_complete(cls.instance._load_data())
            loop.run_until_complete(clients.Imbi.get_instance().aclose())
        return cls.instance

    @property
    def cache_expiration(self) -> datetime.datetime:
        return datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(
            minutes=15
        )

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
        """Load the Imbi data from the API"""
        if self.cache_file.exists():
            with self.cache_file.open('r') as file:
                try:
                    self.cache_data = CacheData.model_validate(json.load(file))
                except (json.JSONDecodeError, pydantic.ValidationError) as err:
                    LOGGER.debug('Registry cache is invalid: %s', err)
                else:
                    if self.cache_data.last_updated > self.cache_expiration:
                        return

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
