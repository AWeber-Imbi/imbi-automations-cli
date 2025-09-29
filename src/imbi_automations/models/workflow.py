import enum
import pathlib
import typing
from typing import Annotated, ClassVar, Literal

import pydantic

from . import github, gitlab, imbi
from .validators import CommandRulesMixin, ExclusiveGroupsMixin, Variant


class WorkflowFilter(pydantic.BaseModel):
    project_ids: set[int] = pydantic.Field(default_factory=set)
    project_types: set[str] = pydantic.Field(default_factory=set)
    project_facts: dict[str, str] = pydantic.Field(default_factory=dict)
    project_environments: set[str] = pydantic.Field(default_factory=set)
    github_identifier_required: bool = False
    github_workflow_status_exclude: set[str] = pydantic.Field(
        default_factory=set
    )


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
    model_config = pydantic.ConfigDict(extra='forbid')

    name: str
    type: WorkflowActionTypes = WorkflowActionTypes.callable

    conditions: list['WorkflowCondition'] = pydantic.Field(
        default_factory=list
    )
    condition_type: WorkflowConditionType = WorkflowConditionType.all
    committable: bool = True
    filter: WorkflowFilter | None = None
    on_success: str | None = None
    on_failure: str | None = None
    timeout: int = 3600
    data: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


class WorkflowCallableAction(WorkflowAction):
    type: Literal['callable'] = 'callable'
    import_name: str = pydantic.Field(alias='import')
    callable: typing.Callable
    args: list[typing.Any] = pydantic.Field(default_factory=list)
    kwargs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


class WorkflowClaudeAction(WorkflowAction):
    type: Literal['claude'] = 'claude'
    prompt: str | None
    validation_prompt: str | None = None
    max_cycles: int = 3


class WorkflowDockerActionCommand(enum.StrEnum):
    build = 'build'
    extract = 'extract'
    pull = 'pull'
    push = 'push'


class WorkflowDockerAction(CommandRulesMixin, WorkflowAction):
    type: Literal['docker'] = 'docker'
    command: WorkflowDockerActionCommand
    image: str
    tag: str = 'latest'
    path: pathlib.Path | None = None
    source: pathlib.Path | None = None
    destination: pathlib.Path | None = None
    committable: bool = False

    # CommandRulesMixin configuration
    command_field: ClassVar[str] = 'command'
    required_fields: ClassVar[dict[object, set[str]]] = {
        WorkflowDockerActionCommand.build: {'path'},
        WorkflowDockerActionCommand.extract: {'source', 'destination'},
        WorkflowDockerActionCommand.pull: set(),
        WorkflowDockerActionCommand.push: set(),
    }
    # image and tag are always allowed; include them accordingly
    allowed_fields: ClassVar[dict[object, set[str]]] = {
        WorkflowDockerActionCommand.build: {'image', 'tag', 'path'},
        WorkflowDockerActionCommand.extract: {
            'image',
            'tag',
            'source',
            'destination',
        },
        WorkflowDockerActionCommand.pull: {'image', 'tag'},
        WorkflowDockerActionCommand.push: {'image', 'tag'},
    }


class WorkflowFileActionCommand(enum.StrEnum):
    append = 'append'
    copy = 'copy'
    delete = 'delete'
    move = 'move'
    rename = 'rename'
    write = 'write'


def _file_delete_requires_path_or_pattern(model: 'WorkflowFileAction') -> None:
    if (
        model.command == WorkflowFileActionCommand.delete
        and model.path is None
        and model.pattern is None
    ):
        raise ValueError(
            "Field 'path' or 'pattern' is required for command 'delete'"
        )


class WorkflowFileAction(CommandRulesMixin, WorkflowAction):
    type: Literal['file'] = 'file'
    command: WorkflowFileActionCommand
    path: pathlib.Path | None = None
    pattern: typing.Pattern | None = None
    source: pathlib.Path | None = None
    destination: pathlib.Path | None = None
    content: str | bytes | None = None
    encoding: str = 'utf-8'

    # CommandRulesMixin configuration
    command_field: ClassVar[str] = 'command'
    required_fields: ClassVar[dict[object, set[str]]] = {
        WorkflowFileActionCommand.append: {'path', 'content'},
        WorkflowFileActionCommand.copy: {'source', 'destination'},
        WorkflowFileActionCommand.delete: set(),
        WorkflowFileActionCommand.move: {'source', 'destination'},
        WorkflowFileActionCommand.rename: {'source', 'destination'},
        WorkflowFileActionCommand.write: {'path', 'content'},
    }
    allowed_fields: ClassVar[dict[object, set[str]]] = {
        WorkflowFileActionCommand.append: {'path', 'content', 'encoding'},
        WorkflowFileActionCommand.copy: {'source', 'destination'},
        WorkflowFileActionCommand.delete: {'path', 'pattern'},
        WorkflowFileActionCommand.move: {'source', 'destination'},
        WorkflowFileActionCommand.rename: {'source', 'destination'},
        WorkflowFileActionCommand.write: {'path', 'content', 'encoding'},
    }
    validators: ClassVar[tuple] = (_file_delete_requires_path_or_pattern,)


class WorkflowGitActionCommand(enum.StrEnum):
    extract = 'extract'


