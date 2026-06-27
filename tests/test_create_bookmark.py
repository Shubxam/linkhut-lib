"""Tests for `create_bookmark`."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from linkhut_lib import create_bookmark
from linkhut_lib.exceptions import BookmarkExistsError, InvalidURLError, RequestError
from linkhut_lib.models import CreateOutcome
from tests._helpers import (
    disable_tag_fetch,
    done_responder,
    last_payload,
    patch_api_call,
    patch_link_meta,
    patch_tags_suggestion,
)


class TestCreateBookmark:
    """Coverage for `create_bookmark`'s branching logic.

    The function does six things worth testing:
      1. Validates the URL (`InvalidURLError` on bad input).
      2. Auto-fetches the title when none is given.
      3. Resolves tags from caller input or from `get_tags_suggestion`.
      4. Sends the right payload (`replace`, `toread`, `shared`, etc.).
      5. Returns `BookmarkCreateResult` with the right `outcome`.
      6. Raises `BookmarkExistsError` when the server says the URL is taken.
    """

    VALID_URL: str = 'https://example.com/article'
    INVALID_URL: str = 'not a url'

    def test_happy_path_with_title(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Title given, no tags → CREATED, payload has `replace=no`."""
        disable_tag_fetch(monkeypatch)
        responder = done_responder()
        patch_api_call(monkeypatch, responder)

        result = create_bookmark(url=self.VALID_URL, title='Example')

        assert result.outcome == CreateOutcome.CREATED
        assert result.url == self.VALID_URL
        sent = last_payload(responder)
        assert sent['url'] == self.VALID_URL
        assert sent['description'] == 'Example'
        assert sent['replace'] == 'no'
        assert sent['toread'] == 'no'
        assert sent['shared'] == 'yes'

    def test_replace_true_returns_replaced_outcome(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`replace=True` with a `done` result code → REPLACED."""
        disable_tag_fetch(monkeypatch)
        patch_api_call(monkeypatch, done_responder())

        result = create_bookmark(url=self.VALID_URL, title='Example', replace=True)

        assert result.outcome == CreateOutcome.REPLACED

    def test_private_and_to_read_flags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`private=True` → `shared=no`; `to_read=True` → `toread=yes`."""
        disable_tag_fetch(monkeypatch)
        responder = done_responder()
        patch_api_call(monkeypatch, responder)

        create_bookmark(
            url=self.VALID_URL,
            title='Example',
            private=True,
            to_read=True,
        )

        sent = last_payload(responder)
        assert sent['shared'] == 'no'
        assert sent['toread'] == 'yes'

    def test_explicit_tags_are_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Tags passed as a string are joined with `+` for the API."""
        disable_tag_fetch(monkeypatch)
        responder = done_responder()
        patch_api_call(monkeypatch, responder)

        create_bookmark(url=self.VALID_URL, title='Example', tags='python, rust')

        assert last_payload(responder)['tags'] == 'python+rust'

    def test_tag_suggestion_used_when_no_tags_and_fetch_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With `tags=''` and `fetch_tags=True`, suggestion list is used."""
        patch_tags_suggestion(monkeypatch, tags=['suggested1', 'suggested2'])
        responder = done_responder()
        patch_api_call(monkeypatch, responder)

        create_bookmark(url=self.VALID_URL, title='Example')

        # Order is `popular` then `recommended`; both end up in the API
        # payload as `+`-joined.
        assert last_payload(responder)['tags'] == 'suggested1+suggested2'

    def test_tag_suggestion_skipped_when_fetch_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`fetch_tags=False` with no caller tags → empty tag string."""

        # Even if we accidentally call get_tags_suggestion, the empty
        # `tags=''` short-circuits the fetch. Patch it to raise so a
        # regression that calls it would surface here.
        def must_not_call(_url: str) -> list:
            raise AssertionError('get_tags_suggestion should not be called')

        monkeypatch.setattr(
            'linkhut_lib.linkhut_lib.utils.get_tags_suggestion', must_not_call
        )
        responder = done_responder()
        patch_api_call(monkeypatch, responder)

        create_bookmark(url=self.VALID_URL, title='Example', fetch_tags=False)

        assert last_payload(responder)['tags'] == ''

    def test_missing_title_triggers_link_meta_fetch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No title → `get_link_meta` is called and its title is used."""
        disable_tag_fetch(monkeypatch)
        patch_link_meta(monkeypatch, title='Fetched From Page', description='')
        responder = done_responder()
        patch_api_call(monkeypatch, responder)

        create_bookmark(url=self.VALID_URL)

        assert last_payload(responder)['description'] == 'Fetched From Page'

    def test_note_is_sent_as_extended(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`note` populates the `extended` field; absence omits it."""
        disable_tag_fetch(monkeypatch)
        responder = done_responder()
        patch_api_call(monkeypatch, responder)

        create_bookmark(url=self.VALID_URL, title='Example', note='a note')

        assert last_payload(responder)['extended'] == 'a note'

    def test_empty_note_omits_extended_field(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`note=''` should NOT add an `extended` key to the payload."""
        disable_tag_fetch(monkeypatch)
        responder = done_responder()
        patch_api_call(monkeypatch, responder)

        create_bookmark(url=self.VALID_URL, title='Example')

        assert 'extended' not in last_payload(responder)

    def test_already_exists_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-`done` result code → `BookmarkExistsError`."""
        disable_tag_fetch(monkeypatch)
        patch_api_call(
            monkeypatch,
            done_responder({'result_code': 'something went wrong'}),
        )

        with pytest.raises(BookmarkExistsError):
            create_bookmark(url=self.VALID_URL, title='Example')

    def test_invalid_url_raises_invalid_url_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Bad URL raises `InvalidURLError` before any API call."""
        # No API call patching needed: validation should reject up front.
        with pytest.raises(InvalidURLError):
            create_bookmark(url=self.INVALID_URL, title='Example')

    def test_request_error_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Network failures from `linkhut_api_call` bubble up as `RequestError`."""
        disable_tag_fetch(monkeypatch)
        patch_api_call(monkeypatch, Mock(side_effect=RequestError('boom')))

        with pytest.raises(RequestError):
            create_bookmark(url=self.VALID_URL, title='Example')

    def test_special_chars_in_tags_are_space_split(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tags separated by `,` or `;` are split on whitespace too."""
        disable_tag_fetch(monkeypatch)
        responder = done_responder()
        patch_api_call(monkeypatch, responder)

        create_bookmark(url=self.VALID_URL, title='Example', tags='a;b, c d')

        # The implementation splits on whitespace after replacing `,` and `;`
        # with spaces.
        assert set(last_payload(responder)['tags'].split('+')) == {
            'a',
            'b',
            'c',
            'd',
        }
