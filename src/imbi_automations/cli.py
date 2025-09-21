import argparse
import logging

import colorlog

from imbi_automations import utils, version

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


def parse_args(*args: tuple[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Imbi Automations',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        'config', metavar='CONFIG', help='Configuration file', nargs=1
    )
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-V', '--version', action='version', version=version)
    return parser.parse_args(*args)


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)
    config = utils.load_configuration(args.config[0])
    LOGGER.info('Imbi Automations v%s starting', version)
