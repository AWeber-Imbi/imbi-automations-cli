import datetime
import typing

import pydantic


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
