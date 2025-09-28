"""File action operations for workflow execution."""

import logging
import pathlib
import re
import shutil

from imbi_automations import mixins, models

LOGGER = logging.getLogger(__name__)


class FileActions(mixins.WorkflowLoggerMixin):
    """File action executor for workflow actions."""

    def __init__(self, verbose: bool = False) -> None:
        super().__init__(verbose)
        self.logger = LOGGER

    async def execute(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowFileAction,
    ) -> None:
        """Execute a file action based on the command type.

        Args:
            context: Workflow context
            action: File action containing the command and parameters

        Raises:
            RuntimeError: If file operation fails
            ValueError: If required parameters are missing or invalid

        """
        self._set_workflow_logger(context.workflow)

        match action.command:
            case models.WorkflowFileActionCommand.append:
                await self._execute_append(context, action)
            case models.WorkflowFileActionCommand.copy:
                await self._execute_copy(context, action)
            case models.WorkflowFileActionCommand.delete:
                await self._execute_delete(context, action)
            case models.WorkflowFileActionCommand.move:
                await self._execute_move(context, action)
            case models.WorkflowFileActionCommand.rename:
                await self._execute_rename(context, action)
            case models.WorkflowFileActionCommand.write:
                await self._execute_write(context, action)
            case _:
                raise RuntimeError(
                    f'Unsupported file command: {action.command}'
                )

    async def _execute_append(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowFileAction,
    ) -> None:
        """Execute append file action."""
        file_path = self._resolve_path(context, action.path)

        self._log_verbose_info('Appending to file: %s', file_path)

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Append content to file
        with file_path.open('a', encoding=action.encoding) as f:
            if isinstance(action.content, bytes):
                f.write(action.content.decode(action.encoding))
            else:
                f.write(action.content)

        self._log_verbose_info('Successfully appended to %s', file_path)

    async def _execute_copy(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowFileAction,
    ) -> None:
        """Execute copy file action."""
        source_path = self._resolve_path(context, action.source)
        dest_path = self._resolve_path(context, action.destination)

        self._log_verbose_info('Copying %s to %s', source_path, dest_path)

        if not source_path.exists():
            raise RuntimeError(f'Source file does not exist: {source_path}')

        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if source_path.is_file():
            shutil.copy2(source_path, dest_path)
        elif source_path.is_dir():
            shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
        else:
            raise RuntimeError(
                f'Source path is neither file nor directory: {source_path}'
            )

        self._log_verbose_info(
            'Successfully copied %s to %s', source_path, dest_path
        )

    async def _execute_delete(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowFileAction,
    ) -> None:
        """Execute delete file action."""
        base_path = self._get_base_path(context)

        if action.path:
            # Delete specific file/directory
            file_path = self._resolve_path(context, action.path)
            self._log_verbose_info('Deleting file/directory: %s', file_path)

            if file_path.exists():
                if file_path.is_file():
                    file_path.unlink()
                elif file_path.is_dir():
                    shutil.rmtree(file_path)
                self._log_verbose_info('Successfully deleted %s', file_path)
            else:
                self.logger.warning(
                    'File to delete does not exist: %s', file_path
                )

        elif action.pattern:
            # Delete files matching pattern
            self._log_verbose_info(
                'Deleting files matching pattern: %s', action.pattern
            )

            deleted_count = 0
            if isinstance(action.pattern, str):
                pattern = re.compile(action.pattern)
            else:
                pattern = action.pattern

            for file_path in base_path.rglob('*'):
                if file_path.is_file():
                    relative_path = file_path.relative_to(base_path)
                    if pattern.search(str(relative_path)):
                        self.logger.debug(
                            'Deleting file matching pattern: %s', file_path
                        )
                        file_path.unlink()
                        deleted_count += 1

            self._log_verbose_info(
                'Deleted %d files matching pattern', deleted_count
            )

    async def _execute_move(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowFileAction,
    ) -> None:
        """Execute move file action."""
        source_path = self._resolve_path(context, action.source)
        dest_path = self._resolve_path(context, action.destination)

        self._log_verbose_info('Moving %s to %s', source_path, dest_path)

        if not source_path.exists():
            raise RuntimeError(f'Source file does not exist: {source_path}')

        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(source_path), str(dest_path))

        self._log_verbose_info(
            'Successfully moved %s to %s', source_path, dest_path
        )

    async def _execute_rename(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowFileAction,
    ) -> None:
        """Execute rename file action."""
        source_path = self._resolve_path(context, action.source)
        dest_path = self._resolve_path(context, action.destination)

        self._log_verbose_info('Renaming %s to %s', source_path, dest_path)

        if not source_path.exists():
            raise RuntimeError(f'Source file does not exist: {source_path}')

        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        source_path.rename(dest_path)

        self._log_verbose_info(
            'Successfully renamed %s to %s', source_path, dest_path
        )

    async def _execute_write(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowFileAction,
    ) -> None:
        """Execute write file action."""
        file_path = self._resolve_path(context, action.path)

        self._log_verbose_info('Writing to file: %s', file_path)

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content to file
        if isinstance(action.content, bytes):
            with file_path.open('wb') as f:
                f.write(action.content)
        else:
            with file_path.open('w', encoding=action.encoding) as f:
                f.write(action.content)

        self._log_verbose_info('Successfully wrote to %s', file_path)

    def _resolve_path(
        self, context: models.WorkflowContext, path: pathlib.Path
    ) -> pathlib.Path:
        """Resolve a path relative to the working directory."""
        if path.is_absolute():
            return path
        return context.working_directory / path

    def _get_base_path(self, context: models.WorkflowContext) -> pathlib.Path:
        """Get the base path for file operations (working directory)."""
        return context.working_directory
