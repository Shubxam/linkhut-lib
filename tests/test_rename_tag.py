"""Tests for `rename_tag`."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from linkhut_lib import rename_tag
from linkhut_lib.exceptions import (
    InvalidTagFormatError,
    RequestError,
)
from tests._helpers import (
    HTTP_SERVICE_UNAVAILABLE,
    done_responder,
    last_payload,
    patch_api_call,
)


class TestRenameTag:
    """Coverage for the tag-rename happy path and failure modes."""

    def test_happy_path_returns_success_dict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`done` → `{'tag_renaming': 'success'}`."""
        patch_api_call(monkeypatch, done_responder())

        result = rename_tag(old_tag='python', new_tag='py')

        assert result == {'tag_renaming': 'success'}

    def test_payload_contains_old_and_new(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the payload sent to /v1/tags/rename has `old` and `new`."""
        responder = done_responder()
        patch_api_call(monkeypatch, responder)
        rename_tag(old_tag='python', new_tag='py')

        assert last_payload(responder) == {'old': 'python', 'new': 'py'}

    def test_invalid_old_tag_raises_invalid_tag_format(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tag construction rejects bad names before any HTTP call."""
        responder = Mock()
        patch_api_call(monkeypatch, responder)

        with pytest.raises(InvalidTagFormatError):
            rename_tag(old_tag='has spaces', new_tag='py')

        assert not responder.called

    def test_invalid_new_tag_raises_invalid_tag_format(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tag construction rejects bad new names too."""
        responder = Mock()
        patch_api_call(monkeypatch, responder)

        with pytest.raises(InvalidTagFormatError):
            rename_tag(old_tag='python', new_tag='has spaces')

        assert not responder.called

    def test_non_done_result_raises_request_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Anything other than `done` → `RequestError`."""
        patch_api_call(
            monkeypatch,
            done_responder({'result_code': 'something went wrong'}),
        )

        with pytest.raises(RequestError, match='rename'):
            rename_tag(old_tag='python', new_tag='py')

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
            rename_tag(old_tag='python', new_tag='py')
        assert exc_info.value.status_code == HTTP_SERVICE_UNAVAILABLE

    def test_alphanumeric_with_hyphens_and_underscores_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tags with `-` and `_` are valid (matches `validate_tag`)."""
        patch_api_call(monkeypatch, done_responder())

        result = rename_tag(old_tag='my-tag_1', new_tag='my-tag_2')

        assert result == {'tag_renaming': 'success'}
