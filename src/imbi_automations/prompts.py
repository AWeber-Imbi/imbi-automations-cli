import logging
import pathlib
import typing

import jinja2

from imbi_automations import models, utils


def render(
    context: models.WorkflowContext, source: pathlib.Path, **kwargs: typing.Any
) -> str | bytes:
    env = jinja2.Environment(
        autoescape=False,  # noqa: S701
        undefined=jinja2.StrictUndefined,
    )
    env.globals['extract_image_from_dockerfile'] = (
        lambda dockerfile: utils.extract_image_from_dockerfile(
            context, dockerfile
        )
    )

    template = env.from_string(source.read_text(encoding='utf-8'))
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
