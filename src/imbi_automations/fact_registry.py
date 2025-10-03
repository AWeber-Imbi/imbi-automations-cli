"""Imbi fact type registry with validation and caching.

Manages project fact types loaded from Imbi API, provides name normalization,
value validation, and disk caching for performance.
"""

import datetime
import json
import logging
import pathlib
import typing

import pydantic

from imbi_automations import clients, models

LOGGER = logging.getLogger(__name__)


class FactTypeDefinition(pydantic.BaseModel):
    """Complete fact type definition with validation rules.

    Combines fact type metadata with enum values and range constraints for
    comprehensive validation of fact values.
    """

    id: int
    name: str
    slug: str
    fact_type: typing.Literal['enum', 'range', 'free-form']
    data_type: typing.Literal[
        'boolean', 'date', 'decimal', 'integer', 'string', 'timestamp'
    ]
    project_type_ids: list[int] = pydantic.Field(default_factory=list)

    # Enum constraints (for fact_type="enum")
    enum_values: list[typing.Any] | None = None

    # Range constraints (for fact_type="range")
    min_value: float | None = None
    max_value: float | None = None

    # Metadata
    ui_options: list[str] = pydantic.Field(default_factory=list)
    weight: float = 0.0
    description: str | None = None

    def validate_value(self, value: typing.Any) -> tuple[bool, str | None]:
        """Validate value against fact type constraints.

        Args:
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.

        """
        # Step 1: Coerce to correct data type
        try:
            typed_value = self._coerce_value(value)
        except (ValueError, TypeError) as exc:
            return False, f'Cannot convert to {self.data_type}: {exc}'

        # Step 2: Apply fact_type validation
        if self.fact_type == 'enum':
            if self.enum_values is None:
                return False, 'Enum values not loaded for enum fact type'

            if typed_value not in self.enum_values:
                enum_list = ', '.join(map(str, self.enum_values))
                return (False, f'Value must be one of: {enum_list}')

        elif self.fact_type == 'range':
            if self.min_value is None or self.max_value is None:
                return False, 'Range bounds not defined for range fact type'

            if not isinstance(typed_value, int | float):
                return False, 'Range fact requires numeric value'

            if not (self.min_value <= typed_value <= self.max_value):
                msg = (
                    f'Value must be between '
                    f'{self.min_value} and {self.max_value}'
                )
                return (False, msg)

        # free-form: no additional validation

        return True, None

    def _coerce_value(self, value: typing.Any) -> typing.Any:
        """Coerce value to the correct data type.

        Args:
            value: Raw value from workflow config

        Returns:
            Value coerced to correct type

        Raises:
            ValueError: If coercion fails

        """
        if self.data_type == 'boolean':
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                if value.lower() in ('true', '1', 'yes'):
                    return True
                if value.lower() in ('false', '0', 'no'):
                    return False
            raise ValueError(f'Cannot convert {value!r} to boolean')

        elif self.data_type == 'integer':
            return int(value)

        elif self.data_type == 'decimal':
            return float(value)

        elif self.data_type == 'string':
            return str(value)

        elif self.data_type in ('date', 'timestamp'):
            # ISO format validation
            if isinstance(value, str):
                # Basic ISO format check
                try:
                    if self.data_type == 'date':
                        datetime.date.fromisoformat(value)
                    else:  # timestamp
                        datetime.datetime.fromisoformat(
                            value.replace('Z', '+00:00')
                        )
                    return value
                except ValueError as exc:
                    raise ValueError(
                        f'Invalid ISO format for {self.data_type}: {exc}'
                    ) from exc
            raise ValueError(f'{self.data_type} must be ISO format string')

        raise ValueError(f'Unknown data type: {self.data_type}')


