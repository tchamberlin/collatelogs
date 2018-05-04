# -*- coding: utf-8 -*-

"""General utilites"""

from __future__ import absolute_import, print_function, unicode_literals

import os
import pwd
import re

import yaml


def read_config(config_path):
    """Given path to yaml file, return its contents as a dict"""

    with open(config_path) as yaml_file:
        return yaml.load(yaml_file)


def match_first(string, regexes):
    """Match string against each regex. Return first match, or None"""

    for regex in regexes:
        m = re.match(regex, string)
        if m:
            return m.groupdict()

    return None


def get_user_from_path(path):
    """Get the username of the owner of the given file"""

    return pwd.getpwuid(os.stat(path).st_uid).pw_name


def compile_regexes(regexes):
    """Compile all regexes and return them as a list"""

    return [re.compile(regex) for regex in regexes]
