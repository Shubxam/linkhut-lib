"""Tests for `delete_tag`."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from linkhut_lib import delete_tag
from linkhut_lib.exceptions import InvalidTagFormatError, RequestError
from tests._helpers import (
    HTTP_SERVICE_UNAVAILABLE,
    done_responder,
    last_payload,
    patch_api_call,
)


class TestDeleteTag:
    """Coverage for the tag-delete happy path and failure modes."""

    def test_happy_path_returns_success_dict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`done` → `{'tag_deletion': 'success'}`."""
        patch_api_call(monkeypatch, done_responder())

        result = delete_tag(tag='python')

        assert result == {'tag_deletion': 'success'}

    def test_payload_contains_tag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify the payload sent to /v1/tags/delete has `tag`."""
        responder = done_responder()
        patch_api_call(monkeypatch, responder)
        delete_tag(tag='python')

        assert last_payload(responder) == {'tag': 'python'}

    def test_invalid_tag_raises_invalid_tag_format(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tag construction rejects bad names before any HTTP call."""
        responder = Mock()
        patch_api_call(monkeypatch, responder)

        with pytest.raises(InvalidTagFormatError):
            delete_tag(tag='has spaces')

        assert not responder.called

    def test_non_done_result_raises_request_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Anything other than `done` → `RequestError`."""
        patch_api_call(
            monkeypatch,
            done_responder({'result_code': 'something went wrong'}),
        )

        with pytest.raises(RequestError, match='delete'):
            delete_tag(tag='nonexistent')

    def test_request_error_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Network failures bubble up as `RequestError`."""
        patch_api_call(
            monkeypatch,
            Mock(
                side_effect=RequestError(
                    'network down', status_code=HTTP_SERVICE_UNAVAILABLE
                )
            ),
        )

        with pytest.raises(RequestError) as exc_info:
            delete_tag(tag='python')
        assert exc_info.value.status_code == HTTP_SERVICE_UNAVAILABLE
