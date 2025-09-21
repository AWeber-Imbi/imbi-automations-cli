import argparse
import logging
import pathlib
import typing

import colorlog

from imbi_automations import engine, models, utils, version

LOGGER = logging.getLogger(__name__)


def configure_logging(debug: bool) -> None:
    """Configure colored logging for CLI applications."""
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - '
            '%(message)s',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bold_red',
            },
        )
    )

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO, handlers=[handler]
    )

    # Reduce verbosity of HTTP libraries
    for logger_name in ('anthropic', 'httpcore', 'httpx'):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def determine_iterator_type(
    args: argparse.Namespace,
) -> engine.AutomationIterator:
    """Determine the iterator type based on CLI arguments.

    Args:
        args: Parsed command line arguments

    Returns:
        AutomationIterator enum value corresponding to the target type

    """
    if args.imbi_project_id:
        return engine.AutomationIterator.imbi_project
    elif args.imbi_project_type:
        return engine.AutomationIterator.imbi_project_types
    elif args.all_imbi_projects:
        return engine.AutomationIterator.imbi_projects
    elif args.github_repository:
        return engine.AutomationIterator.github_project
    elif args.github_organization:
        return engine.AutomationIterator.github_organization
    elif args.all_github_repositories:
        return engine.AutomationIterator.github_repositories
    elif args.gitlab_repository:
        return engine.AutomationIterator.gitlab_project
    elif args.gitlab_group:
        return engine.AutomationIterator.gitlab_group
    elif args.all_gitlab_repositories:
        return engine.AutomationIterator.gitlab_repositories
    else:
        raise ValueError('No valid target argument provided')


def load_configuration(config_file: typing.TextIO) -> models.Configuration:
    """Load configuration from config file

    Args:
        config_file: Path to the main configuration file or file-like object

    Returns:
        Configuration object with merged data

    Raises:
        tomllib.TOMLDecodeError: If TOML parsing fails
        pydantic.ValidationError: If configuration validation fails

    """
    return models.Configuration.model_validate(utils.load_toml(config_file))


def workflow(path: str) -> pathlib.Path:
    """Run a workflow from a directory.

    @TODO have it load in/return the Workflow model once it's created

    """
    path_obj = pathlib.Path(path)
    if not path_obj.is_dir() or not (path_obj / 'config.toml').is_file():
        raise argparse.ArgumentTypeError(f'Invalid workflow path: {path}')
    return path_obj


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Imbi Automations',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.register('type', 'workflow', workflow)
    parser.add_argument(
        'config',
        type=argparse.FileType('r'),
        metavar='CONFIG',
        help='Configuration file',
        nargs=1,
    )
    parser.add_argument(
        'workflow',
        metavar='WORKFLOW',
        type='workflow',
        help='Path to the directory containing the workflow to run',
    )

    # Target argument group - specify how to target repositories
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument(
        '--imbi-project-id',
        type=int,
        metavar='ID',
        help='Process a single project by Imbi Project ID',
    )
    target_group.add_argument(
        '--imbi-project-type',
        metavar='SLUG',
        help='Process all Imbi projects of a specific type slug',
    )
    target_group.add_argument(
        '--all-imbi-projects',
        action='store_true',
        help='Process all Imbi projects',
    )
    target_group.add_argument(
        '--github-repository',
        metavar='URL',
        help='Process a single GitHub repository by URL',
    )
    target_group.add_argument(
        '--github-organization',
        metavar='ORG',
        help='Process all repositories in a GitHub organization',
    )
    target_group.add_argument(
        '--all-github-repositories',
        action='store_true',
        help='Process all GitHub repositories across all organizations',
    )
    target_group.add_argument(
        '--gitlab-repository',
        metavar='URL',
        help='Process a single GitLab repository by URL',
    )
    target_group.add_argument(
        '--gitlab-group',
        metavar='GROUP',
        help='Recursively process all repositories in a GitLab group',
    )
    target_group.add_argument(
        '--all-gitlab-repositories',
        action='store_true',
        help='Process all GitLab repositories across all organizations',
    )

    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-V', '--version', action='version', version=version)
    return parser.parse_args(args)


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)

    config = load_configuration(args.config[0])
    args.config[0].close()

    LOGGER.info('Imbi Automations v%s starting', version)
    ae = engine.AutomationEngine(config, determine_iterator_type(args))
    try:
        ae.run()
    except KeyboardInterrupt:
        LOGGER.info('Interrupted, exiting')
