"""Tests for `upsert_bookmark` (create-on-update variant).

Pre-0.2.0, `update_bookmark` had implicit create-on-update behavior. That
behavior now lives in `upsert_bookmark` so the strict path is the default.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from linkhut_lib import upsert_bookmark
from linkhut_lib.exceptions import RequestError
from tests._helpers import (
    StatefulResponder,
    disable_tag_fetch,
    make_api_response,
    patch_api_call,
    patch_link_meta,
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


# Number of API calls expected in upsert's create-then-create and
# get-then-create paths.
EXPECTED_TWO_API_CALLS: int = 2


def _not_found_then_create() -> StatefulResponder:
    """First call returns an empty `posts` list (BookmarkNotFoundError path).

    The second call is `create_bookmark`, which would otherwise try to
    fetch the link metadata. Patch both `get_link_meta` and
    `get_tags_suggestion` so the create call completes deterministically.
    """
    return StatefulResponder(
        [
            make_api_response({'result_code': 'something went wrong', 'posts': []}),
            make_api_response({'result_code': 'done'}),
        ]
    )


def _get_then_create(fetched: dict[str, str]) -> StatefulResponder:
    """First call returns `fetched` (the get), then `done` (create)."""
    return StatefulResponder(
        [
            make_api_response({'result_code': 'done', 'posts': [fetched]}),
            make_api_response({'result_code': 'done'}),
        ]
    )


class TestUpsertBookmark:
    """Coverage for the create-on-update path."""

    VALID_URL: str = 'https://example.com/article'

    def test_no_update_params_raises_request_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All four update fields empty → `RequestError`, no API call made."""
        responder = Mock()
        patch_api_call(monkeypatch, responder)

        with pytest.raises(RequestError):
            upsert_bookmark(url=self.VALID_URL)

        assert not responder.called

    def test_missing_bookmark_creates_via_upsert(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """URL not bookmarked → upsert creates it; outcome is `upserted`."""
        responder = _not_found_then_create()
        patch_api_call(monkeypatch, responder)
        # Avoid real HTTP when create_bookmark auto-fetches the title.
        patch_link_meta(monkeypatch, title='Existing Title')

        result = upsert_bookmark(url=self.VALID_URL, new_tag='python')

        assert result.outcome.value == 'upserted'
        # Two API calls: the failed get, then the create.
        assert len(responder.calls) == EXPECTED_TWO_API_CALLS
        # The create call carries the tags.
        create_call_payload = responder.calls[-1][1]
        assert create_call_payload['url'] == self.VALID_URL
        assert create_call_payload['tags'] == 'python'

    def test_upsert_creates_with_default_public_and_not_to_read(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When creating via upsert without flags → public + not-to-read."""
        responder = _not_found_then_create()
        patch_api_call(monkeypatch, responder)
        patch_link_meta(monkeypatch, title='Existing Title')

        upsert_bookmark(url=self.VALID_URL, new_tag='python')

        create_call_payload = responder.calls[-1][1]
        assert create_call_payload['shared'] == 'yes'
        assert create_call_payload['toread'] == 'no'

    def test_upsert_creates_with_explicit_flags(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`new_private=True` and `new_to_read=True` carry through to create."""
        responder = _not_found_then_create()
        patch_api_call(monkeypatch, responder)
        patch_link_meta(monkeypatch, title='Existing Title')

        upsert_bookmark(
            url=self.VALID_URL,
            new_tag='python',
            new_private=True,
            new_to_read=True,
        )

        create_call_payload = responder.calls[-1][1]
        assert create_call_payload['shared'] == 'no'
        assert create_call_payload['toread'] == 'yes'

    def test_existing_bookmark_updates_with_outcome_updated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Existing bookmark + change → outcome is `updated`."""
        responder = _get_then_create(
            _existing_bookmark(tags='python', private='yes', toread='no')
        )
        patch_api_call(monkeypatch, responder)

        result = upsert_bookmark(
            url=self.VALID_URL,
            new_tag='rust',
            new_private=True,
            new_to_read=True,
        )

        assert result.outcome.value == 'updated'
        assert len(responder.calls) == EXPECTED_TWO_API_CALLS

    def test_existing_bookmark_no_op_returns_no_op(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Existing bookmark with no real change → outcome is `no_op`."""
        responder = _get_then_create(_existing_bookmark(toread='no', private='yes'))
        patch_api_call(monkeypatch, responder)

        result = upsert_bookmark(
            url=self.VALID_URL,
            new_to_read=False,
            new_private=False,
        )

        assert result.outcome.value == 'no_op'
        # No-op path skips the second API call.
        assert len(responder.calls) == 1

    def test_replace_true_overwrites_tags(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`replace=True` → tag is overwritten on the existing bookmark."""
        responder = _get_then_create(_existing_bookmark(tags='python'))
        patch_api_call(monkeypatch, responder)

        upsert_bookmark(url=self.VALID_URL, new_tag='rust', replace=True)

        assert responder.calls[-1][1]['tags'] == 'rust'

    def test_returned_result_carries_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`BookmarkUpdateResult.url` matches the input URL on both paths."""
        # Create path
        responder = _not_found_then_create()
        patch_api_call(monkeypatch, responder)
        patch_link_meta(monkeypatch, title='Existing Title')

        result = upsert_bookmark(url=self.VALID_URL, new_tag='python')
        assert result.url == self.VALID_URL
        assert isinstance(result.bookmark, dict)

        # Update path
        responder = _get_then_create(_existing_bookmark(toread='no', private='yes'))
        patch_api_call(monkeypatch, responder)

        result = upsert_bookmark(
            url=self.VALID_URL,
            new_to_read=False,
            new_private=False,
        )
        assert result.url == self.VALID_URL

    def test_existing_bookmark_skip_link_meta_when_title_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the fetched bookmark has `description`, no link-meta fetch happens."""

        # If link_meta were called for real, the test would hit the network.
        # We assert by patching get_link_meta to raise if called.
        def must_not_call(_url: str) -> tuple[str, str]:
            raise AssertionError('get_link_meta should not be called')

        monkeypatch.setattr(
            'linkhut_lib.linkhut_lib.utils.get_link_meta', must_not_call
        )

        responder = _get_then_create(
            _existing_bookmark(tags='python', private='yes', toread='no')
        )
        patch_api_call(monkeypatch, responder)
        disable_tag_fetch(monkeypatch)

        upsert_bookmark(url=self.VALID_URL, new_tag='rust')

        assert len(responder.calls) == EXPECTED_TWO_API_CALLS
