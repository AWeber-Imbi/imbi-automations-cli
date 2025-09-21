import enum

from imbi_automations import models


class AutomationIterator(enum.Enum):
    github_repositories = 1
    github_organization = 2
    github_project = 3
    gitlab_repositories = 4
    gitlab_organization = 5
    gitlab_project = 6
    imbi_project_types = 7
    imbi_project = 8
    imbi_projects = 9


class AutomationEngine:
    def __init__(
        self, configuration: models.Configuration, iterator: AutomationIterator
    ) -> None:
        self.configuration = configuration
        self.iterator = iterator

    def run(self) -> None: ...
