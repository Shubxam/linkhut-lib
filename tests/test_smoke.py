"""Smoke tests for the existing helpers.

These tests exercise pure helpers (no live HTTP) so `pytest` exits 0 on the
last-known-good main. They also serve as a safety net while the typed-API
refactor is being completed on a separate branch.
"""

import pytest

from linkhut_lib.exceptions import InvalidTagFormatError
from linkhut_lib.models import Bookmark, Tag
from linkhut_lib.utils import encode_url, tags_in_api_format
from linkhut_lib.validation import validate_tag


class TestValidateTag:
    def test_accepts_alphanumeric(self) -> None:
        assert validate_tag('python') == 'python'

    def test_accepts_hyphens_and_underscores(self) -> None:
        assert validate_tag('foo-bar_baz') == 'foo-bar_baz'

    def test_rejects_spaces(self) -> None:
        with pytest.raises(InvalidTagFormatError):
            validate_tag('foo bar')

    def test_rejects_empty(self) -> None:
        with pytest.raises(InvalidTagFormatError):
            validate_tag('')


class TestEncodeUrl:
    def test_encodes_common_characters(self) -> None:
        assert (
            encode_url('https://example.com/a?b=c&d=e')
            == 'https%3A%2F%2Fexample.com%2Fa%3Fb%3Dc%26d%3De'
        )

    def test_encodes_backslashes(self) -> None:
        assert encode_url('a\\b') == 'a%5Cb'

    def test_passthrough_when_no_specials(self) -> None:
        assert encode_url('plain') == 'plain'


class TestTagsInApiFormat:
    def test_joins_with_plus(self) -> None:
        assert tags_in_api_format([Tag(name='a'), Tag(name='b')]) == 'a+b'

    def test_empty_list(self) -> None:
        assert tags_in_api_format([]) == ''


class TestBookmarkRoundTrip:
    def test_by_alias_dump(self) -> None:
        payload = {
            'href': 'https://example.com',
            'description': 'Example',
        }
        bookmark = Bookmark.model_validate(payload)
        data = bookmark.model_dump(by_alias=True, mode='json')
        # HttpUrl normalizes by appending a trailing slash
        # nested Url/Date models serialize as dicts; the URL sits at ['url']['url']
        assert str(data['href']['url']) == 'https://example.com/'
        assert data['description'] == 'Example'
        assert data['time']  # Date default_factory populated

    def test_parse_from_alias_payload(self) -> None:
        payload = {
            'href': 'https://example.com',
            'description': 'Example',
            'time': '2025-01-01T00:00:00',
        }
        bookmark = Bookmark.model_validate(payload)
        assert bookmark.title == 'Example'
        # HttpUrl normalizes by appending a trailing slash
        assert str(bookmark.url) == 'https://example.com/'
