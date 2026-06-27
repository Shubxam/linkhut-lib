"""Smoke tests for the existing helpers.

These tests exercise pure helpers (no live HTTP) so `pytest` exits 0 on the
last-known-good main. They also serve as a safety net while the typed-API
refactor is being completed on a separate branch.
"""

import httpx
import pytest

from linkhut_lib import utils
from linkhut_lib.exceptions import InvalidTagFormatError, RequestError
from linkhut_lib.models import Bookmark, Tag
from linkhut_lib.utils import tags_in_api_format
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


class TestLinkHutEtiquette:
    """Verify LinkHut API etiquette rules are enforced.

    See https://docs.linkhut.org/overview.html#etiquette for the rules.
    """

    # Status codes the etiquette document calls out as throttle signals.
    THROTTLE_STATUS_CODES: tuple[int, ...] = (500, 999)
    OK_STATUS: int = 200
    NOT_FOUND_STATUS: int = 404
    # Tolerance when checking the throttle slept the right amount: anything
    # ≥ 0.99s is "essentially 1.0s" for a float that's gone through sleep.
    THROTTLE_TOLERANCE: float = 0.99
    EXPECTED_RETRY_CALL_COUNT: int = 2
    EXPECTED_NO_RETRY_CALL_COUNT: int = 1

    def test_linkhut_client_user_agent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Rule 3: User-Agent identifies the library and version."""
        monkeypatch.setenv('LH_PAT', 'test-token')
        utils._linkhut_client.cache_clear()
        try:
            client = utils._linkhut_client()
            ua = client.headers['User-Agent']
            assert ua.startswith('linkhut-lib/'), f'User-Agent was {ua!r}'
            assert 'github.com/shubxam/linkhut-lib' in ua
        finally:
            utils._linkhut_client.cache_clear()

    def test_throttle_enforces_one_second_spacing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rule 1: ≥1s between requests on the LinkHut client.

        The throttle hook records the duration it would have slept (we mock
        `time.sleep` to a no-op so the test runs in milliseconds).
        """
        sleeps: list[float] = []

        def record_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr(utils.time, 'sleep', record_sleep)
        # Reset the throttle so the first call doesn't carry state from
        # earlier tests.
        utils._LINKHUT_THROTTLE._last_request_at = 0.0

        handler_calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal handler_calls
            handler_calls += 1
            return httpx.Response(self.OK_STATUS, json={'ok': True})

        transport = httpx.MockTransport(handler)
        with httpx.Client(
            transport=transport,
            event_hooks={'request': [utils._throttle_request]},
        ) as client:
            client.get('https://example.com/a')
            client.get('https://example.com/b')

        # Two requests fired back-to-back → the second one should have
        # slept ~1s.
        assert any(s >= self.THROTTLE_TOLERANCE for s in sleeps), (
            f'expected ≥1s sleep, recorded sleeps: {sleeps}'
        )
        assert handler_calls == self.EXPECTED_RETRY_CALL_COUNT

    def test_500_triggers_one_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Rule 2: 500 → single retry, then surface the response."""

        def no_sleep(_seconds: float) -> None:
            return None

        monkeypatch.setattr(utils.time, 'sleep', no_sleep)
        utils._LINKHUT_THROTTLE._last_request_at = 0.0

        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(500, json={'error': 'throttled'})
            return httpx.Response(
                self.OK_STATUS,
                json={'result_code': 'done', 'posts': []},
                headers={'content-type': 'application/json'},
            )

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as client:
            result = utils.make_get_request(
                url='https://api.ln.ht/v1/posts/get',
                client=client,
                payload={'count': '5'},
            )

        # Original + one retry = 2 calls.
        assert call_count == self.EXPECTED_RETRY_CALL_COUNT
        assert result.status_code == self.OK_STATUS

    def test_999_triggers_one_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Rule 2: 999 (rate-limit signal) is retried just like 500."""

        def no_sleep(_seconds: float) -> None:
            return None

        monkeypatch.setattr(utils.time, 'sleep', no_sleep)
        utils._LINKHUT_THROTTLE._last_request_at = 0.0

        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(999, text='rate limited')
            return httpx.Response(
                self.OK_STATUS,
                json={'result_code': 'done'},
                headers={'content-type': 'application/json'},
            )

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as client:
            utils.make_get_request(
                url='https://api.ln.ht/v1/posts/get',
                client=client,
            )

        assert call_count == self.EXPECTED_RETRY_CALL_COUNT

    def test_404_is_not_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Rule 2: only 500/999 trigger a retry; other 4xx raise immediately."""
        sleep_calls: list[float] = []

        def record_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        monkeypatch.setattr(utils.time, 'sleep', record_sleep)
        utils._LINKHUT_THROTTLE._last_request_at = 0.0

        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(self.NOT_FOUND_STATUS, json={'error': 'not found'})

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as client:
            with pytest.raises(RequestError) as exc_info:
                utils.make_get_request(
                    url='https://api.ln.ht/v1/posts/get',
                    client=client,
                )
            assert exc_info.value.status_code == self.NOT_FOUND_STATUS

        # No retry, no back-off sleep.
        assert call_count == self.EXPECTED_NO_RETRY_CALL_COUNT
        assert sleep_calls == []
