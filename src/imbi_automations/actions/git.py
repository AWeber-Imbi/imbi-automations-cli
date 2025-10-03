from imbi_automations import git, mixins, models, utils


class GitActions(mixins.WorkflowLoggerMixin):
    """Git command executor for workflow actions."""

    def __init__(
        self,
        configuration: models.Configuration,
        context: models.WorkflowContext,
        verbose: bool,
    ) -> None:
        super().__init__(verbose)
        self._set_workflow_logger(context.workflow)
        self.configuration = configuration
        self.context = context

    async def execute(self, action: models.WorkflowGitAction) -> None:
        """Execute the shell action."""
        match action.command:
            case models.WorkflowGitActionCommand.extract:
                destination_file = utils.resolve_path(
                    self.context, action.destination
                )
                if (
                    not await git.extract_file_from_commit(
                        working_directory=self.context.working_directory
                        / 'repository',
                        source_file=action.source,
                        destination_file=destination_file,
                        commit_keyword=action.commit_keyword,
                        search_strategy=action.search_strategy
                        or 'before_last_match',
                    )
                    and not action.ignore_errors
                ):
                    raise RuntimeError(
                        f'Git extraction failed for {action.source}'
                    )
            case models.WorkflowGitActionCommand.clone:
                destination_path = utils.resolve_path(
                    self.context, action.destination
                )
                await git.clone_to_directory(
                    working_directory=self.context.working_directory,
                    clone_url=action.url,
                    destination=destination_path,
                    branch=action.branch,
                    depth=action.depth,
                )
            case _:
                raise RuntimeError(f'Unsupported command: {action.command}')
