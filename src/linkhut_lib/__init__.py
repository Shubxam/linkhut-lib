"""linkhut-lib — Python client for the LinkHut bookmarking API."""

from importlib.metadata import PackageNotFoundError, version

from .exceptions import (
    BookmarkExistsError,
    BookmarkNotFoundError,
    InvalidDateFormatError,
    InvalidTagFormatError,
    InvalidURLError,
    LinkHutError,
    RequestError,
)
from .linkhut_lib import (
    create_bookmark,
    delete_bookmark,
    delete_tag,
    get_bookmarks,
    get_reading_list,
    rename_tag,
    update_bookmark,
    upsert_bookmark,
)

# Re-export models so users can do `from linkhut_lib import Bookmark, Tag, Date, Url`.
from .models import (
    APIResponse,
    Bookmark,
    BookmarkCreateResult,
    BookmarkUpdateResult,
    CreateOutcome,
    Date,
    HTMLResponse,
    Tag,
    UpdateOutcome,
    Url,
)

try:
    __version__: str = version('linkhut-lib')
except PackageNotFoundError:  # pragma: no cover - editable install fallback
    __version__ = '0.0.0+unknown'

# all the public symbols defined under __all__ will be available when doing `from linkhut_lib import *`
__all__: list[str] = [
    'APIResponse',
    'Bookmark',
    'BookmarkCreateResult',
    'BookmarkExistsError',
    'BookmarkNotFoundError',
    'BookmarkUpdateResult',
    'CreateOutcome',
    'Date',
    'HTMLResponse',
    'InvalidDateFormatError',
    'InvalidTagFormatError',
    'InvalidURLError',
    'LinkHutError',
    'RequestError',
    'Tag',
    'UpdateOutcome',
    'Url',
    'create_bookmark',
    'delete_bookmark',
    'delete_tag',
    'get_bookmarks',
    'get_reading_list',
    'rename_tag',
    'update_bookmark',
    'upsert_bookmark',
]
