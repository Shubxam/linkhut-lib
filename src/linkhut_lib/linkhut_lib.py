"""LinkHut Library — Core functions for interacting with LinkHut API.

This module provides functions for managing bookmarks and tags through the LinkHut API,
including creating, updating, listing and deleting bookmarks, as well as managing tags.

API correctness notes (linkhut-lib 0.1.0):

  - `update_bookmark` is now STRICT: it raises `BookmarkNotFoundError` when
    the URL is not already bookmarked. The previous implicit create-on-update
    behavior has moved to a new `upsert_bookmark` function.

  - `create_bookmark`, `update_bookmark`, and `upsert_bookmark` all return
    a typed `BookmarkCreateResult` / `BookmarkUpdateResult` carrying an
    outcome discriminator, the URL, and the server-shape bookmark dict.

  - `get_bookmarks` now accepts `tag: str | list[str]`. For `count > 0`
    (recent endpoint), only a single tag is allowed and a multi-element
    list raises `ValueError`. For `count == 0` (get endpoint), a list is
    joined with `+` to AND-filter.

  - `get_bookmarks` enforces the documented `dt` format
    (`CCYY-MM-DDThh:mm:ssZ`) and `count` bounds (1..100) on the recent
    endpoint. See https://docs.linkhut.org/posts.html for the wire format.
"""

import json
from typing import Any

from loguru import logger
from pydantic import ValidationError

from . import utils
from .config import LinkHutEndpoint
from .exceptions import (
    BookmarkExistsError,
    BookmarkNotFoundError,
    InvalidURLError,
    RequestError,
)
from .models import (
    APIResponse,
    BookmarkCreateResult,
    BookmarkUpdateResult,
    CreateOutcome,
    Tag,
    UpdateOutcome,
    validate_url_string,
)
from .validation import validate_dt_strict

# `/v1/posts/recent` allows at most 100 results per
# https://docs.linkhut.org/posts.html.
_RECENT_COUNT_MAX: int = 100
_RECENT_COUNT_MIN: int = 1


def _result_code(response: APIResponse) -> str:
    """Pull a result_code string out of an APIResponse, regardless of dict/list body."""
    body: Any = response.content_json
    if isinstance(body, dict):
        return str(body.get('result_code', ''))
    return ''


