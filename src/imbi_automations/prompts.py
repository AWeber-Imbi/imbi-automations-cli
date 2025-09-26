import logging
import pathlib

import jinja2


def render(source: pathlib.Path, **kwargs: dict) -> str | bytes:
    jinja_env = jinja2.Environment(
        autoescape=False,  # noqa: S701
        undefined=jinja2.StrictUndefined,
    )
    template = jinja_env.from_string(source.read_text(encoding='utf-8'))
    return template.render(kwargs)


def render_file(
    source: pathlib.Path, destination: pathlib.Path, **kwargs: dict
) -> None:
    """Render a file from source to destination."""
    logging.info('Rendering %s to %s', source, destination)
    destination.write_text(render(source, **kwargs), encoding='utf-8')
