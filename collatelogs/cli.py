# -*- coding: utf-8 -*-

"""Command-Line Interface for collatelogs"""

from __future__ import absolute_import, print_function, unicode_literals

import argparse
from glob import glob
import logging
import os
import sys

from .logcollator import LogCollator
from .util import read_config

logger = logging.getLogger(__name__)

CONFIG_SEARCH_PATHS = [os.path.realpath(path) for path in [
    os.path.join(os.path.expanduser('~'), '.cl_config.yaml'),
    './config.yaml',
    (os.path.join(os.path.dirname(__file__), 'example_config.yaml'))
]]

REQUIRED_CONFIG_FIELDS = ['log_parsing_info', 'line_output_format']


def check_config(config):
    for field in REQUIRED_CONFIG_FIELDS:
        if field not in config:
            raise ValueError("Field {} is a required field, but is absent from the config!"
                             .format(field))

        if not config['log_parsing_info']:
            raise ValueError("log_parsing_info must have at least one entry!")

        for info in config['log_parsing_info']:
            if 'regex' not in info:
                raise ValueError(
                    "log_parsing_info entries must contain a regex key")


def find_config_file():
    """Search CONFIG_SEARCH_PATHS until config file is found; open and return it"""
    for config_path in CONFIG_SEARCH_PATHS:
        logger.debug("Searching for config file at: %s", config_path)
        try:
            config = read_config(config_path)
        except IOError:
            pass
        else:
            logger.debug("Found config file at: %s", config_path)
            if not isinstance(config, dict):
                raise ValueError(
                    "config file did not parse to a dict; it must be malformed")
            check_config(config)
            return config, config_path

    raise ValueError("Could not find any config file!")


def parse_args():
    """Perform argument parsing"""

    # Create a "dummy" parser that _only_ parses out the --config argument. We need this in order
    # to open the config file and load its values prior to the "real parser"
    _parser = argparse.ArgumentParser(add_help=False)
    _parser.add_argument('-c', '--config')
    # Parse only the args that we "know" about (--config)
    _args, remaining_args = _parser.parse_known_args()

    # If --config has been given, use it
    if _args.config:
        config = read_config(_args.config)
    else:
        # Otherwise look through common locations for the config. Error if one isn't found
        config, config_path = find_config_file()
        # No config key in the config file, so just set it here
        config['config'] = config_path

    # Initialize the "real" parser
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="A simple log collator. NOTE: Defaults are based on the selected "
                    "config file (indicated by the default in --config). Arguments given here will always "
                    "override the config file defaults",
        prog="collatelogs"
    )
    # Use the config file to populate defaults for the rest of the arguments
    # NOTE: This also populates things we never create arguments for -- we depend on this behavior,
    # because we treat args as the config object post-parsing
    parser.set_defaults(**config)

    # Arg time!
    parser.add_argument(
        'logs',
        metavar='PATH',
        nargs='+',
        help="Log file paths"
    )
    parser.add_argument(
        '-t', '--parse-timestamps',
        action='store_true',
        help="Enable reformatting of datetime prefixes. This will be MUCH "
             "slower! Uses the format indicated by --timestamp-output-format"
    )
    parser.add_argument(
        '-T', '--timestamp-output-format',
        metavar='FORMAT',
        help="NOTE: If given, this will enable reformatting of datetime "
             "prefixes. This will be much slower!"
    )
    parser.add_argument(
        '-L', '--line-output-format',
        metavar='FORMAT',
        help='The output format of the log line. This is a "new style"'
             'format'
    )
    parser.add_argument(
        '-b', '--bad-line-behavior',
        choices=('keep', 'discard', 'error'),
        help="Defines the action taken when a line is found that doesn't match any of the given line regexes. "
             "keep: Keep the line in the output (this is almost certainly a _bad_ idea). discard: silently discard "
             "non-matching lines. error: Raise an error at the first instance of non-matching"
    )
    parser.add_argument(
        '--allow-duplicates',
        action='store_true',
        help="If given, don't remove duplicate log lines from the output. "
             "NOTE: Lines are considered duplicate only if they are EXACTLY "
             "the same, including timestamp"
    )
    parser.add_argument(
        '--no-strip',
        action='store_true',
        help='Indicates that lines should not be stripped of whitespace'
    )
    parser.add_argument(
        '-c', '--config',
        metavar='PATH',
        help="The path to the config file. If this is not given, the "
             "following paths will be searched: {}".format(
                 [str(p) for p in CONFIG_SEARCH_PATHS]),
    )
    parser.add_argument(
        '-P', '--no-progress',
        action='store_true',
        help="Indicate this if you don't want the progress bar (slightly faster)"
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help="Increase logging verbosity. NOTE: This will also hide tracebacks (error text still shown)!"
    )

    parsed_args = parser.parse_args(remaining_args)

    # Expand all of the given globs and replace the entry in parsed_args with the expanded version
    logs = []
    for log in parsed_args.logs:
        logs.extend(glob(log))
    if not logs:
        parser.error('Either none of the given paths {} exist, or none of them '
                     'contain files!'.format(parsed_args.logs))
    parsed_args.logs = logs

    return parser.parse_args()


def main():
    """Entry point"""

    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Set logging level to DEBUG")
    else:
        # Only show the error text from tracebacks if we aren't in verbose mode
        sys.tracebacklimit = 0

    config = args.__dict__
    logger.debug("config:\n%s", config)
    if logger.level <= logging.INFO:
        logger.debug("--- Begin execution overview ---")
        logger.debug(
            "Consuming log lines based on the following prefix information:")
        for i, info in enumerate(config['log_parsing_info'], 1):
            logger.debug("  %d. regex: %s", i, info['regex'])
            logger.debug("  %d. timezone: %s", i,
                         info['timezone'] if 'timezone' in info else 'local')
            logger.debug("  %d. timestamp format: %s", i,
                         info['timestamp_format'] if 'timestamp_format' in info
                         else 'None given; dateutil will be used to parse')

        if config['parse_timestamps']:
            logger.debug("Reformatting timestamps into format: %s",
                         config['date_format'])
        logger.debug("--- End execution overview ---")

    # If user has not requested timestamp parsing, set date_format to None
    # to indicate that it is not needed
    if args.parse_timestamps:
        date_format = config['date_format']
    else:
        date_format = None
    lines = LogCollator(
        log_paths=args.logs,
        line_output_format=config['line_output_format'],
        date_format=date_format,
        log_parsing_info=config['log_parsing_info'],
        bad_line_behavior=args.bad_line_behavior,
        allow_duplicates=args.allow_duplicates,
    ).collate(show_progress=not args.no_progress)

    print("\n".join(lines))
