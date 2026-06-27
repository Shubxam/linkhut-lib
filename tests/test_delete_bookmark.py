"""Tests for `delete_bookmark`."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from linkhut_lib import delete_bookmark
from linkhut_lib.exceptions import BookmarkNotFoundError, InvalidURLError, RequestError
from tests._helpers import (
    HTTP_SERVICE_UNAVAILABLE,
    done_responder,
    last_payload,
    patch_api_call,
)


class TestDeleteBookmark:
    """Verify the happy path and the three failure modes of `delete_bookmark`."""

    VALID_URL: str = 'https://example.com/article'
    INVALID_URL: str = 'not a url'

    def test_happy_path_returns_success_dict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`result_code: done` → returns `{'bookmark_deletion': 'success'}`."""
        patch_api_call(monkeypatch, done_responder())

        result = delete_bookmark(url=self.VALID_URL)

        assert result == {'bookmark_deletion': 'success'}

    def test_missing_bookmark_raises_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-`done` result code → `BookmarkNotFoundError`."""
        patch_api_call(
            monkeypatch,
            done_responder({'result_code': 'something went wrong'}),
        )

        with pytest.raises(BookmarkNotFoundError):
            delete_bookmark(url=self.VALID_URL)

    def test_invalid_url_raises_invalid_url_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """URL that fails `validate_url_string` raises `InvalidURLError`."""
        # Use a clearly-bad URL. Don't need to patch the API call because the
        # URL validator should reject the input before any HTTP request.
        with pytest.raises(InvalidURLError):
            delete_bookmark(url=self.INVALID_URL)

    def test_request_error_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`RequestError` from the API layer bubbles up unchanged."""
        patch_api_call(
            monkeypatch,
            Mock(
                side_effect=RequestError(
                    'network down', status_code=HTTP_SERVICE_UNAVAILABLE
                )
            ),
        )

        with pytest.raises(RequestError) as exc_info:
            delete_bookmark(url=self.VALID_URL)
        assert exc_info.value.status_code == HTTP_SERVICE_UNAVAILABLE

    def test_payload_contains_only_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify the API call receives `{'url': <input>}` and nothing else."""
        responder = done_responder()
        patch_api_call(monkeypatch, responder)
        delete_bookmark(url=self.VALID_URL)

        assert last_payload(responder) == {'url': self.VALID_URL}
