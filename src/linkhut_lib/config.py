"""
Configuration settings for the LinkHut and LinkPreview APIs.

This module contains the base URLs and header templates for making API requests.
The actual API keys are inserted into these templates at runtime.
"""

from enum import Enum

# LinkHut API configuration
LINKHUT_HEADER: dict[str, str] = {
    'Accept': 'application/json',
    'Authorization': 'Bearer {PAT}',  # PAT placeholder replaced at runtime
}
LINKHUT_BASEURL: str = 'https://api.ln.ht'

firefox_user_agent: str = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:139.0) Gecko/20100101 Firefox/139.0'


# TODO(#1): rename to CapWords (e.g. LinkHutEndpoint) when callers are updated.
class LH_API_ENDPOINT(Enum):  # noqa: N801
    """LinkHut API endpoint paths."""

    BOOKMARK_GET = '/v1/posts/get'
    BOOKMARK_RECENT = '/v1/posts/recent'
    BOOKMARK_CREATE = '/v1/posts/add'
    BOOKMARK_DELETE = '/v1/posts/delete'
    TAG_SUGGEST = '/v1/posts/suggest'
    TAG_DELETE = '/v1/tags/delete'
    TAG_RENAME = '/v1/tags/rename'


# LinkPreview API configuration
LINKPREVIEW_HEADER: dict[str, str] = {
    'X-Linkpreview-Api-Key': '{API_KEY}'  # API_KEY placeholder replaced at runtime
}
LINKPREVIEW_BASEURL: str = 'https://api.linkpreview.net'
