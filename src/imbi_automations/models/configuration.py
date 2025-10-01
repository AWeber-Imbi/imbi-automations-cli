import os
import pathlib
import typing

import pydantic


class AnthropicConfiguration(pydantic.BaseModel):
    api_key: pydantic.SecretStr | None = pydantic.Field(
        default=os.environ.get('ANTHROPIC_API_KEY')
    )
    bedrock: bool = False
    model: str = pydantic.Field(default='claude-3-5-haiku-latest')


class GitHubConfiguration(pydantic.BaseModel):
    api_key: pydantic.SecretStr
    hostname: str = pydantic.Field(default='github.com')


class GitLabConfiguration(pydantic.BaseModel):
    api_key: pydantic.SecretStr
    hostname: str = pydantic.Field(default='gitlab.com')


class ImbiConfiguration(pydantic.BaseModel):
    api_key: pydantic.SecretStr
    hostname: str
    github_identifier: str = 'github'
    gitlab_identifier: str = 'gitlab'
    pagerduty_identifier: str = 'pagerduty'
    sonarqube_identifier: str = 'sonarqube'
    sentry_identifier: str = 'sentry'
    github_link: str = 'GitHub Repository'
    gitlab_link: str = 'GitLab Project'
    grafana_link: str = 'Grafana Dashboard'
    pagerduty_link: str = 'PagerDuty'
    sentry_link: str = 'Sentry'
    sonarqube_link: str = 'SonarQube'


class ClaudeCodeConfiguration(pydantic.BaseModel):
    executable: str = 'claude'  # Claude Code executable path
    base_prompt: pathlib.Path | None = None
    enabled: bool = True

    def __init__(self, **kwargs: typing.Any) -> None:
        super().__init__(**kwargs)
        # Set default base_prompt to claude.md in prompts directory
        # if not specified
        if self.base_prompt is None:
            self.base_prompt = (
                pathlib.Path(__file__).parent / 'prompts' / 'claude.md'
            )


class Configuration(pydantic.BaseModel):
    ai_commits: bool = False
    anthropic: AnthropicConfiguration = pydantic.Field(
        default_factory=AnthropicConfiguration
    )
    claude_code: ClaudeCodeConfiguration | None = None
    commit_author: str = 'Imbi Automations <noreply@aweber.com>'
    error_dir: pathlib.Path = pathlib.Path('./errors')
    github: GitHubConfiguration | None = None
    gitlab: GitLabConfiguration | None = None
    imbi: ImbiConfiguration | None = None
    preserve_on_error: bool = False
