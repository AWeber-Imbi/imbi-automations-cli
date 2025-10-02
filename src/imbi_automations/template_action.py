"""Template action implementation for rendering Jinja2 templates."""

import logging
import pathlib

import jinja2

from imbi_automations import models, utils

LOGGER = logging.getLogger(__name__)


async def execute(
    context: models.WorkflowContext, action: models.WorkflowTemplateAction
) -> None:
    """Execute template action to render Jinja2 templates.

    Args:
        context: Workflow execution context
        action: Template action configuration

    Raises:
        RuntimeError: If template rendering fails

    """
    # Resolve source and destination paths
    source_path = utils.resolve_path(context, action.source_path)
    destination_path = utils.resolve_path(context, action.destination_path)

    if not source_path.exists():
        raise RuntimeError(
            f'Template source path does not exist: {source_path}'
        )

    # Setup Jinja2 environment
    env = jinja2.Environment(
        autoescape=False,  # noqa: S701
        undefined=jinja2.StrictUndefined,
    )
    env.globals['extract_image_from_dockerfile'] = (
        lambda dockerfile: utils.extract_image_from_dockerfile(
            context, dockerfile
        )
    )

    # Prepare template context with full workflow context
    template_context = {
        'workflow': context.workflow,
        'github_repository': context.github_repository,
        'gitlab_project': context.gitlab_project,
        'imbi_project': context.imbi_project,
        'working_directory': context.working_directory,
        'starting_commit': context.starting_commit,
    }

    if source_path.is_file():
        # Single file template
        LOGGER.debug(
            'Rendering template from %s to %s', source_path, destination_path
        )
        _render_template_file(
            env, source_path, destination_path, template_context
        )
        LOGGER.info('Rendered template to %s', destination_path)
    elif source_path.is_dir():
        # Directory of templates - glob everything
        LOGGER.debug(
            'Rendering all templates from directory %s to %s',
            source_path,
            destination_path,
        )

        # Ensure destination directory exists
        destination_path.mkdir(parents=True, exist_ok=True)

        # Glob all files recursively
        template_files = list(source_path.rglob('*'))
        file_count = 0

        for template_file in template_files:
            if template_file.is_file():
                # Calculate relative path from source
                relative_path = template_file.relative_to(source_path)
                dest_file = destination_path / relative_path

                # Ensure parent directory exists
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                _render_template_file(
                    env, template_file, dest_file, template_context
                )
                file_count += 1

        LOGGER.info(
            'Rendered %d templates from %s to %s',
            file_count,
            source_path,
            destination_path,
        )
    else:
        raise RuntimeError(
            f'Template source path is neither file nor directory: '
            f'{source_path}'
        )


def _render_template_file(
    env: jinja2.Environment,
    source_file: pathlib.Path,
    destination_file: pathlib.Path,
    template_context: dict,
) -> None:
    """Render a single template file.

    Args:
        env: Jinja2 environment
        source_file: Source template file path
        destination_file: Destination output file path
        template_context: Template rendering context

    """
    LOGGER.debug('Rendering %s to %s', source_file, destination_file)

    try:
        template_content = source_file.read_text(encoding='utf-8')
        template = env.from_string(template_content)
        rendered = template.render(**template_context)

        destination_file.write_text(rendered, encoding='utf-8')
    except jinja2.TemplateError as exc:
        raise RuntimeError(
            f'Template rendering failed for {source_file}: {exc}'
        ) from exc
