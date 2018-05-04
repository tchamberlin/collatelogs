# -*- coding: utf-8 -*-

"""Collates a given set of log files"""

from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
import warnings

try:
    import dateutil.parser as dp
except ImportError:
    warnings.warn("dateutil not found; date parsing will not be possible. "
                  "Consider running this in an environment with dateutil installed")
try:
    from tqdm import tqdm
    # Due to TQDM bug? https://github.com/tqdm/tqdm/issues/481
    tqdm.monitor_interval = 0
except ImportError:
    warnings.warn("tqdm not found; progress bars will not function. "
                  "Consider running this in an environment with tqdm installed")

from .util import (
    compile_regexes,
    get_user_from_path,
    match_first,
)


def check_prefix_output_format(prefix_output_format):
    if not prefix_output_format.startswith('{timestamp'):
        raise ValueError("prefix_output_format must start with 'timestamp'")


def amend_prefix(
        line,
        prefix_output_format,
        prefix_regexes,
        date_format=None,
        subsecond_digits=3,
        pad_milliseconds=False,
        **kwargs
):
    """Given a line from a log file, insert its filename and return it"""

    kwargs_from_regex = match_first(line, prefix_regexes)

    if not kwargs_from_regex:
        raise ValueError("Line {!r} did not match against any of the given regexes!"
                         .format(line))

    # Add kwargs
    kwargs.update(kwargs_from_regex)
    timestamp = kwargs['timestamp']

    if date_format:
        timestamp = dp.parse(timestamp).strftime(date_format)
        # Adjust precision of microseconds to given number of digits (that is,
        # chop of the requested number of digits
        if '%f' in date_format:
            timestamp = timestamp[:-1 * (6 - subsecond_digits)]
    elif pad_milliseconds:
        # If millisecond padding has been requested, pad by the given
        # number of digits
        if "," not in timestamp:
            timestamp += ",{}".format("0" * subsecond_digits)

    kwargs['timestamp'] = timestamp

    return prefix_output_format.format(**kwargs)


def format_advanced(
        log_paths,
        prefix_output_format,
        prefix_regexes,
        date_format=None,
        bad_line_behavior='discard',
        allow_duplicates=False,
        subsecond_digits=3,
        pad_milliseconds=False
):
    check_prefix_output_format(prefix_output_format)

    if date_format and 'dateutil' not in sys.modules:
        raise ValueError("You have indicated a date_format which requires "
                         "date parsing, but dateutil is not installed!")

    # Compile all regexes ahead of the loop (for performance)
    prefix_regexes = compile_regexes(prefix_regexes)

    log_lines = []
    bad_lines = []

    lines_to_process = []
    for log_path in log_paths:
        user = get_user_from_path(log_path)
        filename = os.path.basename(log_path)
        try:
            with open(log_path) as log_file:
                for line in log_file.readlines():
                    # TODO: Write non-progress version that does this in-place
                    lines_to_process.append((line, user, filename))
        except IOError:
            print("WARNING: Could not read file {}".format(log_path), file=sys.stderr)
    if not lines_to_process:
        print("WARNING: No lines to process!")
        return []

    # Show progress bars if possible
    if 'tqdm' in sys.modules:
        line_iter = tqdm(lines_to_process, desc="Processing log lines")
    else:
        line_iter = lines_to_process
    for line, user, filename in line_iter:
        try:
            amended_line = amend_prefix(
                line,
                prefix_output_format=prefix_output_format,
                date_format=date_format,
                prefix_regexes=prefix_regexes,
                pad_milliseconds=pad_milliseconds,
                subsecond_digits=subsecond_digits,
                # Below this are included in kwargs
                filename=filename,
                user=user
            )
            log_lines.append(amended_line)
        except ValueError:
            if bad_line_behavior == 'keep':
                bad_lines.append(line)
            elif bad_line_behavior == 'error':
                raise

    # If we are not allowing duplicates, remove duplicates
    if not allow_duplicates:
        log_lines = set(log_lines)

    return sorted(log_lines)


def amend_simple(line, filename, user, timestamp_length):
    """Given a line from a log file, insert its filename and return it"""
    return "{} - {} - {}{}".format(line[:timestamp_length], filename, user, line[timestamp_length:])


def format_simple(
        log_paths,
        timestamp_length,
        allow_duplicates=False,
        no_strip=False,
        bad_line_behavior='discard'
):
    lines_to_process = []
    log_lines = []
    for log_path in log_paths:
        user = get_user_from_path(log_path)
        filename = os.path.basename(log_path)
        try:
            with open(log_path) as log_file:
                # TODO: Write non-progress version that does this in-place
                for line in log_file.readlines():
                    if not no_strip:
                        line = line.strip()
                    lines_to_process.append((line, user, filename))
        except IOError:
            print("WARNING: Could not read file {}".format(log_path), file=sys.stderr)

    if 'tqdm' in sys.modules:
        line_iter = tqdm(lines_to_process, desc="Processing log lines")
    else:
        line_iter = lines_to_process

    for line, user, filename in line_iter:
        if len(line) > timestamp_length and not line[timestamp_length].isdigit():
            amended_line = amend_simple(
                line,
                filename=filename,
                user=user,
                timestamp_length=timestamp_length
            )
            log_lines.append(amended_line)
        else:
            if bad_line_behavior == 'keep':
                log_lines.append(line)
            elif bad_line_behavior == 'error':
                raise ValueError("Bad line: {}".format(line))

    # If we are not allowing duplicates, remove duplicates
    if not allow_duplicates:
        log_lines = set(log_lines)

    return log_lines
