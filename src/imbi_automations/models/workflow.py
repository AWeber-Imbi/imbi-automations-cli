import enum
import pathlib

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
    project_ids: set[int] = pydantic.Field(default_factory=set)
    project_types: set[str] = pydantic.Field(default_factory=set)
    project_facts: dict[str, str] = pydantic.Field(default_factory=dict)
    project_environments: set[str] = pydantic.Field(default_factory=set)
    requires_github_identifier: bool = False
    exclude_github_workflow_status: set[str] = pydantic.Field(
        default_factory=set
    )


class WorkflowGitCloneType(enum.StrEnum):
    """Enumeration of supported git clone types."""

    http = 'http'
    ssh = 'ssh'


class WorkflowGit(pydantic.BaseModel):
    """Configuration for a source repository."""

    clone: bool = True
    shallow: bool = True
    starting_branch: str | None = None
    commit_author: str = 'Authored-By: Imbi Automations <noreply@aweber.com>'
    ci_skip_checks: bool = False
    clone_type: WorkflowGitCloneType = WorkflowGitCloneType.ssh


class WorkflowGitHub(pydantic.BaseModel):
    create_pull_request: bool = True


class WorkflowGitLab(pydantic.BaseModel):
    create_merge_request: bool = True


class WorkflowConfiguration(pydantic.BaseModel):
    name: str
    description: str | None = None
    git: WorkflowGit = pydantic.Field(default_factory=WorkflowGit)
    github: WorkflowGitHub = pydantic.Field(default_factory=WorkflowGitHub)
    gitlab: WorkflowGitLab = pydantic.Field(default_factory=WorkflowGitLab)
    filter: WorkflowFilter | None = None

    condition_type: WorkflowConditionType = WorkflowConditionType.all
    conditions: list[WorkflowCondition] = pydantic.Field(default_factory=list)
    create_pull_request: bool = True
    actions: list[WorkflowAction] = pydantic.Field(default_factory=list)


class WorkflowActionResult(pydantic.BaseModel):
    """Result of a workflow action."""

    name: str


class Workflow(pydantic.BaseModel):
    path: pathlib.Path
    configuration: WorkflowConfiguration


class WorkflowContext(pydantic.BaseModel):
    """Template context for workflow execution with type safety."""

    workflow: Workflow
    github_repository: github.GitHubRepository | None = None
    gitlab_project: gitlab.GitLabProject | None = None
    imbi_project: imbi.ImbiProject
    working_directory: pathlib.Path | None = None
