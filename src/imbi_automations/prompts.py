import logging
import pathlib
import typing

import jinja2

from imbi_automations import models, utils


def render(
    context: models.WorkflowContext | None = None,
    source: pathlib.Path | str | None = None,
    **kwargs: typing.Any,
) -> str | bytes:
    if not source:
        raise ValueError('source is required')
    env = jinja2.Environment(
        autoescape=False,  # noqa: S701
        undefined=jinja2.StrictUndefined,
    )
    if context:
        env.globals['extract_image_from_dockerfile'] = (
            lambda dockerfile: utils.extract_image_from_dockerfile(
                context, dockerfile
            )
        )
    if isinstance(source, pathlib.Path):
        source = source.read_text(encoding='utf-8')
    template = env.from_string(source)
    return template.render(kwargs)


def render_file(
    context: models.WorkflowContext,
    source: pathlib.Path,
    destination: pathlib.Path,
    **kwargs: typing.Any,
) -> None:
    """Render a file from source to destination."""
    logging.info('Rendering %s to %s', source, destination)
    destination.write_text(render(context, source, **kwargs), encoding='utf-8')


def has_template_syntax(value: str) -> bool:
    """Check if value contains Jinja2 templating syntax."""
    template_patterns = [
        '{{',  # Variable substitution
        '{%',  # Control structures
        '{#',  # Comments
    ]
    return any(pattern in value for pattern in template_patterns)
