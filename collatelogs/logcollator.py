# -*- coding: utf-8 -*-

"""Collate a given set of log files"""

from __future__ import absolute_import, print_function, unicode_literals
import contextlib
from datetime import time, datetime, timedelta
import logging
import re
import sys
import warnings
from pytz import timezone

try:
    from tzlocal import get_localzone
except ImportError:
    warnings.warn(
        "tzlocal not found; timezone conversion will not be possible. That is, if "
        "a non-local timezone is specified in the config, an error will be raised. "
        "Consider running this in an environment with dateutil installed"
    )

try:
    import dateutil.parser as dp
    from dateutil.relativedelta import relativedelta
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
    warnings.warn(
        "tqdm not found; progress bars will be unavailable. "
        "Consider running this in an environment with tqdm installed"
    )

from .metahandlers import all_meta_handlers
from .util import (
    compile_regexes,
    match_first,
    check_that_regexes_are_all_supersets_of_format_string,
    debug_regexes_str,
    extract_keywords_from_format_string,
    convert_timezone,
)


logger = logging.getLogger(__name__)


class LogCollator(object):
    def __init__(
        self,
        log_paths,
        line_output_format,
        log_parsing_info,
        timestamp_output_format=None,
        bad_line_behavior="error",
        allow_duplicates=False,
        subsecond_digits=3,
        strip_lines=True,
    ):
        if not line_output_format.startswith("{timestamp"):
            raise ValueError(r"line_output_format must start with '{timestamp}'")

        for info in log_parsing_info:
            if (
                timestamp_output_format
                and "timestamp_input_format" not in info
                and "dateutil" not in sys.modules
            ):
                raise ValueError(
                    "You have indicated a timestamp_output_format which requires "
                    "date parsing, but no timestamp_input_format is specified in the config, "
                    "and dateutil is not installed!"
                )

        # TODO: This is being called twice currently; refactor
        line_output_format_keywords = extract_keywords_from_format_string(
            line_output_format
        )
        self.meta_handlers = {
            name: handler
            for name, handler in all_meta_handlers.items()
            if name in line_output_format_keywords
        }
        self.log_parsing_info = log_parsing_info
        # Precompile all regexes
        compile_regexes(self.log_parsing_info)
        regexes = [info["line_regex"] for info in self.log_parsing_info]
        debug_info = debug_regexes_str(
            # TODO: HACK! debug_regexes_str should take a single iterable to check, so we
            # don't have to do this
            regexes,
            [*self.meta_handlers.keys(), "name"],
            line_output_format,
        )
        for line in debug_info:
            logger.error(line)
        if not check_that_regexes_are_all_supersets_of_format_string(
            # TODO: HACK! debug_regexes_str should take a single iterable to check, so we
            # don't have to do this
            regexes,
            [*self.meta_handlers.keys(), "name"],
            line_output_format,
        ):
            raise ValueError(
                "Keywords in prefix output format must be a subset of each "
                "prefix regex's groups! That is, you have included keywords "
                "in the format string that are not in one or more of the "
                "given regexes. See log for more details"
            )

        self.log_paths = log_paths
        self.line_output_format = line_output_format
        self.timestamp_output_format = timestamp_output_format

        self.bad_line_behavior = bad_line_behavior
        self.allow_duplicates = allow_duplicates
        self.subsecond_digits = subsecond_digits
        self.strip_lines = strip_lines

    def amend_prefix_no_parse_timestamp(self, line, meta=None, prev_timestamp=None):
        """Given a line from a log file, insert its filename and return it"""
        if not meta:
            meta = {}

        parsing_info = match_first(line, self.log_parsing_info, "line_regex")
        # TODO: Broken until we are doing per-file determination of parsing_info
        # if not parsing_info and prev_timestamp:
        #     fixed_line = f"{prev_timestamp}{line}"
        #     parsing_info = match_first(fixed_line, self.log_parsing_info, "line_regex")

        #     if not parsing_info:
        #         raise ValueError(
        #             "Line {!r} did not match against any of the given regexes!".format(
        #                 fixed_line
        #             )
        #         )
        #     logger.warning(f"Added timestamp! ({line!r} -> {fixed_line!r}")

        if not parsing_info:
            raise ValueError(
                "Line {!r} did not match against any of the given regexes!".format(line)
            )
        # Can't use keyword expansion here due to Python 2.7 support
        kwargs_for_format = meta
        kwargs_from_regex = parsing_info["match"]
        kwargs_for_format.update(kwargs_from_regex)
        kwargs_for_format["name"] = parsing_info["name"]
        reformatted = self.line_output_format.format(**kwargs_for_format)

        print(reformatted)
        return reformatted, kwargs_from_regex

    def parse_timestamp(self, timestamp, timestamp_format, base_datetime=None):
        # If a timestamp input format is given, use it to parse the prefix timestamp
        if timestamp_format:
            parsed_timestamp = datetime.strptime(timestamp, timestamp_format)
        # Otherwise, use dateutil to generically parse the timestamp
        else:
            parsed_timestamp = dp.parse(timestamp)

        if base_datetime and parsed_timestamp.year == 1900:
            parsed_timestamp = datetime(
                year=base_datetime.year,
                month=base_datetime.month,
                day=base_datetime.day,
                hour=parsed_timestamp.hour,
                minute=parsed_timestamp.minute,
                second=parsed_timestamp.second,
                microsecond=parsed_timestamp.microsecond,
            )

        if parsed_timestamp.year == 1900:
            raise ValueError(f"Error parsing {timestamp}")

        return parsed_timestamp

    def amend_prefix_parse_timestamp(
        self, line, meta=None, filename_date=None, previous_line_date=None
    ):
        """Given a line from a log file, insert its filename and return it"""
        if not meta:
            meta = {}

        # A single parsing info dict (i.e. one regex and its associated data)
        parsing_info = match_first(line, self.log_parsing_info, "line_regex")
        if not parsing_info:
            # TODO: Add to config! Broken until then
            # if previous_line_date:
            #     prev_ts = previous_line_date.strftime("%H:%M:%S")
            #     fixed_line = f"[{prev_ts}] {line}"
            #     parsing_info = match_first(
            #         fixed_line, self.log_parsing_info, "line_regex"
            #     )
            if not parsing_info:
                raise ValueError(
                    "Line {!r} did not match against any of the given regexes!".format(
                        line
                    )
                )

        # Can't use keyword expansion here due to Python 2.7 support
        kwargs_for_format = meta
        kwargs_from_regex = parsing_info["match"]
        kwargs_for_format.update(kwargs_from_regex)
        # If a timestamp output format is given, use it to reformat timestamp output
        if self.timestamp_output_format:
            parsed_timestamp = self.parse_timestamp(
                timestamp=kwargs_for_format["timestamp"],
                timestamp_format=parsing_info.get("timestamp_input_format", None),
                base_datetime=(
                    previous_line_date if previous_line_date else filename_date
                ),
            )

            # If parsed_timestamp is naive...
            if not getattr(parsed_timestamp, "tzinfo", None):
                timestamp_input_timezone = parsing_info.get(
                    "timestamp_input_timezone", None
                )
                timestamp_output_timezone = parsing_info.get(
                    "timestamp_output_timezone", None
                )
                # If either timestamp_input_timezone or timestamp_output_timezone
                # is given, the user wants to convert time zone
                if timestamp_output_timezone:
                    parsed_timestamp = convert_timezone(
                        dt=parsed_timestamp,
                        tz_from=timestamp_input_timezone,
                        tz_to=timestamp_output_timezone,
                    )
                # If they don't want to convert, then we simply localize (i.e. add timezone info
                # without changing the time)
                else:
                    if timestamp_input_timezone:
                        parsed_timestamp = timezone(timestamp_input_timezone).localize(
                            parsed_timestamp
                        )
                    else:
                        parsed_timestamp = timezone("UTC").localize(parsed_timestamp)

            else:
                logger.info(
                    "Timestamp {} already has timezone data; skipping further translation".format(
                        parsed_timestamp
                    )
                )

            if (
                parsing_info.get("fix_wraparound", False) is True
                and previous_line_date
                and parsed_timestamp < previous_line_date
            ):
                old_parsed_timestamp = parsed_timestamp
                parsed_timestamp += relativedelta(days=1)
                logger.warning(
                    f"Wrap-around detected! Advanced {old_parsed_timestamp} "
                    f"1 day to {parsed_timestamp}"
                )
            kwargs_for_format["timestamp"] = parsed_timestamp.strftime(
                self.timestamp_output_format
            )

        kwargs_for_format["name"] = parsing_info["name"]
        reformatted = self.line_output_format.format(**kwargs_for_format)
        # if self.strip_lines:
        #     reformatted = reformatted.strip()
        return (parsed_timestamp, reformatted)

    def process_log_line_no_parse_timestamp(
        self, line, path_meta_keywords, prev_timestamp_str
    ):
        # Split into two funcs
        amended_line, timestamp_str = self.amend_prefix_no_parse_timestamp(
            line, meta=path_meta_keywords, prev_timestamp=prev_timestamp_str,
        )

        return amended_line, timestamp_str

    def process_log_line_parse_timestamp(
        self, line, filename_date, previous_line_date, path_meta_keywords
    ):
        previous_line_date, amended_line = self.amend_prefix_parse_timestamp(
            line,
            filename_date=filename_date,
            meta=path_meta_keywords,
            previous_line_date=previous_line_date,
        )

        return amended_line, previous_line_date

    def process_log_file(self, log_path, log_lines, progress=None):
        processed_lines = []
        # Call all meta handlers and map returned values to keywords
        # These will be used downstream to populate the line_output_format
        # Note that this might be empty -- it depends on whether meta
        # keywords have been specified in line_output_format
        path_meta_keywords = {
            key: handler(log_path) for key, handler in self.meta_handlers.items()
        }
        parsing_info = match_first(
            log_path, self.log_parsing_info, "filename_date_regex"
        )
        if parsing_info:
            filename_date_regex = parsing_info["filename_date_regex"]
            try:
                filename_date_format = parsing_info["filename_date_format"]
            except KeyError:
                raise ValueError(
                    "If filename_date_regex is given, filename_date_format must also be given in config!"
                )
            match = re.match(filename_date_regex, log_path)
            if match:
                filename_date_str = match.groupdict()["date"]
            else:
                raise ValueError(
                    f"Failed to parse file path {log_path!r} with regex {filename_date_regex}"
                )
            filename_date = datetime.strptime(filename_date_str, filename_date_format)
            logger.debug(f"Parsed date {filename_date} from path {log_path}")
        else:
            filename_date = None

        previous_line_date = None
        previous_timestamp_str = None
        # Amend all lines
        for line_number, line in enumerate(log_lines):
            if self.strip_lines:
                line = line.strip()

            if not line:
                continue

            try:
                if self.timestamp_output_format:
                    processed_line, timestamp = self.process_log_line_parse_timestamp(
                        line=line,
                        filename_date=filename_date,
                        previous_line_date=previous_line_date,
                        path_meta_keywords=path_meta_keywords,
                    )
                    previous_line_date = timestamp
                    processed_lines.append((timestamp, processed_line))
                else:
                    (
                        processed_line,
                        timestamp_str,
                    ) = self.process_log_line_no_parse_timestamp(
                        line=line,
                        path_meta_keywords=path_meta_keywords,
                        prev_timestamp_str=previous_timestamp_str,
                    )
                    processed_lines.append(processed_line)
                    previous_timestamp_str = timestamp_str
            except dp._parser.ParserError as error:
                tqdm.write(f"{error}")
            except ValueError:
                if self.bad_line_behavior == "keep":
                    processed_line = line
                elif self.bad_line_behavior == "error":
                    logger.error(f"Invalid line: {line}")
                    raise
                elif self.bad_line_behavior == "warn":
                    logger.warning("No match found; skipped: %r", line)
                elif self.bad_line_behavior == "discard":
                    # Discard
                    pass
                else:
                    raise AssertionError(
                        f"Invalid bad_line_behavior {self.bad_line_behavior}; "
                        "this shouldn't be possible"
                    )

            # line_number is only used to enforce the update_interval
            if progress and line_number % 100 == 0:
                progress.update(100)

        return processed_lines

    def process_path_map(self, path_map, progress=None):
        """Process lines in path_map based on other keys"""
        # TODO: VERY BROKEN
        # filename_date_format = self.log_parsing_info[-1]["filename_date_format"]
        all_processed_lines = []
        for log_path, log_lines in path_map.items():
            processed_lines = self.process_log_file(
                log_path, log_lines, progress=progress,
            )
            all_processed_lines.extend(processed_lines)

        return all_processed_lines

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
                logger.warning("Could not read file %s", log_path)
            except UnicodeDecodeError:
                # TODO: Allow this to be specified in config somehow
                try:
                    with open(log_path, encoding="LATIN1") as log_file:
                        path_map[log_path] = log_file.readlines()
                except IOError:
                    logger.warning("Could not read file %s", log_path)

        # Determine sum of total lines in all log files
        total_lines = sum([len(lines) for lines in path_map.values()])
        # Bail if there are no lines to process
        if not total_lines:
            logger.warning("No lines to process!")
            return []

        if "tqdm" in sys.modules and show_progress:
            # Show progress bars if possible and requested...
            with tqdm(total=total_lines, unit="lines") as progress:
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
