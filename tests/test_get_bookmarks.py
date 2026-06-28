"""Tests for `get_bookmarks`.

`get_bookmarks` is the most branching public function: it routes between
`/v1/posts/recent` and `/v1/posts/get`, validates `dt` format and `count`
bounds, and dispatches `tag` as either single-string or `+`-joined list.

These tests cover the routing and validation branches. The HTTP layer
itself is exercised by the etiquette tests in `test_smoke.py`.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from linkhut_lib import get_bookmarks
from linkhut_lib.config import LinkHutEndpoint
from linkhut_lib.exceptions import (
    BookmarkNotFoundError,
    InvalidDateFormatError,
    RequestError,
)
from tests._helpers import done_responder, last_action, last_payload, patch_api_call

# Documented bounds for /v1/posts/recent (per docs.linkhut.org/posts.html).
_RECENT_COUNT_MAX: int = 100
_RECENT_COUNT_MIN: int = 1

# Fake status code for the request-error propagation test.
_FAKE_STATUS_CODE: int = 500


class TestGetBookmarksRecent:
    """Branches that hit `/v1/posts/recent`."""

    def test_default_no_args_uses_recent_with_15(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No args → recent endpoint with `count=15`."""
        responder = done_responder(
            {'result_code': 'done', 'posts': [{'href': 'https://x'}]}
        )
        patch_api_call(monkeypatch, responder)

        get_bookmarks()

        assert last_action(responder) == LinkHutEndpoint.BOOKMARK_RECENT
        assert last_payload(responder) == {'count': '15'}

    def test_count_with_single_tag_uses_recent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`count > 0` + tag → recent endpoint with single tag."""
        responder = done_responder(
            {'result_code': 'done', 'posts': [{'href': 'https://x'}]}
        )
        patch_api_call(monkeypatch, responder)
        get_bookmarks(count=5, tag='python')

        assert last_action(responder) == LinkHutEndpoint.BOOKMARK_RECENT
        assert last_payload(responder) == {'count': '5', 'tag': 'python'}

    def test_count_with_single_element_list_unwraps(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`count > 0` + `[tag]` (1 element) → unwraps to single string."""
        responder = done_responder(
            {'result_code': 'done', 'posts': [{'href': 'https://x'}]}
        )
        patch_api_call(monkeypatch, responder)
        get_bookmarks(count=5, tag=['python'])

        assert last_payload(responder)['tag'] == 'python'

    def test_count_with_multi_element_list_raises_value_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`count > 0` + multi-tag list → `ValueError` (single-tag only)."""
        responder = Mock()
        patch_api_call(monkeypatch, responder)

        with pytest.raises(ValueError, match='single tag'):
            get_bookmarks(count=5, tag=['python', 'rust'])

        assert not responder.called

    def test_count_above_maximum_raises_value_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`count > 100` → `ValueError` before any HTTP call."""
        responder = Mock()
        patch_api_call(monkeypatch, responder)

        with pytest.raises(ValueError, match='between 1 and 100'):
            get_bookmarks(count=_RECENT_COUNT_MAX + 1)

        assert not responder.called

    def test_count_negative_raises_value_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`count = -1` → `ValueError` before any HTTP call.

        Using -1 (rather than 0) avoids the falsy-coercion branch in
        `get_bookmarks`: `count=0` falls into the `/get` path with no
        filters, while any negative `count > 0` test requires a
        truthy coercion that doesn't exist.
        """
        responder = Mock()
        patch_api_call(monkeypatch, responder)

        with pytest.raises(ValueError, match='between 1 and 100'):
            get_bookmarks(count=-1)

        assert not responder.called

    def test_count_at_maximum_is_allowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`count = 100` (the documented max) is allowed."""
        responder = done_responder(
            {'result_code': 'done', 'posts': [{'href': 'https://x'}]}
        )
        patch_api_call(monkeypatch, responder)
        get_bookmarks(count=_RECENT_COUNT_MAX)

        assert last_payload(responder)['count'] == str(_RECENT_COUNT_MAX)

    def test_count_at_minimum_is_allowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`count = 1` (the documented min) is allowed."""
        responder = done_responder(
            {'result_code': 'done', 'posts': [{'href': 'https://x'}]}
        )
        patch_api_call(monkeypatch, responder)
        get_bookmarks(count=_RECENT_COUNT_MIN)

        assert last_payload(responder)['count'] == str(_RECENT_COUNT_MIN)

    def test_comma_separated_tag_string_takes_first(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`tag='python,rust'` on recent → only the first tag is used."""
        responder = done_responder(
            {'result_code': 'done', 'posts': [{'href': 'https://x'}]}
        )
        patch_api_call(monkeypatch, responder)
        get_bookmarks(count=5, tag='python,rust')

        assert last_payload(responder)['tag'] == 'python'


