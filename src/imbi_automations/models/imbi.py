"""Imbi project management system API models.

Defines Pydantic models for Imbi API responses including projects, project
types, environments, links, facts, and other project metadata used for
workflow targeting and context enrichment.
"""

import datetime
import typing

import pydantic

from . import base


class ImbiProjectLink(base.BaseModel):
    """External link associated with an Imbi project.

    Represents links to external systems like GitHub, GitLab, PagerDuty, etc.
    """

    id: int | None = None
    project_id: int
    link_type_id: int
    created_by: str
    last_modified_by: str | None = None
    url: str


class ImbiProject(base.BaseModel):
    """Imbi project with metadata and external system integrations.

    Complete project definition including dependencies, facts, identifiers
    for external systems, and links to related services.
    """

    id: int
    dependencies: list[int] | None
    description: str | None
    environments: list[str] | None
    facts: dict[str, typing.Any] | None
    identifiers: dict[str, typing.Any] | None
    links: dict[str, str] | None
    name: str
    namespace: str
    namespace_slug: str
    project_score: str | None
    project_type: str
    project_type_slug: str
    slug: str
    urls: dict[str, str] | None
    imbi_url: str


class ImbiProjectType(base.BaseModel):
    """Project type definition in Imbi.

    Categorizes projects with metadata for icon display, environment URL
    support, and GitLab project prefix configuration.
    """

    id: int
    created_by: str | None = None
    last_modified_by: str | None = None
    name: str
    plural_name: str
    description: str | None = None
    slug: str
    icon_class: str
    environment_urls: bool = False
    gitlab_project_prefix: str | None = None


class ImbiProjectFactType(base.BaseModel):
    """Definition of a project fact type with validation rules.

    Defines metadata schema for project facts including data type
    (boolean, integer, number, string), fact type (enum, free-form,
    range), and UI options.
    """

    id: int
    created_by: str | None = None
    last_modified_by: str | None = None
    name: str
    project_type_ids: list[int] = pydantic.Field(default_factory=list)
    fact_type: str  # enum, free-form, range
    description: str | None = None
    data_type: str  # boolean, integer, number, string
    ui_options: list[str] = pydantic.Field(default_factory=list)
    weight: float = 0.0


class ImbiProjectFactTypeEnum(base.BaseModel):
    """Enumerated value option for enum-type project facts.

    Defines a single allowed value for enum fact types with optional icon
    and scoring information.
    """

    id: int
    fact_type_id: int
    created_by: str | None = None
    last_modified_by: str | None = None
    value: str
    icon_class: str | None = None
    score: int


class ImbiProjectFact(base.BaseModel):
    """Individual fact value for a project.

    Represents a single fact value recorded for a project with scoring,
    weighting, and audit information.
    """

    fact_type_id: int
    name: str
    recorded_at: datetime.datetime | None = None
    recorded_by: str | None = None
    value: bool | int | float | str | None = None
    ui_options: list[str] = pydantic.Field(default_factory=list)
    score: float | None = 0.0
    weight: float = 0.0
