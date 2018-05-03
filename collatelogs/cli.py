import argparse
from glob import glob
import os

from collatelogs.collatelogs import format_simple, format_advanced
from collatelogs.util import read_config

DEFAULT_CONFIG_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), 'config.yaml'))

def get_value_from_arg_or_config(key, args, config):
    if key in args.__dict__ and args.__dict__[key]:
        value = args.__dict__[key]
    else:
        try:
            value = config[key]
        except KeyError:
            raise ValueError('{} must be specified either as an argument or '
                             'in the config file!'.format(key))

    return value


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        'logs',
        nargs='+',
        help="Sparrow log file paths"
    )
    parser.add_argument(
        '-d', '--parse-timestamps',
        action='store_true',
        help="Enable reformatting of datetime prefixes. This will be MUCH "
             "slower! Uses the format indicated by --date-format"
    )
    parser.add_argument(
        '-l', '--timestamp-length',
        type=int,
        help='The length of the timestamp at the beginning of each log line. '
             'If given, only basic formatting will be available. Fast!'
    )
    parser.add_argument(
        '-b', '--bad-line-behavior',
        choices=('keep', 'discard', 'error'),
        help="TODO"
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
        help='Indicates that lines should not be stripped. NOTE: This only '
             'has an effect if in "simple" mode'
    )
    parser.add_argument(
        '-p', '--precision',
        type=int,
        default=3,
        choices=range(1, 7),
        help="The precision of the microsecond string format (if given), as a "
             "number of digits (defaults to milliseconds)"
    )
    parser.add_argument(
        '-P', '--pad-milli',
        action='store_true',
        help="Use this option if you have timestamps with formats that differ only "
             "in their inclusion of milliseconds. That is, if one timestamp format "
             "includes millisconds, but others don't, then you can give this argument "
             "to pad those that don't. This will allow them to sort properly. NOTE: "
             "This accomplishes the same thing as --date-format, but is MUCH faster "
             "(if this is the only difference in date formats)"
    )
    parser.add_argument(
        '-c', '--config',
        help="The path to the config file",
        default=DEFAULT_CONFIG_PATH
    )

    config_group = parser.add_argument_group(
        'config',
        'These arguments will override config file values'
    )
    config_group.add_argument(
        '-D', '--date-format',
        help="NOTE: If given, this will enable reformatting of datetime "
             "prefixes. This will be much slower!"
    )
    config_group.add_argument(
        '-f', '--prefix-output-format',
        help='The output format of the log line prefix. This is a "new style"'
             'format'
    )
    config_group.add_argument(
        '-r', '--prefix-regexes',
        metavar="PREFIX_REGEX",
        nargs='+',
        help='A regular expression indicating the expected format(s) of '
             'the given logs. These will be tried in the given order, and the '
             'first match will be used. If no match is found, an error will be '
             'raised'
    )
    parsed_args = parser.parse_args()
    logs = []
    for log in parsed_args.logs:
        logs.extend(glob(log))

    if not logs:
        parser.error('Either none of the given paths {} exist, or none of them '
                     'contain files!'.format(parsed_args.logs))

    parsed_args.logs = logs
    return parsed_args



def main():
    args = parse_args()
    if args.timestamp_length:
        lines = format_simple(
            log_paths=args.logs,
            timestamp_length=args.timestamp_length,
            allow_duplicates=args.allow_duplicates,
            bad_line_behavior=args.bad_line_behavior,
            no_strip=args.no_strip
        )
    else:
        config = read_config(args.config)
        prefix_regexes = get_value_from_arg_or_config('prefix_regexes', args, config)
        date_format = get_value_from_arg_or_config('date_format', args, config)
        prefix_output_format = get_value_from_arg_or_config('prefix_output_format', args, config)

        # If user has not requested timestamp parsing, set date_format to None
        # to indicate that it is not needed
        if not args.parse_timestamps:
            date_format = None
        lines = format_advanced(
            log_paths=args.logs,
            prefix_output_format=prefix_output_format,
            date_format=date_format,
            prefix_regexes=prefix_regexes,
            bad_line_behavior=args.bad_line_behavior,
            allow_duplicates=args.allow_duplicates,
            pad_milliseconds=args.pad_milli,
            subsecond_digits=args.precision
        )

    print("\n".join(lines))