class TestGetBookmarksGet:
    """Branches that hit `/v1/posts/get`."""

    def test_tag_only_uses_get_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`tag` without `count` → /get with `tag=python`."""
        responder = done_responder(
            {'result_code': 'done', 'posts': [{'href': 'https://x'}]}
        )
        patch_api_call(monkeypatch, responder)
        get_bookmarks(tag='python')

        assert last_action(responder) == LinkHutEndpoint.BOOKMARK_GET
        assert last_payload(responder)['tag'] == 'python'

    def test_tag_list_is_joined_with_plus(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`tag=['python', 'rust']` on /get → joined with `+` (AND-filter)."""
        responder = done_responder(
            {'result_code': 'done', 'posts': [{'href': 'https://x'}]}
        )
        patch_api_call(monkeypatch, responder)
        get_bookmarks(tag=['python', 'rust'])

        assert last_payload(responder)['tag'] == 'python+rust'

    def test_date_with_strict_format_is_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`date='2025-01-01T00:00:00Z'` is the documented wire format."""
        responder = done_responder(
            {'result_code': 'done', 'posts': [{'href': 'https://x'}]}
        )
        patch_api_call(monkeypatch, responder)
        get_bookmarks(date='2025-01-01T00:00:00Z')

        assert last_payload(responder)['dt'] == '2025-01-01T00:00:00Z'

    def test_date_without_z_suffix_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing Z suffix → `InvalidDateFormatError` before any HTTP call."""
        responder = Mock()
        patch_api_call(monkeypatch, responder)

        with pytest.raises(InvalidDateFormatError):
            get_bookmarks(date='2025-01-01T00:00:00')

        assert not responder.called

    def test_date_without_time_component_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`date='2025-01-01'` → `InvalidDateFormatError` (missing time)."""
        responder = Mock()
        patch_api_call(monkeypatch, responder)

        with pytest.raises(InvalidDateFormatError):
            get_bookmarks(date='2025-01-01')

        assert not responder.called

    def test_url_filter_uses_url_field(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`url='...'` is passed through unchanged."""
        responder = done_responder(
            {'result_code': 'done', 'posts': [{'href': 'https://x'}]}
        )
        patch_api_call(monkeypatch, responder)
        get_bookmarks(url='https://example.com/article')

        assert last_payload(responder)['url'] == 'https://example.com/article'

    def test_url_without_scheme_is_passed_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """URLs without `http://` are NOT modified (etiquette rule 4)."""
        responder = done_responder(
            {'result_code': 'done', 'posts': [{'href': 'https://x'}]}
        )
        patch_api_call(monkeypatch, responder)
        get_bookmarks(url='example.com/article')

        assert last_payload(responder)['url'] == 'example.com/article'


class TestGetBookmarksResultHandling:
    """Empty-result and result-code dispatch."""

    def test_empty_posts_raises_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`posts: []` → `BookmarkNotFoundError`."""
        patch_api_call(
            monkeypatch, done_responder({'result_code': 'done', 'posts': []})
        )

        with pytest.raises(BookmarkNotFoundError):
            get_bookmarks(tag='python')

    def test_something_went_wrong_raises_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`result_code: 'something went wrong'` → `BookmarkNotFoundError`."""
        patch_api_call(
            monkeypatch,
            done_responder({'result_code': 'something went wrong'}),
        )

        with pytest.raises(BookmarkNotFoundError):
            get_bookmarks(url='https://example.com/missing')

    def test_returned_list_contains_posts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-empty `posts` is returned as a list of dicts."""
        sample_posts = [
            {'href': 'https://a.example', 'description': 'A'},
            {'href': 'https://b.example', 'description': 'B'},
        ]
        patch_api_call(
            monkeypatch,
            done_responder({'result_code': 'done', 'posts': sample_posts}),
        )

        result = get_bookmarks(count=5)

        assert result == sample_posts

    def test_request_error_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`RequestError` from the API layer bubbles up."""
        patch_api_call(
            monkeypatch,
            Mock(side_effect=RequestError('boom', status_code=_FAKE_STATUS_CODE)),
        )

        with pytest.raises(RequestError):
            get_bookmarks(tag='python')

    def test_non_dict_body_raises_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A list-shaped response body → no `posts` key → empty list → not found."""
        patch_api_call(monkeypatch, done_responder([{'result_code': 'done'}]))

        with pytest.raises(BookmarkNotFoundError):
            get_bookmarks(tag='python')
