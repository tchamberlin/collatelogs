# -*- coding: utf-8 -*-

"""File metadata handlers: provide metadata based on a given path

These are used to populated keywords in the line_output_format, elsewhere"""

import os
try:
    # For unix
    import pwd
except ImportError:
    # For windows
    import win32security
import sys


def get_owner_from_path(path):
    """Get the username of the owner of the given file"""

    if 'pwd' in sys.modules:
        # On unix
        return pwd.getpwuid(os.stat(path).st_uid).pw_name

    # On Windows
    f = win32security.GetFileSecurity(
        path, win32security.OWNER_SECURITY_INFORMATION)
    username, _, _ = win32security.LookupAccountSid(None, f.GetSecurityDescriptorOwner())
    return username


# All available meta handlers
all_meta_handlers = {
    'owner': get_owner_from_path,
    'filename': os.path.basename
}
