import os
import pathlib
import typing

import pydantic


class AnthropicConfiguration(pydantic.BaseModel):
    api_key: pydantic.SecretStr | None = pydantic.Field(
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
    base_prompt: pathlib.Path | None = None

    def __init__(self, **kwargs: typing.Any) -> None:
        super().__init__(**kwargs)
        # Set default base_prompt to claude.md in prompts directory
        # if not specified
        if self.base_prompt is None:
            self.base_prompt = (
                pathlib.Path(__file__).parent / 'prompts' / 'claude.md'
            )


class Configuration(pydantic.BaseModel):
    anthropic: AnthropicConfiguration = pydantic.Field(
        default_factory=AnthropicConfiguration
    )
    claude_code: ClaudeCodeConfiguration | None = None
    github: GitHubConfiguration | None = None
    gitlab: GitLabConfiguration | None = None
    imbi: ImbiConfiguration | None = None
