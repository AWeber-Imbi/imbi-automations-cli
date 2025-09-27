import enum
import pathlib
import typing

import pydantic

from . import github, gitlab, imbi


class WorkflowActionTypes(enum.StrEnum):
    callable = 'callable'
    claude = 'claude'
    docker = 'docker'
    file = 'file'
    git = 'git'
    github = 'github'
    shell = 'shell'
    template = 'template'
    utility = 'utility'


class WorkflowConditionType(enum.StrEnum):
    all = 'all'
    any = 'any'


class WorkflowAction(pydantic.BaseModel):
    name: str
    type: WorkflowActionTypes = WorkflowActionTypes.callable

    conditions: list['WorkflowCondition'] = pydantic.Field(
        default_factory=list
    )
    condition_type: WorkflowConditionType = WorkflowConditionType.all
    on_failure: str | None = None
    timeout: int = 3600
    data: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


class WorkflowCallableAction(WorkflowAction):
    import_name: str = pydantic.Field(alias='import')
    callable: typing.Callable
    args: list[typing.Any] = pydantic.Field(default_factory=list)
    kwargs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


class WorkflowClaudeAction(WorkflowAction):
    prompt: str | None
    validation_prompt: str | None = None


class WorkflowDockerActionCommand(enum.StrEnum):
    build = 'build'
    extract_file = 'extract_file'
    pull = 'pull'
    push = 'push'


class WorkflowDockerAction(WorkflowAction):
    command: WorkflowDockerActionCommand
    image: str
    source: pathlib.Path | None = None
    destination: pathlib.Path | None = None


class WorkflowFileActionCommand(enum.StrEnum):
    append = 'append'
    copy = 'copy'
    delete = 'delete'
    move = 'move'
    rename = 'rename'
    write = 'write'


class WorkflowFileAction(WorkflowAction):
    command: WorkflowFileActionCommand
    path: pathlib.Path | None
    pattern: typing.Pattern | None = None
    source: pathlib.Path | None = None
    destination: pathlib.Path | None = None
    content: str | bytes | None = None
    encoding: str = 'utf-8'


class WorkflowGitActionCommand(enum.StrEnum):
    extract = 'extract'


class WorkflowGitActionCommitMatchStrategy(enum.StrEnum):
    before_first_match = 'before_first_match'
    before_last_match = 'before_last_match'


class WorkflowGitAction(WorkflowAction):
    command: WorkflowGitActionCommand
    source: pathlib.Path
    destination: pathlib.Path
    commit_keyword: str | None = None
    search_strategy: WorkflowGitActionCommitMatchStrategy | None = None


class WorkflowGitHubCommand(enum.StrEnum):
    sync_environments = 'sync_environments'


class WorkflowGitHubAction(WorkflowAction):
    command: WorkflowGitHubCommand


class WorkflowShellAction(WorkflowAction):
    command: str


class WorkflowTemplateAction(WorkflowAction):
    source_path: pathlib.Path
    destination_path: pathlib.Path


class WorkflowUtilityCommands(enum.StrEnum):
    docker_tag = 'docker_tag'
    dockerfile_from = 'dockerfile_from'
    compare_semver = 'compare_semver'
    parse_python_constraints = 'parse_python_constraints'


class WorkflowUtilityAction(WorkflowAction):
    command: WorkflowUtilityCommands
    path: pathlib.Path | None = None
    args: list[typing.Any] = pydantic.Field(default_factory=list)
    kwargs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


class WorkflowConditionRemoteClient(enum.StrEnum):
    github = 'github'
    gitlab = 'gitlab'


class WorkflowCondition(pydantic.BaseModel):
    file_exists: str | typing.Pattern | None = None
    file_not_exists: str | typing.Pattern | None = None
    file_contains: str | None = None
    file: str | typing.Pattern | None = None

    remote_client: WorkflowConditionRemoteClient = (
        WorkflowConditionRemoteClient.github
    )
    remote_file_exists: str | None = None
    remote_file_not_exists: str | None = None
    remote_file_contains: str | None = None
    remote_file: str | typing.Pattern | None = None


class WorkflowFilter(pydantic.BaseModel):
    project_ids: set[int] = pydantic.Field(default_factory=set)
    project_types: set[str] = pydantic.Field(default_factory=set)
    project_facts: dict[str, str] = pydantic.Field(default_factory=dict)
    project_environments: set[str] = pydantic.Field(default_factory=set)
    github_identifier_required: bool = False
    github_workflow_status_exclude: set[str] = pydantic.Field(
        default_factory=set
    )


class WorkflowGitCloneType(enum.StrEnum):
    http = 'http'
    ssh = 'ssh'


class WorkflowGit(pydantic.BaseModel):
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
