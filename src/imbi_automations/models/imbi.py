import datetime
import typing

import pydantic


class ImbiProjectLink(pydantic.BaseModel):
    id: int | None = None
    project_id: int
    link_type_id: int
    created_by: str
    last_modified_by: str | None = None
    url: str


class ImbiProject(pydantic.BaseModel):
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


class ImbiProjectType(pydantic.BaseModel):
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


class ImbiProjectFactType(pydantic.BaseModel):
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


class ImbiProjectFactTypeEnum(pydantic.BaseModel):
    id: int
    fact_type_id: int
    created_by: str | None = None
    last_modified_by: str | None = None
    value: str
    icon_class: str | None = None
    score: int


class ImbiProjectFact(pydantic.BaseModel):
    fact_type_id: int
    name: str
    recorded_at: datetime.datetime | None = None
    recorded_by: str | None = None
    value: bool | int | float | str | None = None
    ui_options: list[str] = pydantic.Field(default_factory=list)
    score: float | None = 0.0
    weight: float = 0.0