class WorkflowGitActionCommitMatchStrategy(enum.StrEnum):
    before_first_match = 'before_first_match'
    before_last_match = 'before_last_match'


class WorkflowGitAction(WorkflowAction):
    type: Literal['git'] = 'git'
    command: WorkflowGitActionCommand
    source: pathlib.Path
    destination: pathlib.Path
    commit_keyword: str | None = None
    search_strategy: WorkflowGitActionCommitMatchStrategy | None = None
    ignore_errors: bool = False

    @pydantic.model_validator(mode='after')
    def set_committable_for_extract(self) -> 'WorkflowGitAction':
        """Set committable to False for extract commands."""
        if self.command == WorkflowGitActionCommand.extract:
            self.committable = False
        return self


class WorkflowGitHubCommand(enum.StrEnum):
    sync_environments = 'sync_environments'


class WorkflowGitHubAction(WorkflowAction):
    type: Literal['github'] = 'github'
    command: WorkflowGitHubCommand


class WorkflowShellAction(WorkflowAction):
    type: Literal['shell'] = 'shell'
    command: str
    ignore_errors: bool = False


class WorkflowTemplateAction(WorkflowAction):
    type: Literal['template'] = 'template'
    source_path: pathlib.Path
    destination_path: pathlib.Path


class WorkflowUtilityCommands(enum.StrEnum):
    docker_tag = 'docker_tag'
    dockerfile_from = 'dockerfile_from'
    compare_semver = 'compare_semver'
    parse_python_constraints = 'parse_python_constraints'


class WorkflowUtilityAction(WorkflowAction):
    type: Literal['utility'] = 'utility'
    command: WorkflowUtilityCommands
    path: pathlib.Path | None = None
    args: list[typing.Any] = pydantic.Field(default_factory=list)
    kwargs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


WorkflowActions = Annotated[
    (
        WorkflowCallableAction
        | WorkflowClaudeAction
        | WorkflowDockerAction
        | WorkflowFileAction
        | WorkflowGitAction
        | WorkflowGitHubAction
        | WorkflowShellAction
        | WorkflowTemplateAction
        | WorkflowUtilityAction
    ),
    pydantic.Field(discriminator='type'),
]


class WorkflowConditionRemoteClient(enum.StrEnum):
    github = 'github'
    gitlab = 'gitlab'


class WorkflowCondition(ExclusiveGroupsMixin, pydantic.BaseModel):
    file_exists: str | typing.Pattern | None = None
    file_not_exists: str | typing.Pattern | None = None
    file_contains: str | None = None
    file_doesnt_contain: str | None = None
    file: pathlib.Path | None = None

    remote_client: WorkflowConditionRemoteClient = (
        WorkflowConditionRemoteClient.github
    )
    remote_file_exists: str | None = None
    remote_file_not_exists: str | None = None
    remote_file_contains: str | None = None
    remote_file_doesnt_contain: str | None = None
    remote_file: pathlib.Path | None = None

    # ExclusiveGroupsMixin configuration
    variants_a: ClassVar[tuple[Variant, ...]] = (
        Variant(name='file_exists', requires_all=('file_exists',)),
        Variant(name='file_not_exists', requires_all=('file_not_exists',)),
        Variant(
            name='file_contains',
            requires_all=('file_contains', 'file'),
            paired=(('file_contains', 'file'),),
        ),
        Variant(
            name='file_doesnt_contain',
            requires_all=('file_doesnt_contain', 'file'),
            paired=(('file_doesnt_contain', 'file'),),
        ),
    )

    variants_b: ClassVar[tuple[Variant, ...]] = (
        Variant(
            name='remote_file_exists', requires_all=('remote_file_exists',)
        ),
        Variant(
            name='remote_file_not_exists',
            requires_all=('remote_file_not_exists',),
        ),
        Variant(
            name='remote_file_contains',
            requires_all=('remote_file_contains', 'remote_file'),
            paired=(('remote_file_contains', 'remote_file'),),
        ),
        Variant(
            name='remote_file_doesnt_contain',
            requires_all=('remote_file_doesnt_contain', 'remote_file'),
            paired=(('remote_file_doesnt_contain', 'remote_file'),),
        ),
    )


class WorkflowGitCloneType(enum.StrEnum):
    http = 'http'
    ssh = 'ssh'


class WorkflowGit(pydantic.BaseModel):
    clone: bool = True
    depth: int = 1
    ref: str | None = None
    starting_branch: str | None = None
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
    actions: list[WorkflowActions] = pydantic.Field(default_factory=list)


class WorkflowActionResult(pydantic.BaseModel):
    name: str


class Workflow(pydantic.BaseModel):
    path: pathlib.Path
    configuration: WorkflowConfiguration
    slug: str | None = None

    @pydantic.model_validator(mode='after')
    def _set_slug(self) -> 'Workflow':
        if not self.slug:
            self.slug = self.path.name.lower().replace('_', '-')
        return self


class WorkflowContext(pydantic.BaseModel):
    """Template context for workflow execution with type safety."""

    workflow: Workflow
    github_repository: github.GitHubRepository | None = None
    gitlab_project: gitlab.GitLabProject | None = None
    imbi_project: imbi.ImbiProject
    working_directory: pathlib.Path | None = None
    starting_commit: str | None = None
