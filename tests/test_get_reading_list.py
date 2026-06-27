"""Tests for `get_reading_list`."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from linkhut_lib import get_reading_list
from linkhut_lib.config import LinkHutEndpoint
from linkhut_lib.exceptions import BookmarkNotFoundError
from tests._helpers import done_responder, last_action, last_payload, patch_api_call


class TestGetReadingList:
    """`get_reading_list` is a thin wrapper around `get_bookmarks(tag='unread')`."""

    def test_happy_path_returns_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-empty `posts` → returned as a list of dicts."""
        sample = [
            {'href': 'https://a.example', 'description': 'A'},
            {'href': 'https://b.example', 'description': 'B'},
        ]
        patch_api_call(
            monkeypatch,
            done_responder({'result_code': 'done', 'posts': sample}),
        )

        result = get_reading_list(count=10)

        assert result == sample

    def test_uses_unread_tag_on_recent_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify it routes to /recent with `tag=unread` and the given count."""
        responder = done_responder(
            {'result_code': 'done', 'posts': [{'href': 'https://x'}]}
        )
        patch_api_call(monkeypatch, responder)
        get_reading_list(count=3)

        assert last_action(responder) == LinkHutEndpoint.BOOKMARK_RECENT
        assert last_payload(responder) == {'count': '3', 'tag': 'unread'}

    def test_default_count_is_5(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default count is 5 per the documented signature."""
        responder = done_responder(
            {'result_code': 'done', 'posts': [{'href': 'https://x'}]}
        )
        patch_api_call(monkeypatch, responder)
        get_reading_list()

        assert last_payload(responder) == {'count': '5', 'tag': 'unread'}

    def test_empty_reading_list_raises_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty `posts` → `BookmarkNotFoundError` (re-raised with context)."""
        patch_api_call(
            monkeypatch, done_responder({'result_code': 'done', 'posts': []})
        )

        with pytest.raises(BookmarkNotFoundError):
            get_reading_list(count=5)

    def test_something_went_wrong_raises_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`result_code: 'something went wrong'` → `BookmarkNotFoundError`."""
        patch_api_call(
            monkeypatch,
            done_responder({'result_code': 'something went wrong'}),
        )

        with pytest.raises(BookmarkNotFoundError):
            get_reading_list(count=5)

    def test_count_out_of_bounds_raises_value_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`count > 100` propagates the ValueError from `get_bookmarks`."""
        responder = Mock()
        patch_api_call(monkeypatch, responder)

        with pytest.raises(ValueError, match='between 1 and 100'):
            get_reading_list(count=200)

        assert not responder.called
