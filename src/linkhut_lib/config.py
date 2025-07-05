"""
Configuration settings for the LinkHut and LinkPreview APIs.

This module contains the base URLs and header templates for making API requests.
The actual API keys are inserted into these templates at runtime.
"""
# TODO: make use of ENUMs and TypeAlias and Dataclasses

from enum import Enum

# from typing import TypeAlias

# LinkHut API configuration
LINKHUT_HEADER: dict[str, str] = {
    "Accept": "application/json",
    "Authorization": "Bearer {PAT}",  # PAT placeholder replaced at runtime
}
LINKHUT_BASEURL: str = "https://api.ln.ht"

# LinkHut API endpoints
LINKHUT_API_ENDPOINTS: dict[str, str] = {
    "bookmark_get": "/v1/posts/get",
    "bookmark_recent": "/v1/posts/recent",
    "bookmark_create": "/v1/posts/add",
    "bookmark_delete": "/v1/posts/delete",
    "tag_suggest": "/v1/posts/suggest",
    "tag_delete": "/v1/tags/delete",
    "tag_rename": "/v1/tags/rename",
}

firefox_user_agent: str = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:139.0) Gecko/20100101 Firefox/139.0"
)


class LH_API_ENDPOINT(Enum):
    """Enum-like class for LinkHut API endpoints."""

    BOOKMARK_GET = "/v1/posts/get"
    BOOKMARK_RECENT = "/v1/posts/recent"
    BOOKMARK_CREATE = "/v1/posts/add"
    BOOKMARK_DELETE = "/v1/posts/delete"
    TAG_SUGGEST = "/v1/posts/suggest"
    TAG_DELETE = "/v1/tags/delete"
    TAG_RENAME = "/v1/tags/rename"


# LinkPreview API configuration
LINKPREVIEW_HEADER: dict[str, str] = {
    "X-Linkpreview-Api-Key": "{API_KEY}"  # API_KEY placeholder replaced at runtime
}
LINKPREVIEW_BASEURL: str = "https://api.linkpreview.net"
