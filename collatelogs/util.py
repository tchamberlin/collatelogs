# -*- coding: utf-8 -*-

"""General utilites"""

from __future__ import absolute_import, print_function, unicode_literals

import logging
import re
from string import Formatter

import yaml


logger = logging.getLogger(__name__)
formatter = Formatter()


def check_that_regexes_are_all_supersets_of_format_string(regexes, meta, format_string):
    return all(
        [not get_missing_groups(regex, meta, format_string) for regex in regexes]
    )


def debug_regexes(regexes, meta, format_string):
    return {regex: get_missing_groups(regex, meta, format_string) for regex in regexes}


def debug_regexes_str(regexes, meta, format_string):
    lines = []

    for regex in regexes:
        missing_groups = get_missing_groups(regex, meta, format_string)
        if missing_groups:
            lines.append(
                f"'{regex.pattern}' is missing groups {missing_groups} "
                f"required by output format string '{format_string}'"
            )

    return lines


def get_missing_groups(regex, meta, format_string):
    """Parse regex and format_string; determine all format keywords exist in regex groups"""
    # Determine which keywords exist in the format string
    format_string_keywords = extract_keywords_from_format_string(format_string)
    # logger.debug("Got format string keywords: %s", format_string_keywords)
    # Determine which groups exist in the regex
    regex_groups = extract_groups_from_compiled_regex(regex)

    # logger.debug("Got regex groups: %s", regex_groups)
    # logger.debug("meta keywords: %s", meta)
    # Determine whether all format keywords exist in the regex as groups
    # foo =  set(regex_groups).union(set(meta)).issuperset(format_string_keywords)
    missing = set(format_string_keywords).difference(set(regex_groups).union(set(meta)))
    return missing


def extract_keywords_from_format_string(format_string):
    """Determine which keywords exist in given format string"""

    return [keyword for _, keyword, _, _ in formatter.parse(format_string)]


def extract_groups_from_compiled_regex(regex):
    """Determine which groups exist in given (compiled!) regex"""

    return regex.groupindex.keys()


def read_config(config_path):
    """Given path to yaml file, return its contents as a dict"""

    with open(config_path) as yaml_file:
        return yaml.load(yaml_file, Loader=yaml.Loader)


def match_first(string, prefix_infos, key):
    """Match string against each regex. Return first match, or None"""

    for prefix_info in prefix_infos:
        regex = prefix_info.get(key)
        if regex:
            match = re.match(regex, string)
            if match:
                prefix_info["match"] = match.groupdict()
                return prefix_info

    return None


def compile_regexes(prefix_parsing_info):
    """Compile all regexes in prefix_parsing_info, in place"""

    for info in prefix_parsing_info:
        info["line_regex"] = re.compile(info["line_regex"])


def convert_timezone(dt, tz_from, tz_to):
    """Convert dt from tz_from to tz_to"""

    return tz_from.localize(dt).astimezone(tz_to)
