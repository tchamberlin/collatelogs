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
    else:
        # On Windows
        f = win32security.GetFileSecurity(
            path, win32security.OWNER_SECURITY_INFORMATION)
        (username, domain, sid_name_use) = win32security.LookupAccountSid(
            None, f.GetSecurityDescriptorOwner())
        return username


# All available meta handlers
all_meta_handlers = {
    'owner': get_owner_from_path,
    'filename': os.path.basename
}
