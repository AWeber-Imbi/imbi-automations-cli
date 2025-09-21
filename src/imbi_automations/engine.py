import enum
import logging

from imbi_automations import models

LOGGER = logging.getLogger(__name__)


class AutomationIterator(enum.Enum):
    github_repositories = 1
    github_organization = 2
    github_project = 3
    gitlab_repositories = 4
    gitlab_group = 5
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

    def run(self) -> None:
        match self.iterator:
            case AutomationIterator.github_repositories:
                self._process_github_repositories()
            case AutomationIterator.github_organization:
                self._process_github_organization()
            case AutomationIterator.github_project:
                self._process_github_project()
            case AutomationIterator.gitlab_repositories:
                self._process_gitlab_repositories()
            case AutomationIterator.gitlab_group:
                self._process_gitlab_group()
            case AutomationIterator.gitlab_project:
                self._process_gitlab_project()
            case AutomationIterator.imbi_project_types:
                self._process_imbi_project_types()
            case AutomationIterator.imbi_project:
                self._process_imbi_project()
            case AutomationIterator.imbi_projects:
                self._process_imbi_projects()

    def _process_github_repositories(self) -> None: ...

    def _process_github_organization(self) -> None: ...

    def _process_github_project(self) -> None: ...

    def _process_gitlab_repositories(self) -> None: ...

    def _process_gitlab_group(self) -> None: ...

    def _process_gitlab_project(self) -> None: ...

    def _process_imbi_project_types(self) -> None: ...

    def _process_imbi_project(self) -> None: ...

    def _process_imbi_projects(self) -> None: ...