def get_bookmarks(
    tag: str | list[str] = '',
    date: str = '',
    url: str = '',
    count: int = 0,
) -> list[dict[str, str]]:
    """Get bookmarks from LinkHut. Supports filtering or fetching by recent count.

    - If 'count' is provided, fetches the most recent 'count' bookmarks,
      optionally filtered by a single tag. Uses /v1/posts/recent.
    - If 'date', 'url', or 'tag' (without 'count') are provided, fetches
      bookmarks matching the criteria. Uses /v1/posts/get.
    - If no arguments are provided, fetches the 15 most recent bookmarks.

    Args:
        tag (str | list[str]): Filter by tag(s). For /recent (count > 0),
            only a single tag is allowed; pass either a string or a
            single-element list. Multi-element lists raise `ValueError`.
            For /get (count == 0), a list of tags is joined with `+` to
            AND-filter (per https://docs.linkhut.org/posts.html).
        date (str): Filter by date in `CCYY-MM-DDThh:mm:ssZ` format
            (literal T separator, Z suffix). Required by /v1/posts/get.
        url (str): Filter by exact URL (for /v1/posts/get).
        count (int): Number of recent bookmarks to fetch (for /v1/posts/recent).
            Clamped to 1..100 per the documented bounds.

    Returns:
        list[dict]: list of dictionaries containing bookmark metadata.

    Raises:
        ValueError: If `count` is out of bounds or `tag` has the wrong
            shape for the chosen endpoint.
        InvalidDateFormatError: If `date` is not in `CCYY-MM-DDThh:mm:ssZ`.
        BookmarkNotFoundError: If no bookmarks found for the given criteria.
        RequestError: If API request fails.
    """
    fields: dict[str, str] = {}
    action: LinkHutEndpoint

    # Determine action based on provided parameters
    if count:
        if not _RECENT_COUNT_MIN <= count <= _RECENT_COUNT_MAX:
            raise ValueError(
                f'count must be between {_RECENT_COUNT_MIN} and '
                f'{_RECENT_COUNT_MAX} (got {count}).'
            )
        action = LinkHutEndpoint.BOOKMARK_RECENT
        fields['count'] = str(count)
        if tag:
            # /v1/posts/recent accepts a single tag only.
            if isinstance(tag, list):
                if len(tag) != 1:
                    raise ValueError(
                        '/v1/posts/recent accepts only a single tag; '
                        'pass tag="foo" or tag=["foo"]. For multi-tag '
                        'filtering, use count=0 with the /v1/posts/get '
                        'endpoint.'
                    )
                tag = tag[0]
            # Preserve the historical "first comma/space separated token"
            # behavior so callers passing 'python,rust' still get 'python'.
            fields['tag'] = tag.replace(',', ' ').split()[0]
            logger.debug(f'Using single tag for /recent endpoint: {fields["tag"]}')
    elif tag or date or url:
        action = LinkHutEndpoint.BOOKMARK_GET
        if tag:
            # /v1/posts/get expects tags=tag1+tag2... — join with '+' whether
            # the caller passed a string or a list.
            tag_str: str = '+'.join(tag) if isinstance(tag, list) else tag
            fields['tag'] = tag_str.replace(' ', '+').replace(',', '+')
        if date:
            # /v1/posts/get requires CCYY-MM-DDThh:mm:ssZ with literal T and Z.
            validate_dt_strict(date)  # raises InvalidDateFormatError on bad input
            fields['dt'] = date
        if url:
            # No need to validate URL format here: if a user has imported a
            # bookmark file, not all URLs will have http:// or https://.
            # Pass the URL through unchanged — LinkHut API etiquette says
            # we must not modify URLs without explicit user direction.
            fields['url'] = url
    else:
        # Default behavior: get the 15 most recent posts.
        action = LinkHutEndpoint.BOOKMARK_RECENT
        fields['count'] = '15'

    response: APIResponse = utils.linkhut_api_call(action=action, payload=fields)
    body: Any = response.content_json
    fetched_bookmarks: list[dict[str, str]] = (
        list(body.get('posts', [])) if isinstance(body, dict) else []
    )

    if fetched_bookmarks:
        logger.debug('Bookmarks fetched successfully')
        return fetched_bookmarks

    # A "something went wrong" result_code on /get means the caller passed
    # a URL the server could not match — treat that as a not-found.
    # In every other empty-result case, treat the same way: nothing to
    # return, nothing to disambiguate.
    logger.warning(
        f'No bookmarks found for the given criteria '
        f'(result_code={_result_code(response)!r})'
    )
    raise BookmarkNotFoundError('No bookmarks found for the given criteria')


