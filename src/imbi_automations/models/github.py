"""GitHub API response models.

Defines Pydantic models for GitHub API responses including organizations,
repositories, users, workflow runs, pull requests, and environments. Models
follow GitHub's REST API v3 schema with proper type annotations.
"""

import datetime
import typing

from . import base


class GitHubOrganization(base.BaseModel):
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


class GitHubUser(base.BaseModel):
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


class GitHubLabel(base.BaseModel):
    """GitHub label."""

    id: int | None = None
    node_id: str | None = None
    name: str
    description: str | None = None
    color: str


class GitHubPullRequest(base.BaseModel):
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


class GitHubRepository(base.BaseModel):
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


class GitHubWorkflowRun(base.BaseModel):
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


class GitHubWorkflowJob(base.BaseModel):
    """GitHub Actions workflow job."""

    id: int
    run_id: int
    node_id: str
    name: str
    status: str | None
    conclusion: str | None
    created_at: datetime.datetime
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None
    url: str
    html_url: str


class GitHubTeam(base.BaseModel):
    """GitHub team with repository permission."""

    id: int
    node_id: str
    name: str
    slug: str
    description: str | None
    privacy: str  # 'closed' or 'secret'
    permission: str  # Repository permission level
    url: str
    html_url: str
    members_url: str
    repositories_url: str


class GitHubTeamPermission(base.BaseModel):
    """GitHub team permission on a repository."""

    team_slug: str
    permission: str  # pull, triage, push, maintain, admin


class GitHubEnvironment(base.BaseModel):
    """GitHub repository environment."""

    id: int | None = None
    name: str
    url: str | None = None
    html_url: str | None = None
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None
    protection_rules: list[dict[str, typing.Any]] | None = None
    deployment_branch_policy: dict[str, typing.Any] | None = None
