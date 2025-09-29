import logging

from imbi_automations import clients, mixins, models

LOGGER = logging.getLogger(__name__)


class Filter(mixins.WorkflowLoggerMixin):
    """Filter for workflows and actions."""

    def __init__(
        self,
        configuration: models.Configuration,
        workflow: models.Workflow,
        verbose: bool,
    ) -> None:
        super().__init__(verbose)
        self.configuration = configuration
        self._set_workflow_logger(workflow)

    async def filter_project(
        self,
        project: models.ImbiProject,
        workflow_filter: models.WorkflowFilter,
    ) -> models.ImbiProject | None:
        """Filter projects based on workflow configuration

        project_ids: set[int] = pydantic.Field(default_factory=set)
        project_types: set[str] = pydantic.Field(default_factory=set)
        project_facts: dict[str, str] = pydantic.Field(default_factory=dict)
        project_environments: set[str] = pydantic.Field(default_factory=set)
        requires_github_identifier: bool = False
        exclude_github_workflow_status: set[str] = pydantic.Field(
            default_factory=set
        )

        """
        if (
            workflow_filter.github_identifier_required
            and not project.identifiers.get(
                self.configuration.imbi.github_identifier
            )
        ):
            return None

        if (
            workflow_filter.project_ids
            and project.id not in workflow_filter.project_ids
        ):
            return None

        if workflow_filter.project_environments and not any(
            env in project.environments
            for env in workflow_filter.project_environments
        ):
            return None

        if workflow_filter.project_facts and not all(
            project.facts.get(k) == v
            for k, v in workflow_filter.project_facts.items()
        ):
            return None

        if (
            workflow_filter.project_types
            and project.project_type_slug not in workflow_filter.project_types
        ):
            return None

        # Dynamic Filters Should happen _after_ easily applied ones

        if workflow_filter.github_workflow_status_exclude:
            status = await self._filter_github_action_status(project)
            if status in workflow_filter.github_workflow_status_exclude:
                return None

        return project

    async def _filter_github_action_status(
        self, project: models.ImbiProject
    ) -> str:
        client = clients.GitHub.get_instance(config=self.configuration.github)
        repository = await client.get_repository(project)
        return await client.get_repository_workflow_status(repository)
