import datetime
import os
import pathlib
import typing

import pydantic

# Configuration Models


class AnthropicConfiguration(pydantic.BaseModel):
    api_key: pydantic.SecretStr = pydantic.Field(
        default=os.environ.get('ANTHROPIC_API_KEY')
    )
    hostname: str = pydantic.Field(default='github.com')


class GitHubConfiguration(pydantic.BaseModel):
    api_key: pydantic.SecretStr
    hostname: str = pydantic.Field(default='github.com')


class GitLabConfiguration(pydantic.BaseModel):
    api_key: pydantic.SecretStr
    hostname: str = pydantic.Field(default='gitlab.com')


class ImbiConfiguration(pydantic.BaseModel):
    api_key: pydantic.SecretStr
    hostname: str
    github_link: str = 'GitHub Repository'  # Name of GitHub link in Imbi
    gitlab_link: str = 'GitLab Project'  # Name of GitLab link in Imbi
    grafana_link: str = 'Grafana Dashboard'  # Name of Grafana link in Imbi
    pagerduty_link: str = 'PagerDuty'  # Name of PagerDuty link in Imbi
    sentry_link: str = 'Sentry'  # Name of Sentry link in Imbi
    sonarqube_link: str = 'SonarQube'  # Name of SonarQube link in Imbi


class ClaudeCodeConfiguration(pydantic.BaseModel):
    executable: str = 'claude'  # Claude Code executable path


class Configuration(pydantic.BaseModel):
    anthropic: AnthropicConfiguration = pydantic.Field(
        default_factory=AnthropicConfiguration
    )
    claude_code: ClaudeCodeConfiguration | None = None
    github: GitHubConfiguration | None = None
    gitlab: GitLabConfiguration | None = None
    imbi: ImbiConfiguration | None = None


# GitHub Related Models


class GitHubOrganization(pydantic.BaseModel):
    """GitHub organization (simple schema)."""

    login: str
    id: int
    node_id: str
    url: str
    repos_url: str
    events_url: str
    hooks_url: str
    issues_url: str
    members_url: str
    public_members_url: str
    avatar_url: str
    description: str | None


class GitHubUser(pydantic.BaseModel):
    """GitHub user (simple schema)."""

    login: str
    id: int
    node_id: str
    avatar_url: str
    gravatar_id: str | None = None
    url: str
    html_url: str
    type: str
    site_admin: bool | None = None


class GitHubLabel(pydantic.BaseModel):
    """GitHub label."""

    id: int | None = None
    node_id: str | None = None
    name: str
    description: str | None = None
    color: str


class GitHubPullRequest(pydantic.BaseModel):
    """GitHub pull request."""

    id: int
    number: int
    title: str
    body: str | None = None
    state: str
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None
    closed_at: datetime.datetime | None = None
    merged_at: datetime.datetime | None = None
    head: dict[str, typing.Any]
    base: dict[str, typing.Any]
    user: GitHubUser
    assignees: list[GitHubUser] | None = None
    requested_reviewers: list[GitHubUser] | None = None
    labels: list[GitHubLabel] | None = None
    milestone: typing.Any | None = None
    draft: bool | None = None
    html_url: str
    url: str
    merge_commit_sha: str | None = None
    mergeable: bool | None = None
    mergeable_state: str | None = None
    merged: bool | None = None
    merged_by: GitHubUser | None = None
    comments: int | None = None
    review_comments: int | None = None
    maintainer_can_modify: bool | None = None
    commits: int | None = None
    additions: int | None = None
    deletions: int | None = None
    changed_files: int | None = None


class GitHubRepository(pydantic.BaseModel):
    """GitHub repository with key properties."""

    # Core required fields
    id: int
    node_id: str
    name: str
    full_name: str
    owner: GitHubUser
    private: bool
    html_url: str
    description: str | None
    fork: bool
    url: str
    default_branch: str

    # Clone URLs
    clone_url: str  # HTTPS clone URL
    ssh_url: str  # SSH clone URL
    git_url: str  # Git protocol URL

    # Common optional fields
    archived: bool | None = None
    disabled: bool | None = None
    visibility: str | None = None
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None
    pushed_at: datetime.datetime | None = None
    size: int | None = None
    stargazers_count: int | None = None
    watchers_count: int | None = None
    language: str | None = None
    forks_count: int | None = None
    open_issues_count: int | None = None
    topics: list[str] | None = None
    has_issues: bool | None = None
    has_projects: bool | None = None
    has_wiki: bool | None = None
    has_pages: bool | None = None
    has_downloads: bool | None = None

    # Custom properties (optional, populated by specific API calls)
    custom_properties: dict[str, str | list[str]] | None = None