def create_bookmark(
    url: str,
    title: str = '',
    note: str = '',
    tags: str = '',  # could be of form: "tag1,tag2" or "tag1 tag2" or "tag1 tag2,tag3"
    fetch_tags: bool = True,
    private: bool = False,
    to_read: bool = False,
    replace: bool = False,
) -> BookmarkCreateResult:
    """Create a new bookmark in LinkHut.

    This function creates a new bookmark with the specified URL and optional metadata.
    If title is not provided, it will attempt to fetch the title automatically from the URL.
    If tags are not provided and fetch_tags is True, it will attempt to suggest tags based on the URL content.

    Args:
        url (str): The URL to bookmark
        title (str): Title for the bookmark. If None, fetches automatically.
        note (str): Extended notes or description for the bookmark
        tags (str): Comma-separated list of tags to apply to the bookmark
        fetch_tags (bool): Whether to auto-suggest tags if none provided (default: True)
        private (bool): Whether the bookmark should be private (default: False)
        to_read (bool): Whether to mark the bookmark as "to read" (default: False)
        replace (bool): Whether to replace an existing bookmark with the same URL (default: False)

    Returns:
        BookmarkCreateResult: Typed result carrying `outcome`, `url`, and
            the server-shape `bookmark` dict.

    Raises:
        InvalidURLError: If URL format is invalid.
        BookmarkExistsError: If bookmark already exists and replace=False.
        RequestError: If API request fails.
    """
    # URL validation: Pydantic's HttpUrl does the actual check; we translate
    # ValidationError to the library's own error type. Validation does not
    # modify the URL — LinkHut etiquette forbids silent URL rewriting.
    try:
        validate_url_string(url)
    except ValidationError as exc:
        raise InvalidURLError(f'Invalid URL: {url}') from exc

    # If title not provided, try to fetch it from the destination page.
    if not title:
        title, _desc = utils.get_link_meta(url)

    # Build the tag list. The previous implementation used `tags.isalnum()` as
    # a stand-in for "is this a normal tag string?" which rejected any string
    # containing spaces. We use the explicit empty/whitespace check instead.
    final_tags: list[Tag] = []
    if tags.strip():
        final_tags.extend(
            Tag(name=t) for t in tags.replace(',', ' ').replace(';', ' ').split()
        )
    elif fetch_tags:
        final_tags.extend(utils.get_tags_suggestion(url))

    # Prepare API payload
    fields: dict[str, str] = {
        'url': url,
        'description': title,
        'tags': utils.tags_in_api_format(final_tags),
        'replace': 'yes' if replace else 'no',
        'toread': 'yes' if to_read else 'no',
        'shared': 'no' if private else 'yes',
    }
    if note:
        fields['extended'] = note

    response: APIResponse = utils.linkhut_api_call(
        action=LinkHutEndpoint.BOOKMARK_CREATE, payload=fields
    )
    if _result_code(response) == 'done':
        # `replace=yes` is the only way the server can come back with
        # `result_code: done` for an existing URL. `replace=no` plus an
        # existing URL surfaces as `BookmarkExistsError` below.
        outcome: CreateOutcome = (
            CreateOutcome.REPLACED if replace else CreateOutcome.CREATED
        )
        logger.debug(f'Bookmark {outcome}: {fields}')
        return BookmarkCreateResult(outcome=outcome, url=url, bookmark=fields)
    logger.warning(f'Failed to create bookmark: {response.content_json}')
    raise BookmarkExistsError('Bookmark already exists or creation failed')


def _update_existing_bookmark(
    url: str,
    fetched_bookmark: dict[str, str],
    new_tag: str,
    new_note: str,
    new_private: bool | None,
    new_to_read: bool | None,
    replace: bool,
) -> BookmarkUpdateResult | None:
    """Apply update logic to a fetched bookmark. Returns None if no-op."""
    fields_to_inherit: set[str] = {
        'description',
        'tags',
        'extended',
        'shared',
        'toread',
    }
    if not fields_to_inherit.issubset(fetched_bookmark.keys()):
        logger.debug('Unexpected bookmark format received. Missing required fields.')
        raise RequestError(
            'Unexpected bookmark format received. Missing required fields.'
        )

    # get existing bookmark meta
    title: str = fetched_bookmark.get('description', url)
    tags: str = fetched_bookmark.get('tags', '')
    note: str = fetched_bookmark.get('extended', '')
    current_toread: bool = fetched_bookmark.get('toread') == 'yes'
    current_private: bool = fetched_bookmark.get('shared') == 'no'

    # Determine privacy setting
    private: bool = new_private if new_private is not None else current_private

    # Determine to_read setting
    final_toread: bool = new_to_read if new_to_read is not None else current_toread

    # Check if no actual changes are needed
    if (
        new_to_read is not None
        and current_toread == new_to_read
        and new_private is not None
        and current_private == new_private
        and not new_tag
        and not new_note
    ):
        logger.info(
            f'Bookmark with URL {url} already has the desired status. Nothing to do.'
        )
        return None

    logger.info(f'Bookmark with URL {url} already exists. Updating it.')

    # Refactored tag and note concatenation for clarity
    if replace:
        updated_tags: str = new_tag
        updated_note: str = new_note
    else:
        updated_tags = f'{tags} {new_tag}'.strip() if new_tag else tags
        updated_note = f'{note} {new_note}'.strip() if new_note else note

    result_bookmark = create_bookmark(
        url=url,
        title=title,
        tags=updated_tags,
        note=updated_note,
        private=private,
        replace=True,
        fetch_tags=False,
        to_read=final_toread,
    )
    return BookmarkUpdateResult(
        outcome=UpdateOutcome.UPDATED,
        url=url,
        bookmark=result_bookmark.bookmark,
    )