class FactRegistry:
    """Registry of Imbi fact types with validation and caching.

    Loads fact type metadata from Imbi API or disk cache, provides name
    normalization and value validation.
    """

    def __init__(self, cache_file: str = 'fact-cache.json') -> None:
        self.facts_by_id: dict[int, FactTypeDefinition] = {}
        self.facts_by_slug: dict[str, list[FactTypeDefinition]] = {}
        self.slug_to_name: dict[str, str] = {}
        self.name_to_slug: dict[str, str] = {}
        self.project_type_slugs: set[str] = set()
        self._cache_dir = pathlib.Path.home() / '.imbi-automations'
        self._cache_file = self._cache_dir / cache_file
        self._hostname: str | None = None

    @classmethod
    async def load(
        cls,
        imbi_client: 'models.Imbi',
        use_cache: bool = True,
        cache_ttl_hours: int = 24,
    ) -> 'FactRegistry':
        """Load fact types from cache or Imbi API.

        Args:
            imbi_client: Imbi API client instance
            use_cache: Whether to use cached data
            cache_ttl_hours: Cache time-to-live in hours

        Returns:
            Loaded FactRegistry instance

        """
        registry = cls()
        registry._hostname = imbi_client.base_url

        # Try loading from cache
        if use_cache and registry._is_cache_valid(cache_ttl_hours):
            try:
                registry._load_from_cache()
                LOGGER.debug('Loaded fact types from cache')
                return registry
            except (OSError, json.JSONDecodeError, KeyError) as exc:
                LOGGER.warning(
                    'Failed to load cache, fetching from API: %s', exc
                )

        # Load from API
        await registry._load_from_api(imbi_client)
        registry._save_to_cache()

        return registry

    def _is_cache_valid(self, ttl_hours: int) -> bool:
        """Check if cache file exists and is within TTL."""
        if not self._cache_file.exists():
            return False

        try:
            with open(self._cache_file) as f:
                cache_data = json.load(f)

            # Check hostname match
            if cache_data.get('hostname') != self._hostname:
                return False

            # Check age
            cached_at = datetime.datetime.fromisoformat(
                cache_data['cached_at']
            )
            age = datetime.datetime.now(datetime.UTC) - cached_at
            return age.total_seconds() < (ttl_hours * 3600)

        except (KeyError, ValueError) as exc:
            LOGGER.warning('Invalid cache file: %s', exc)
            return False

    def _load_from_cache(self) -> None:
        """Load fact types and project types from cache file."""
        with open(self._cache_file) as f:
            cache_data = json.load(f)

        # Load project type slugs
        self.project_type_slugs = set(cache_data.get('project_type_slugs', []))

        for fact_data in cache_data['fact_types']:
            fact_def = FactTypeDefinition.model_validate(fact_data)
            self._register_fact(fact_def)

    async def _load_from_api(self, imbi_client: clients.Imbi) -> None:
        """Load fact types and project types from Imbi API."""
        # Load project types
        project_types = await imbi_client.get_project_types()
        self.project_type_slugs = {pt.slug for pt in project_types}

        # Load fact types
        fact_types = await imbi_client.get_fact_types()

        # Load enum values
        fact_enums = await imbi_client.get_fact_type_enums()

        # Group enums by fact_type_id
        enums_by_type: dict[int, list[typing.Any]] = {}
        for enum in fact_enums:
            if enum.fact_type_id not in enums_by_type:
                enums_by_type[enum.fact_type_id] = []
            enums_by_type[enum.fact_type_id].append(enum.value)

        # Build FactTypeDefinitions
        for fact_type in fact_types:
            slug = self.normalize_name(fact_type.name)
            enum_values = enums_by_type.get(fact_type.id)

            fact_def = FactTypeDefinition(
                id=fact_type.id,
                name=fact_type.name,
                slug=slug,
                fact_type=fact_type.fact_type,
                data_type=fact_type.data_type,
                project_type_ids=fact_type.project_type_ids,
                enum_values=enum_values,
                ui_options=fact_type.ui_options,
                weight=fact_type.weight,
            )

            self._register_fact(fact_def)

        LOGGER.info(
            'Loaded %d fact types from Imbi API', len(self.facts_by_id)
        )

    def _register_fact(self, fact_def: FactTypeDefinition) -> None:
        """Register a fact type in the registry.

        Handles multiple fact types with the same name (different IDs
        for different project types).
        """
        self.facts_by_id[fact_def.id] = fact_def

        # Multiple facts can have the same slug
        if fact_def.slug not in self.facts_by_slug:
            self.facts_by_slug[fact_def.slug] = []
        self.facts_by_slug[fact_def.slug].append(fact_def)

        self.slug_to_name[fact_def.slug] = fact_def.name
        self.name_to_slug[fact_def.name] = fact_def.slug

    def _save_to_cache(self) -> None:
        """Save fact types to cache file."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        cache_data = {
            'version': 1,
            'hostname': self._hostname,
            'cached_at': datetime.datetime.now(datetime.UTC).isoformat(),
            'project_type_slugs': sorted(self.project_type_slugs),
            'fact_types': [
                fact.model_dump() for fact in self.facts_by_id.values()
            ],
        }

        with open(self._cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)

        LOGGER.debug('Saved fact types to cache: %s', self._cache_file)

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize fact name to slug format.

        Args:
            name: Fact name (e.g., "Programming Language")

        Returns:
            Slug (e.g., "programming_language")

        """
        return name.lower().replace(' ', '_').replace('-', '_')

    def get_fact(self, name_or_slug: str) -> FactTypeDefinition | None:
        """Get first fact type by name or slug.

        Args:
            name_or_slug: Fact name or slug

        Returns:
            First matching FactTypeDefinition or None if not found

        Note: For fact names with multiple definitions (different project
        types), use get_facts() to get all matching definitions.
        """
        facts = self.get_facts(name_or_slug)
        return facts[0] if facts else None

    def get_facts(self, name_or_slug: str) -> list[FactTypeDefinition]:
        """Get all fact types matching name or slug.

        Args:
            name_or_slug: Fact name or slug

        Returns:
            List of matching FactTypeDefinitions (multiple for same name)

        """
        slug = self.normalize_name(name_or_slug)
        return self.facts_by_slug.get(slug, [])

    def validate_value(
        self, fact_name: str, value: typing.Any
    ) -> tuple[bool, str | None]:
        """Validate value for a specific fact.

        Args:
            fact_name: Fact name or slug
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)

        """
        fact_def = self.get_fact(fact_name)
        if not fact_def:
            return False, f'Unknown fact type: {fact_name}'

        return fact_def.validate_value(value)