class GitHubWorkflowRun(pydantic.BaseModel):
    """GitHub Actions workflow run."""

    id: int
    name: str | None
    node_id: str
    check_suite_id: int
    check_suite_node_id: str
    head_branch: str | None
    head_sha: str
    path: str
    run_number: int
    run_attempt: int | None = None
    event: str
    status: str | None
    conclusion: str | None
    workflow_id: int
    url: str
    html_url: str
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None


# GitLab Related Models


class GitLabNamespace(pydantic.BaseModel):
    """GitLab namespace/group."""

    id: int
    name: str
    path: str
    kind: str
    full_path: str
    parent_id: int | None = None
    avatar_url: str | None = None
    web_url: str


class GitLabUser(pydantic.BaseModel):
    """GitLab user."""

    id: int
    username: str
    name: str
    state: str
    avatar_url: str | None = None
    web_url: str
    email: str | None = None


class GitLabMergeRequest(pydantic.BaseModel):
    """GitLab merge request."""

    id: int
    iid: int
    title: str
    description: str | None = None
    state: str
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None
    merged_at: datetime.datetime | None = None
    closed_at: datetime.datetime | None = None
    target_branch: str
    source_branch: str
    upvotes: int | None = None
    downvotes: int | None = None
    author: GitLabUser
    assignees: list[GitLabUser] | None = None
    reviewers: list[GitLabUser] | None = None
    source_project_id: int
    target_project_id: int
    labels: list[str] | None = None
    draft: bool | None = None
    work_in_progress: bool | None = None
    milestone: typing.Any | None = None
    merge_when_pipeline_succeeds: bool | None = None
    merge_status: str | None = None
    sha: str | None = None
    merge_commit_sha: str | None = None
    user_notes_count: int | None = None
    changes_count: str | None = None
    should_remove_source_branch: bool | None = None
    force_remove_source_branch: bool | None = None
    squash: bool | None = None
    web_url: str


class GitLabProject(pydantic.BaseModel):
    """GitLab project with key properties."""

    # Core required fields
    id: int
    name: str
    description: str | None = None
    name_with_namespace: str
    path: str
    path_with_namespace: str
    created_at: datetime.datetime
    default_branch: str | None = None

    # URLs
    ssh_url_to_repo: str
    http_url_to_repo: str
    web_url: str
    readme_url: str | None = None
    avatar_url: str | None = None

    # Counts and metadata
    forks_count: int | None = None
    star_count: int | None = None
    last_activity_at: datetime.datetime | None = None
    visibility: str

    # Nested objects
    namespace: GitLabNamespace

    # Boolean flags
    archived: bool | None = None
    empty_repo: bool | None = None
    issues_enabled: bool | None = None
    merge_requests_enabled: bool | None = None
    wiki_enabled: bool | None = None
    jobs_enabled: bool | None = None
    snippets_enabled: bool | None = None
    container_registry_enabled: bool | None = None

    # Lists
    tag_list: list[str] | None = None
    topics: list[str] | None = None


# Imbi Project Related Models


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


class WorkflowAction(pydantic.BaseModel):
    """A single action in a workflow."""

    name: str
    value: WorkflowActionValue
    target: WorkflowActionTarget | None = None
    value_mapping: dict[str, str] | None = None


class WorkflowConfiguration(pydantic.BaseModel):
    name: str
    description: str | None = None
    clone_repository: bool = True
    actions: list[WorkflowAction] = pydantic.Field(default_factory=list)


class Workflow(pydantic.BaseModel):
    path: pathlib.Path
    configuration: WorkflowConfiguration


class WorkflowRun(pydantic.BaseModel):
    workflow: Workflow
    github_repository: GitHubRepository | None = None
    gitlab_project: GitLabProject | None = None
    imbi_project: ImbiProject