def update_bookmark(
    url: str,
    new_tag: str = '',
    new_note: str = '',
    new_private: bool | None = None,
    new_to_read: bool | None = None,
    replace: bool = False,  # whether to replace data or append to existing data
) -> BookmarkUpdateResult:
    """STRICT update: raise `BookmarkNotFoundError` if the URL isn't bookmarked.

    Use `upsert_bookmark` if you want the old create-on-update behavior.

    Args:
        url (str): The URL of the bookmark to update.
        new_tag (str): New tags to set for the bookmark (replaces existing tags if replace=True).
        new_note (str): Note to append to the existing note (or replace if replace=True).
        new_private (str): Whether to set the bookmark as private ("yes") or public ("no").
        new_to_read (bool | None): Whether to mark as to-read (True) or read (False). None means no change.
        replace (bool): Whether to replace existing data or append to it.

    Returns:
        BookmarkUpdateResult: Typed result carrying `outcome` (UPDATED or
            NO_OP), `url`, and the server-shape `bookmark` dict.

    Raises:
        RequestError: If no update parameters provided or API request fails.
        BookmarkNotFoundError: If the URL is not bookmarked.
        InvalidURLError: If URL format is invalid.
    """
    # check if there is nothing to update
    if not new_tag and not new_note and new_private is None and new_to_read is None:
        logger.debug('No updates provided. Nothing to do.')
        raise RequestError('No update parameters provided')

    # Strict: get_bookmarks will raise BookmarkNotFoundError if no match,
    # which we let propagate so callers see the right error type.
    bookmarks = get_bookmarks(url=url)
    fetched_bookmark: dict[str, str] = bookmarks[0]

    updated = _update_existing_bookmark(
        url=url,
        fetched_bookmark=fetched_bookmark,
        new_tag=new_tag,
        new_note=new_note,
        new_private=new_private,
        new_to_read=new_to_read,
        replace=replace,
    )
    if updated is None:
        # No-op path: the server-state already matched what was requested.
        return BookmarkUpdateResult(
            outcome=UpdateOutcome.NO_OP,
            url=url,
            bookmark=fetched_bookmark,
        )
    return updated


def upsert_bookmark(
    url: str,
    new_tag: str = '',
    new_note: str = '',
    new_private: bool | None = None,
    new_to_read: bool | None = None,
    replace: bool = False,
) -> BookmarkUpdateResult:
    """Create-on-update: create the bookmark if it doesn't exist, else update it.

    This is the pre-`linkhut-lib 0.1.0` behavior of `update_bookmark`,
    extracted so the strict path is the default and the implicit create
    is opt-in.

    Args:
        url (str): The URL of the bookmark to upsert.
        new_tag (str): New tags to set for the bookmark (replaces existing tags if replace=True).
        new_note (str): Note to append to the existing note (or replace if replace=True).
        new_private (bool | None): Whether to set the bookmark as private.
        new_to_read (bool | None): Whether to mark as to-read.
        replace (bool): Whether to replace existing data or append to it.

    Returns:
        BookmarkUpdateResult: Typed result carrying `outcome` (UPDATED,
            UPSERTED, or NO_OP), `url`, and the server-shape `bookmark`
            dict.

    Raises:
        RequestError: If no update parameters provided or API request fails.
        InvalidURLError: If URL format is invalid.
    """
    if not new_tag and not new_note and new_private is None and new_to_read is None:
        logger.debug('No updates provided. Nothing to do.')
        raise RequestError('No update parameters provided')

    try:
        bookmarks = get_bookmarks(url=url)
    except BookmarkNotFoundError:
        # URL not bookmarked → create path. Mirror the pre-`linkhut-lib
        # 0.1.0` default of public + not-to-read when the caller didn't
        # specify.
        private: bool = new_private if new_private is not None else False
        to_read: bool = new_to_read if new_to_read is not None else False
        result = create_bookmark(
            url=url,
            tags=new_tag,
            note=new_note,
            private=private,
            to_read=to_read,
        )
        return BookmarkUpdateResult(
            outcome=UpdateOutcome.UPSERTED,
            url=url,
            bookmark=result.bookmark,
        )

    fetched_bookmark: dict[str, str] = bookmarks[0]
    updated = _update_existing_bookmark(
        url=url,
        fetched_bookmark=fetched_bookmark,
        new_tag=new_tag,
        new_note=new_note,
        new_private=new_private,
        new_to_read=new_to_read,
        replace=replace,
    )
    if updated is None:
        return BookmarkUpdateResult(
            outcome=UpdateOutcome.NO_OP,
            url=url,
            bookmark=fetched_bookmark,
        )
    return updated


