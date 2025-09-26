import enum
import pathlib
import typing

import pydantic

from . import github, gitlab, imbi


class WorkflowActionKwargs(pydantic.BaseModel):
    """Dynamic kwargs for workflow actions."""

    model_config = pydantic.ConfigDict(extra='allow')


class WorkflowActionValue(pydantic.BaseModel):
    """Configuration for retrieving a value via client method call."""

    client: str
    method: str
    kwargs: WorkflowActionKwargs = pydantic.Field(
        default_factory=WorkflowActionKwargs
    )


class WorkflowActionTarget(pydantic.BaseModel):
    """Configuration for updating a target via client method call."""

    client: str
    method: str
    kwargs: WorkflowActionKwargs = pydantic.Field(
        default_factory=WorkflowActionKwargs
    )


class WorkflowActionTypes(enum.StrEnum):
    """Enumeration of supported workflow action types."""

    callable = 'callable'
    templates = 'templates'
    file = 'file'
    claude = 'claude'
    shell = 'shell'
    ai_editor = 'ai-editor'
    git_revert = 'git-revert'
    git_extract = 'git-extract'
    docker_extract = 'docker-extract'
    add_trailing_whitespace = 'add-trailing-whitespace'


class WorkflowConditionType(enum.StrEnum):
    """Enumeration of supported condition logic types."""

    all = 'all'
    any = 'any'


class WorkflowAction(pydantic.BaseModel):
    """A single action in a workflow."""

    name: str
    type: WorkflowActionTypes = WorkflowActionTypes.callable
    value: WorkflowActionValue | None = None
    target: WorkflowActionTarget | str | None = None
    value_mapping: dict[str, str] | None = None

    # Conditional execution - action only runs if condition is met
    condition: str | None = None

    # Rich conditions - same options as top-level conditions
    conditions: list['WorkflowCondition'] = pydantic.Field(
        default_factory=list
    )
    condition_type: WorkflowConditionType = WorkflowConditionType.all

    # File action fields
    command: str | None = None
    source: str | None = None
    destination: str | None = None
    pattern: str | None = None
    replacement: str | None = None

    # Claude action fields
    prompt_file: str | None = None  # Legacy single prompt (deprecated)
    prompt: str | None = None  # Primary prompt file (generator for agents)
    validation_prompt: str | None = (
        None  # Validator prompt file (enables agent mode)
    )
    timeout: int = 3600
    max_retries: int | None = None
    on_failure: str | None = None  # Action name to restart from on failure
    max_cycles: int = 3  # Maximum generation→validation cycles

    # AI Editor action fields
    target_file: str | None = None

    # Git revert action fields
    keyword: str | None = None
    strategy: str | None = None  # before_first_match, before_last_match
    # target_path: If specified, save reverted content to different file

    # Docker extract action fields
    dockerfile_path: str | None = None
    source_path: str | None = None
    target_path: str | None = None


class WorkflowCondition(pydantic.BaseModel):
    """A single condition in a workflow."""

    # Local conditions (require cloned repository)
    file_exists: str | None = None
    file_not_exists: str | None = None
    file_contains: str | None = None
    file: str | None = None

    # Remote conditions (checked before cloning using GitHub API)
    remote_file_exists: str | None = None
    remote_file_not_exists: str | None = None
    remote_file_contains: str | None = None
    remote_file: str | None = None


class WorkflowFilter(pydantic.BaseModel):
    project_ids: list[int] = pydantic.Field(default_factory=list)
    project_types: list[str] = pydantic.Field(default_factory=list)
    project_facts: dict[str, str] = pydantic.Field(default_factory=dict)
    project_environments: list[str] = pydantic.Field(default_factory=list)
    requires_github_identifier: bool = False
    exclude_github_workflow_status: list[str] = pydantic.Field(
        default_factory=list
    )


class WorkflowConfiguration(pydantic.BaseModel):
    name: str
    description: str | None = None
    filter: WorkflowFilter | None = None
    ci_skip_checks: bool = False
    clone_repository: bool = True
    shallow_clone: bool = True
    commit_author_trailer: str = (
        'Authored-By: Imbi Automations <noreply@aweber.com>'
    )
    condition_type: WorkflowConditionType = WorkflowConditionType.all
    conditions: list[WorkflowCondition] = pydantic.Field(default_factory=list)
    create_pull_request: bool = True
    actions: list[WorkflowAction] = pydantic.Field(default_factory=list)


class Workflow(pydantic.BaseModel):
    path: pathlib.Path
    configuration: WorkflowConfiguration


class WorkflowRun(pydantic.BaseModel):
    workflow: Workflow
    working_directory: pathlib.Path | None = None
    github_repository: github.GitHubRepository | None = None
    gitlab_project: gitlab.GitLabProject | None = None
    imbi_project: imbi.ImbiProject


class WorkflowContext(pydantic.BaseModel):
    """Template context for workflow execution with type safety."""

    # Core workflow objects
    workflow: Workflow
    workflow_run: WorkflowRun

    # Repository/project information
    github_repository: github.GitHubRepository | None = None
    gitlab_project: gitlab.GitLabProject | None = None
    imbi_project: imbi.ImbiProject

    # Execution context
    working_directory: pathlib.Path | None = None
    actions: typing.Any = None  # ActionResults object from engine

    # Runtime state (added during execution)
    previous_failure: str | None = None

    class Config:
        # Allow arbitrary types for actions (ActionResults)
        arbitrary_types_allowed = True
