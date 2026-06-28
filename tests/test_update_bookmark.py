"""Tests for `update_bookmark` (strict variant).

`update_bookmark` raises `BookmarkNotFoundError` when the URL isn't already
bookmarked. The create-on-update behavior lives in `upsert_bookmark` (see
`test_upsert_bookmark.py`).
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from linkhut_lib import update_bookmark
from linkhut_lib.exceptions import (
    BookmarkNotFoundError,
    RequestError,
)
from tests._helpers import (
    StatefulResponder,
    disable_tag_fetch,
    done_responder,
    make_api_response,
    patch_api_call,
)


def _existing_bookmark(
    *,
    url: str = 'https://example.com/article',
    tags: str = 'python',
    note: str = 'existing note',
    private: str = 'yes',
    toread: str = 'no',
) -> dict[str, str]:
    """A server-shape bookmark payload as `get_bookmarks` would return it."""
    return {
        'href': url,
        'description': 'Existing Title',
        'tags': tags,
        'extended': note,
        'shared': private,
        'toread': toread,
    }


def _get_then_create(fetched: dict[str, str]) -> StatefulResponder:
    """Build a responder that returns the get-result, then `done` for the create.

    `update_bookmark` calls `get_bookmarks` (which calls
    `linkhut_api_call`) and then `create_bookmark` (which also calls it)
    in the success path.
    """
    return StatefulResponder(
        [
            make_api_response({'result_code': 'done', 'posts': [fetched]}),
            make_api_response({'result_code': 'done'}),
        ]
    )


class TestUpdateBookmark:
    """Coverage for the strict-update path."""

    VALID_URL: str = 'https://example.com/article'

    def test_no_update_params_raises_request_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All four update fields empty → `RequestError`, no API call made."""
        responder = Mock()
        patch_api_call(monkeypatch, responder)

        with pytest.raises(RequestError):
            update_bookmark(url=self.VALID_URL)

        assert not responder.called

    def test_missing_bookmark_raises_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """URL not bookmarked → `BookmarkNotFoundError` (strict behavior)."""
        patch_api_call(
            monkeypatch,
            done_responder({'result_code': 'something went wrong', 'posts': []}),
        )

        with pytest.raises(BookmarkNotFoundError):
            update_bookmark(url=self.VALID_URL, new_tag='python')

    def test_no_op_returns_no_op_outcome(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Matching `new_to_read=False` and `new_private=False` → NO_OP.

        With both flags passed on a bookmark whose state already matches,
        the function short-circuits to a NO_OP outcome without a second
        API call.
        """
        responder = _get_then_create(
            _existing_bookmark(toread='no', private='yes'),
        )
        patch_api_call(monkeypatch, responder)

        result = update_bookmark(
            url=self.VALID_URL,
            new_to_read=False,
            new_private=False,
        )

        assert result.outcome.value == 'no_op'
        # The no-op path skips the create call.
        assert len(responder.calls) == 1

    def test_tag_update_concatenates_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`replace=False` (default) → new tag joins existing tags with `+`.

        Internally the merge builds a space-separated string, then
        `create_bookmark` re-splits and re-joins with `+` via
        `tags_in_api_format`, so the API payload uses `+` as the separator.
        """
        responder = _get_then_create(_existing_bookmark(tags='python'))
        patch_api_call(monkeypatch, responder)

        update_bookmark(url=self.VALID_URL, new_tag='rust')

        # The second API call (create with replace=yes) carries the merged
        # tags.
        create_call_payload = responder.calls[-1][1]
        assert create_call_payload['tags'] == 'python+rust'

    def test_replace_true_overwrites_tags(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`replace=True` → tag is overwritten, not appended."""
        responder = _get_then_create(_existing_bookmark(tags='python'))
        patch_api_call(monkeypatch, responder)

        update_bookmark(url=self.VALID_URL, new_tag='rust', replace=True)

        assert responder.calls[-1][1]['tags'] == 'rust'

    def test_note_concatenates_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`replace=False` (default) → new note is appended to existing note."""
        responder = _get_then_create(_existing_bookmark(note='existing note'))
        patch_api_call(monkeypatch, responder)

        update_bookmark(url=self.VALID_URL, new_note='new note')

        assert responder.calls[-1][1]['extended'] == 'existing note new note'

    def test_replace_true_overwrites_note(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`replace=True` → note is overwritten, not appended."""
        responder = _get_then_create(_existing_bookmark(note='existing note'))
        patch_api_call(monkeypatch, responder)

        update_bookmark(url=self.VALID_URL, new_note='new note', replace=True)

        assert responder.calls[-1][1]['extended'] == 'new note'

    def test_privacy_change_writes_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`new_private=True` on a public bookmark → `shared=no` on write."""
        responder = _get_then_create(_existing_bookmark(private='yes'))
        patch_api_call(monkeypatch, responder)

        update_bookmark(url=self.VALID_URL, new_private=True)

        assert responder.calls[-1][1]['shared'] == 'no'

    def test_to_read_change_writes_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`new_to_read=True` on `toread=no` bookmark → `toread=yes` on write."""
        responder = _get_then_create(_existing_bookmark(toread='no'))
        patch_api_call(monkeypatch, responder)

        update_bookmark(url=self.VALID_URL, new_to_read=True)

        assert responder.calls[-1][1]['toread'] == 'yes'

    def test_returned_result_carries_url_and_bookmark(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`BookmarkUpdateResult.url` matches the input URL."""
        responder = _get_then_create(_existing_bookmark())
        patch_api_call(monkeypatch, responder)

        result = update_bookmark(url=self.VALID_URL, new_tag='rust')

        assert result.url == self.VALID_URL
        assert isinstance(result.bookmark, dict)
        assert result.outcome.value == 'updated'

    def test_existing_bookmark_missing_required_fields_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A fetched bookmark missing required keys → `RequestError`."""
        # `description` is required by the `fields_to_inherit` set, so
        # dropping it forces the error.
        incomplete = _existing_bookmark()
        incomplete.pop('description')

        responder = done_responder({'result_code': 'done', 'posts': [incomplete]})
        patch_api_call(monkeypatch, responder)
        disable_tag_fetch(monkeypatch)

        with pytest.raises(RequestError):
            update_bookmark(url=self.VALID_URL, new_tag='rust')

    def test_get_then_create_url_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`update_bookmark` calls `get_bookmarks` with `url=...` to find the bookmark."""
        responder = _get_then_create(_existing_bookmark())
        patch_api_call(monkeypatch, responder)
        disable_tag_fetch(monkeypatch)

        update_bookmark(url=self.VALID_URL, new_tag='rust')

        # First call: get_bookmarks with the URL filter.
        first_call_payload = responder.calls[0][1]
        assert first_call_payload['url'] == self.VALID_URL
