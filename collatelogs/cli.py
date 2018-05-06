# -*- coding: utf-8 -*-

"""Command-Line Interface for collatelogs"""

from __future__ import absolute_import, print_function, unicode_literals

import argparse
from glob import glob
import logging
import os
import sys
import warnings

try:
    from pytz import timezone
except ImportError:
    warnings.warn("pytz not found; timezone conversion will not be possible. That is, if "
                  "a non-local timezone is specified in the config, an error will be raised. "
                  "Consider running this in an environment with dateutil installed")
try:
    from tzlocal import get_localzone
except ImportError:
    warnings.warn("tzlocal not found; timezone conversion will not be possible. That is, if "
                  "a non-local timezone is specified in the config, an error will be raised. "
                  "Consider running this in an environment with dateutil installed")

from .logcollator import LogCollator
from .util import read_config

logger = logging.getLogger(__name__)

CONFIG_SEARCH_PATHS = [os.path.realpath(path) for path in [
    os.path.join(os.path.expanduser('~'), '.cl_config.yaml'),
    './config.yaml',
    (os.path.join(os.path.dirname(__file__), 'example_config.yaml'))
]]

REQUIRED_CONFIG_FIELDS = ['log_parsing_info', 'line_output_format']

LOCAL_TIMEZONE = get_localzone()


class ConfigFileError(ValueError):
    pass


def check_config(config):
    for field in REQUIRED_CONFIG_FIELDS:
        if field not in config:
            raise ConfigFileError("Field {} is a required field, but is absent from the config!".format(field))

        if not config['log_parsing_info']:
            raise ConfigFileError("log_parsing_info must have at least one entry!")

    for info_index, info in enumerate(config['log_parsing_info']):
        if 'regex' not in info:
            raise ConfigFileError(
                "log_parsing_info[{}] does not contain a regex key"
                .format(info_index)
            )

        if 'timestamp_input_timezone' in info or 'timestamp_output_timezone' in info:
            if 'timestamp_input_timezone' in info:
                logger.debug("Converting timestamp_input_timezone (%s) to timezone object",
                             info['timestamp_input_timezone'])
                info['timestamp_input_timezone'] = timezone(info['timestamp_input_timezone'])
            else:
                logger.debug("Converting blank timestamp_input_timezone to local timezone object")
                info['timestamp_input_timezone'] = LOCAL_TIMEZONE
            if 'timestamp_output_timezone' in info:
                logger.debug("Converting timestamp_output_timezone (%s) to timezone object",
                             info['timestamp_output_timezone'])
                info['timestamp_output_timezone'] = timezone(info['timestamp_output_timezone'])
            else:
                logger.debug("Converting blank timestamp_output_timezone to local timezone object")
                info['timestamp_output_timezone'] = LOCAL_TIMEZONE

            if info['timestamp_input_timezone'] == info['timestamp_output_timezone']:
                logger.warning(
                    "log_parsing_info[%s]'s timestamp_input_timezone and timestamp_output_timezone are both set to %s; "
                    "conversion will accomplish nothing", info_index, info['timestamp_input_timezone']
                )


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
            return config, config_path

    raise ValueError("Could not find any config file!")


def parse_args():
    """Perform argument parsing"""

    # Create a "dummy" parser that _only_ parses out the --config argument.
    # This is the first stage in the two-stage argument-parsing process
    _parser = argparse.ArgumentParser(add_help=False)
    _parser.add_argument('-c', '--config')
    # Parse only known args here so that the rest can be used below (--config)
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
    # NOTE: This also populates defaults for arguments that are never created --
    # this is important because args are treated as "the config" below
    parser.set_defaults(**config)

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

    return parser.parse_args(), config


def main():
    """Entry point"""

    args, config = parse_args()


    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Set logging level to DEBUG")
    else:
        # Only show the error text from tracebacks if verbose mode not active
        sys.tracebacklimit = 0

    # Wait to check the config until here in order to respect --verbose
    check_config(config)

    # Pull out the dict from args object and use it as "the config"
    logger.debug("args: %s", args)
    if logger.level <= logging.INFO:
        logger.debug("--- Begin execution overview ---")
        logger.debug("Parsing log lines based on the following information:")
        for i, info in enumerate(args.log_parsing_info, 1):
            logger.debug("  %d. regex: %s", i, info['regex'])
            logger.debug("  %d. timezone: %s", i,
                         info['timezone'] if 'timezone' in info else 'local')
            logger.debug("  %d. timestamp format: %s", i,
                         info['timestamp_input_format'] if 'timestamp_input_format' in info
                         else 'None given; dateutil will be used to parse')

        if args.parse_timestamps:
            logger.debug("Reformatting timestamps into format: %s",
                         args.timestamp_output_format)
        logger.debug("--- End execution overview ---")

    # If user has not requested timestamp parsing, set timestamp_output_format to None
    # to indicate that it is not needed
    if args.parse_timestamps:
        timestamp_output_format = args.timestamp_output_format
    else:
        timestamp_output_format = None

    # Perform log collation
    lines = LogCollator(
        log_paths=args.logs,
        line_output_format=args.line_output_format,
        timestamp_output_format=timestamp_output_format,
        log_parsing_info=args.log_parsing_info,
        bad_line_behavior=args.bad_line_behavior,
        allow_duplicates=args.allow_duplicates,
    ).collate(show_progress=not args.no_progress)

    print("\n".join(lines))