def get_reading_list(count: int = 5) -> list[dict[str, str]]:
    """Fetch and display the user's reading list (bookmarks marked as to-read).

    Args:
        count (int): Number of bookmarks to fetch (default: 5)

    Returns:
        list[dict[str, str]]: List of bookmarks marked as to-read

    Raises:
        BookmarkNotFoundError: If no bookmarks found in the reading list.
        RequestError: If API request fails.
    """
    try:
        reading_list: list[dict[str, str]] = get_bookmarks(tag='unread', count=count)
        logger.debug(
            f'Reading list fetched successfully: {json.dumps(reading_list, indent=2)}'
        )
    except BookmarkNotFoundError:
        logger.info('No bookmarks found in the reading list.')
        raise BookmarkNotFoundError('No bookmarks found in the reading list') from None
    return reading_list


def delete_bookmark(url: str) -> dict[str, str]:
    """Delete a bookmark.

    Args:
        url (str): URL of the bookmark to delete

    Returns:
        dict[str, str]: Success status information

    Raises:
        InvalidURLError: If URL format is invalid.
        BookmarkNotFoundError: If bookmark doesn't exist.
        RequestError: If API request fails.
    """
    try:
        validate_url_string(url)
    except ValidationError as exc:
        raise InvalidURLError(f'Invalid URL: {url}') from exc

    fields: dict[str, str] = {'url': url}
    response: APIResponse = utils.linkhut_api_call(
        action=LinkHutEndpoint.BOOKMARK_DELETE, payload=fields
    )
    result_code: str = _result_code(response)
    if result_code == 'done':
        logger.debug(f'Bookmark with URL {url} successfully deleted.')
        return {'bookmark_deletion': 'success'}
    logger.error(
        f'Unable to delete bookmark with URL {url}. Result code: {result_code}'
    )
    raise BookmarkNotFoundError(
        f'Unable to delete bookmark with URL {url}. Bookmark may not exist.'
    )


def rename_tag(old_tag: str, new_tag: str) -> dict[str, str]:
    """Rename a tag across all bookmarks.

    Args:
        old_tag (str): Current tag name
        new_tag (str): New tag name

    Returns:
        dict[str, str]: Success status information

    Raises:
        InvalidTagFormatError: If tag format is invalid.
        RequestError: If API request fails or tag doesn't exist.
    """
    # Tag construction enforces format: invalid names raise InvalidTagFormatError.
    Tag(name=old_tag)
    Tag(name=new_tag)

    fields: dict[str, str] = {'old': old_tag, 'new': new_tag}
    response: APIResponse = utils.linkhut_api_call(
        action=LinkHutEndpoint.TAG_RENAME, payload=fields
    )
    result_code: str = _result_code(response)
    if result_code == 'done':
        logger.info(f"Tag '{old_tag}' successfully renamed to '{new_tag}'.")
        return {'tag_renaming': 'success'}
    logger.error(
        f"Failed to rename tag '{old_tag}' to '{new_tag}'. Result code: {result_code}"
    )
    raise RequestError(
        f"Failed to rename tag '{old_tag}' to '{new_tag}'. Result code: {result_code}"
    )


def delete_tag(tag: str) -> dict[str, str]:
    """Delete a tag from all bookmarks.

    Args:
        tag (str): Tag to delete

    Returns:
        dict[str, str]: Success status information

    Raises:
        InvalidTagFormatError: If tag format is invalid.
        RequestError: If API request fails or tag doesn't exist.
    """
    # Tag construction enforces format: invalid names raise InvalidTagFormatError.
    Tag(name=tag)

    fields: dict[str, str] = {'tag': tag}
    response: APIResponse = utils.linkhut_api_call(
        action=LinkHutEndpoint.TAG_DELETE, payload=fields
    )
    result_code: str = _result_code(response)
    if result_code == 'done':
        logger.debug(f"Tag '{tag}' successfully deleted.")
        return {'tag_deletion': 'success'}
    logger.error(
        f"Failed to delete tag '{tag}'. Tag doesn't exist. Result code: {result_code}"
    )
    raise RequestError(
        f"Failed to delete tag '{tag}'. Tag may not exist. Result code: {result_code}"
    )
