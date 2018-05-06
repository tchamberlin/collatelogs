# -*- coding: utf-8 -*-

"""Collate a given set of log files"""

from __future__ import absolute_import, print_function, unicode_literals

from datetime import datetime
import logging
import sys
import warnings

try:
    import dateutil.parser as dp
except ImportError:
    warnings.warn(
        "dateutil not found; generic date parsing will not be possible -- that "
        "is, all timestamp formats must be specified in the config. Also, "
        "timezone conversion will not be possible. That is, if a non-local "
        "timezone is specified in the config, an error will be raised. "
        "Consider running this in an environment with dateutil installed"
    )

try:
    from tqdm import tqdm
    # Due to TQDM bug? https://github.com/tqdm/tqdm/issues/481
    tqdm.monitor_interval = 0
except ImportError:
    warnings.warn("tqdm not found; progress bars will be unavailable. "
                  "Consider running this in an environment with tqdm installed")

from .metahandlers import all_meta_handlers
from .util import (
    compile_regexes,
    match_first,
    check_that_regexes_are_all_supersets_of_format_string,
    extract_keywords_from_format_string,
    convert_timezone
)


logger = logging.getLogger(__name__)


class LogCollator(object):
    def __init__(
            self,
            log_paths,
            line_output_format,
            log_parsing_info,
            timestamp_output_format=None,
            bad_line_behavior='error',
            allow_duplicates=False,
            subsecond_digits=3,
            strip_lines=True
    ):
        if not line_output_format.startswith('{timestamp'):
            raise ValueError(r"line_output_format must start with '{timestamp}'")

        for info in log_parsing_info:
            if timestamp_output_format and 'timestamp_input_format' not in info and 'dateutil' not in sys.modules:
                raise ValueError("You have indicated a timestamp_output_format which requires "
                                 "date parsing, but no timestamp_input_format is specified in the config, "
                                 "and dateutil is not installed!")

        # TODO: This is being called twice currently; refactor
        line_output_format_keywords = extract_keywords_from_format_string(line_output_format)
        self.meta_handlers = {
            name: handler for name, handler in all_meta_handlers.items()
            if name in line_output_format_keywords
        }
        logger.debug("Using meta handlers: %s", self.meta_handlers.keys())
        self.log_parsing_info = log_parsing_info
        # Precompile all regexes
        compile_regexes(self.log_parsing_info)
        regexes = [info['regex'] for info in self.log_parsing_info]
        if not check_that_regexes_are_all_supersets_of_format_string(regexes, self.meta_handlers.keys(), line_output_format):
            raise ValueError(
                "Keywords in prefix output format must be a subset of each "
                "prefix regex's groups! That is, you have included keywords "
                "in the format string that are not in one or more of the "
                "given regexes")

        self.log_paths = log_paths
        self.line_output_format = line_output_format
        self.timestamp_output_format = timestamp_output_format

        self.bad_line_behavior = bad_line_behavior
        self.allow_duplicates = allow_duplicates
        self.subsecond_digits = subsecond_digits
        self.strip_lines = strip_lines

    def amend_prefix(self, line, meta=None):
        """Given a line from a log file, insert its filename and return it"""
        if not meta:
            meta = {}

        # A single parsing info dict (i.e. one regex and its associated data)
        parsing_info = match_first(line, self.log_parsing_info)
        if not parsing_info:
            raise ValueError("Line {!r} did not match against any of the given regexes!"
                             .format(line))
        # Can't use keyword expansion here due to Pyhton 2.7 support
        kwargs_for_format = meta
        kwargs_from_regex = parsing_info['match']
        kwargs_for_format.update(kwargs_from_regex)

        # If a timestamp output format is given, use it to reformat timestamp output
        if self.timestamp_output_format:
            # If a timestamp input format is given, use it to parse the prefix timestamp
            if 'timestamp_input_format' in parsing_info:
                parsed_timestamp = datetime.strptime(
                    kwargs_for_format['timestamp'],
                    parsing_info['timestamp_input_format']
                )
            # Otherwise, use dateutil to generically parse the timestamp
            else:
                parsed_timestamp = dp.parse(kwargs_for_format['timestamp'])

            timestamp_input_timezone = parsing_info.get('timestamp_input_timezone', None)
            timestamp_output_timezone = parsing_info.get('timestamp_output_timezone', None)
            # If either timestamp_input_timezone or timestamp_output_timezone
            # is given, the user wants to convert time zone
            if timestamp_input_timezone or timestamp_output_timezone:
                parsed_timestamp = convert_timezone(
                    dt=parsed_timestamp,
                    tz_from=timestamp_input_timezone,
                    tz_to=timestamp_output_timezone
                )

            kwargs_for_format['timestamp'] = parsed_timestamp.strftime(
                self.timestamp_output_format)

        reformatted = self.line_output_format.format(**kwargs_for_format)
        if self.strip_lines:
            reformatted = reformatted.strip()

        if self.timestamp_output_format:
            return (parsed_timestamp, reformatted)
        return reformatted

    def process_path_map(self, path_map, progress=None, update_interval=100):
        """Process lines in path_map based on other keys"""

        all_log_lines = []
        for log_path, log_lines in path_map.items():
            # Call all meta handlers and map returned values to keywords
            # These will be used downstream to populate the line_output_format
            # Note that this might be empty -- it depends on whether meta
            # keywords have been specified in line_output_format
            path_meta_keywords = {key: handler(log_path) for key, handler in self.meta_handlers.items()}
            # Amend all lines
            for line_number, line in enumerate(log_lines):
                try:
                    amended_line = self.amend_prefix(line, meta=path_meta_keywords)
                    all_log_lines.append(amended_line)
                except ValueError:
                    if self.bad_line_behavior == 'keep':
                        all_log_lines.append(line)
                    elif self.bad_line_behavior == 'error':
                        raise
                    # Otherwise discard

                # line_number is only used to enforce the update_interval
                if progress and line_number % update_interval == 0:
                    progress.update(update_interval)

        return all_log_lines

    def collate(self, show_progress=True):
        """Collate log paths"""

        # A map of log paths to their lines
        path_map = {}
        # Populate path map --
        for log_path in self.log_paths:
            path_map[log_path] = {}
            try:
                with open(log_path) as log_file:
                    path_map[log_path] = log_file.readlines()
            except IOError:
                logger.warning('Could not read file %s', log_path)

        # Determine sum of total lines in all log files
        total_lines = sum([len(lines) for lines in path_map.values()])
        # Bail if there are no lines to process
        if not total_lines:
            logger.warning("No lines to process!")
            return []

        if 'tqdm' in sys.modules and show_progress:
            # Show progress bars if possible and requested...
            with tqdm(total=total_lines, unit='lines') as progress:
                log_lines = self.process_path_map(path_map, progress)
        else:
            # ...otherwise don't
            log_lines = self.process_path_map(path_map)

        # Remove duplicates if requested
        if not self.allow_duplicates:
            log_lines = set(log_lines)

        # If timestamp_output_format is set, log_lines will be a list
        # of tuples of the format (timestamp_dt, line). This is because
        # timestamp_dt can be used to sort, since it has already been parsed.
        # This can be much more accurate than an alphabetical sort, depending
        # on the timestamp_output_format used (e.g. if only years are printed
        # out, sorting alphabetically work at all)
        if self.timestamp_output_format:
            return [line[1] for line in sorted(log_lines, key=lambda x: x[0])]
        # Otherwise to a basic alphabetical sort (since we haven't parsed
        # timestamps)
        return sorted(log_lines)
