# -*- coding: utf-8 -*-

"""Collates a given set of log files"""

from __future__ import absolute_import, print_function, unicode_literals

from datetime import datetime
import logging
import os
import sys
import warnings

try:
    import dateutil.parser as dp
except ImportError:
    warnings.warn("dateutil not found; generic date parsing will not be possible -- "
                  "that is, all timestamp formats must be specified in the config. "
                  "Also, timezone conversion will not be possible. That is, if "
                  "a non-local timezone is specified in the config, an error will be raised. "
                  "Consider running this in an environment with dateutil installed")


try:
    from tqdm import tqdm
    # Due to TQDM bug? https://github.com/tqdm/tqdm/issues/481
    tqdm.monitor_interval = 0
except ImportError:
    warnings.warn("tqdm not found; progress bars will not function. "
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
            date_format=None,
            bad_line_behavior='error',
            allow_duplicates=False,
            subsecond_digits=3,
            strip_lines=True
    ):
        if not line_output_format.startswith('{timestamp'):
            raise ValueError("line_output_format must start with 'timestamp'")

        for info in log_parsing_info:
            if date_format and 'timestamp_format' not in info and 'dateutil' not in sys.modules:
                raise ValueError("You have indicated a date_format which requires "
                                 "date parsing, but no timestamp_format is specified in the config, "
                                 "and dateutil is not installed!")

        self.meta_handlers = all_meta_handlers

        self.log_parsing_info = log_parsing_info
        # Precompile all regexes
        compile_regexes(self.log_parsing_info)
        regexes = [info['regex'] for info in self.log_parsing_info]
        if not check_that_regexes_are_all_supersets_of_format_string(regexes, self.meta_handlers.keys(), line_output_format):
            raise ValueError("Keywords in prefix output format must be a subset of each prefix regex's groups! "
                             "That is, you have included keywords in the format string that are not in one or more "
                             "of the given regexes")

        self.log_paths = log_paths
        self.line_output_format = line_output_format
        self.line_output_format_keywords = extract_keywords_from_format_string(
            line_output_format)
        self.date_format = date_format

        self.bad_line_behavior = bad_line_behavior
        self.allow_duplicates = allow_duplicates
        self.subsecond_digits = subsecond_digits
        self.strip_lines = strip_lines

    def amend_prefix(self, line, meta=None):
        """Given a line from a log file, insert its filename and return it"""
        if not meta:
            meta = {}

        # A single prefix info dict
        parsing_info = match_first(line, self.log_parsing_info)
        if not parsing_info:
            raise ValueError("Line {!r} did not match against any of the given regexes!"
                             .format(line))
        kwargs_from_regex = parsing_info['match']

        kwargs_for_format = meta
        kwargs_for_format.update(kwargs_from_regex)
        # kwargs_for_format = dict(**meta, **kwargs_from_regex)

        if self.date_format:
            if 'timestamp_format' in parsing_info:
                parsed_timestamp = datetime.strptime(
                    kwargs_for_format['timestamp'], parsing_info['timestamp_format'])
            else:
                parsed_timestamp = dp.parse(kwargs_for_format['timestamp'])

            if 'log_timezone' in parsing_info and parsing_info['log_timezone']:
                if 'output_timezone' in parsing_info and parsing_info['output_timezone']:
                    output_timezone = parsing_info['output_timezone']
                else:
                    output_timezone = None

                parsed_timestamp = convert_timezone(
                    parsed_timestamp, parsing_info['log_timezone'], output_timezone)

            kwargs_for_format['timestamp'] = parsed_timestamp.strftime(
                self.date_format)

        reformatted = self.line_output_format.format(**kwargs_for_format)
        if self.strip_lines:
            reformatted = reformatted.strip()

        if self.date_format:
            return (parsed_timestamp, reformatted)
        else:
            return reformatted

    def process_lines(self, path_map, progress=None, update_interval=100):
        log_lines = []
        for log_path, path_data in path_map.items():
            path_meta = {key: handler(log_path)
                         for key, handler in self.meta_handlers.items()}
            for i, line in enumerate(path_data['lines']):
                try:
                    amended_line = self.amend_prefix(
                        line,
                        # Below this are included in kwargs
                        meta=path_meta
                    )
                    log_lines.append(amended_line)
                except ValueError:
                    if self.bad_line_behavior == 'keep':
                        log_lines.append(line)
                    elif self.bad_line_behavior == 'error':
                        raise

                if progress and i % update_interval == 0:
                    progress.update(update_interval)

        return log_lines

    def collate(self, show_progress=True):
        path_map = {}
        for log_path in self.log_paths:
            path_map[log_path] = {}
            try:
                with open(log_path) as log_file:
                    path_map[log_path]['lines'] = log_file.readlines()
            except IOError:
                logger.warning('Could not read file %s', log_path)

        total_lines = sum([len(data['lines']) for data in path_map.values()])
        if not total_lines:
            logger.warning("No lines to process!")
            return []

        # Show progress bars if possible
        if 'tqdm' in sys.modules and show_progress:
            with tqdm(total=total_lines, unit='lines') as progress:
                log_lines = self.process_lines(path_map, progress)
        else:
            log_lines = self.process_lines(path_map)

        # If we are not allowing duplicates, remove duplicates
        if not self.allow_duplicates:
            log_lines = set(log_lines)

        if self.date_format:
            return [line[1] for line in sorted(log_lines, key=lambda x: x[0])]
        else:
            return sorted(log_lines)
