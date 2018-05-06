# -*- coding: utf-8 -*-

"""General utilites"""

from __future__ import absolute_import, print_function, unicode_literals

import logging
import os


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

from string import Formatter
import re

import yaml
import sys

logger = logging.getLogger(__name__)

formatter = Formatter()

local_timezone = get_localzone()


def check_that_regexes_are_all_supersets_of_format_string(regexes, meta, format_string):
    return all([check_that_regex_is_superset_of_format_string(regex, meta, format_string) for regex in regexes])


def check_that_regex_is_superset_of_format_string(regex, meta, format_string):
    """Parse regex and format_string; determine all format keywords exist in regex groups"""
    # Determine which keywords exist in the format string
    format_string_keywords = extract_keywords_from_format_string(format_string)
    logger.debug("Got format string keywords: %s", format_string_keywords)
    # Determine which groups exist in the regex
    regex_groups = extract_groups_from_compiled_regex(regex)

    logger.debug("Got regex groups: %s", regex_groups)
    logger.debug("meta keywords: %s", meta)
    # import ipdb; ipdb.set_trace()
    # Determine whether all format keywords exist in the regex as groups
    return set(regex_groups + meta).issuperset(format_string_keywords)


def extract_keywords_from_format_string(format_string):
    """Determine which keywords exist in given format string"""

    return [keyword for _, keyword, _, _ in formatter.parse(format_string)]


def extract_groups_from_compiled_regex(regex):
    """Determine which groups exist in given (compiled!) regex"""

    return regex.groupindex.keys()


def read_config(config_path):
    """Given path to yaml file, return its contents as a dict"""

    with open(config_path) as yaml_file:
        return yaml.load(yaml_file)


def match_first(string, prefix_infos):
    """Match string against each regex. Return first match, or None"""

    for prefix_info in prefix_infos:
        regex = prefix_info['regex']
        m = re.match(regex, string)
        if m:
            prefix_info['match'] = m.groupdict()
            return prefix_info

    return None


def compile_regexes(prefix_parsing_info):
    """Compile all regexes in prefix_parsing_info, in place"""

    for info in prefix_parsing_info:
        info['regex'] = re.compile(info['regex'])


def convert_timezone(dt, tz_orig, tz_dest=None):
    if tz_dest:
        tz_dest = timezone(tz_dest)
    else:
        tz_dest = local_timezone
    return timezone(tz_orig).localize(dt).astimezone(tz_dest)
