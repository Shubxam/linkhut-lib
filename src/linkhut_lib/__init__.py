# this dunder file is used to mark the directory as a Python package

# this import enables the user to access the LinkHut API functions
# as `from linkhut_lib import create_bookmark`
# against the `from linkhut_lib.linkhut_lib import create_bookmark`

from .exceptions import (
    APIError,
    BookmarkExistsError,
    BookmarkNotFoundError,
    InvalidDateFormatError,
    InvalidTagFormatError,
    InvalidURLError,
    LinkHutError,
)
from .linkhut_lib import (
    create_bookmark,
    delete_bookmark,
    delete_tag,
    get_bookmarks,
    get_reading_list,
    rename_tag,
    update_bookmark,
)

# all the public symbols defined under __all__ will be available when doing `from linkhut_lib import *`
__all__: list[str] = [
    "get_bookmarks",
    "create_bookmark",
    "update_bookmark",
    "get_reading_list",
    "delete_bookmark",
    "rename_tag",
    "delete_tag",
    "LinkHutError",
    "InvalidURLError",
    "BookmarkNotFoundError",
    "InvalidDateFormatError",
    "InvalidTagFormatError",
    "APIError",
    "BookmarkExistsError",
]
