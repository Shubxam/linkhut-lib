"""HTTP helpers for the LinkHut API and arbitrary web-page scraping.

Note: make the order of the return types of functions with api calls consistent.
I.e. all the functions which call make_get_request should use `return response.json(), response.status_code`.

LinkHut API etiquette (https://docs.linkhut.org/overview.html#etiquette) is
enforced below at three points:

  1. **Rate limit.** `_throttle_request` is installed as a `'request'` event
     hook on the LinkHut client. It sleeps so each request goes out at least
     `_MIN_INTERVAL_SECONDS` after the previous one.

  2. **500/999 back-off.** `make_get_request` retries once after
     `_THROTTLE_BACKOFF_SECONDS` when the API returns 500 or 999. Other
     status codes are not retried — the etiquette says 500/999 specifically
     mean "you have been throttled."

  3. **User-Agent.** The LinkHut client sets `User-Agent: linkhut-lib/<ver>`
     with a contact URL so the upstream API can identify this client.
     Default identifiers (httpx's `python-httpx/X.Y.Z`) tend to get banned.

  4. **No silent URL modification.** This module validates URLs (`Url`,
     `HttpUrl`) but never rewrites them. The earlier `encode_url` helper
     was removed for that reason.
"""

import os
import time
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from loguru import logger

from .config import (
    LINKHUT_BASEURL,
    LINKHUT_HEADER,
    LinkHutEndpoint,
    firefox_user_agent,
)
from .exceptions import RequestError
from .models import APIResponse, GETResponse, HTMLResponse, Tag
from .validation import validate_date as _validate_date

# Re-export for callers that want `utils.validate_date(...)` instead of importing
# from the validation module directly.
validate_date = _validate_date


# Resolve the package version once for the User-Agent header. Mirrors the
# fallback in `linkhut_lib.__init__` so a missing package metadata (editable
# installs, etc.) doesn't crash client construction.
try:
    _PACKAGE_VERSION: str = version('linkhut-lib')
except PackageNotFoundError:  # pragma: no cover - editable install fallback
    _PACKAGE_VERSION = '0.0.0+unknown'

# Etiquette rule 1: minimum spacing between LinkHut API requests.
_MIN_INTERVAL_SECONDS: float = 1.0

# Etiquette rule 2: wait this long before the single retry on 500/999.
_THROTTLE_BACKOFF_SECONDS: float = 5.0


class _LinkHutThrottle:
    """Process-wide rate limiter for LinkHut API calls (etiquette rule 1).

    Module-level mutable state kept in an instance attribute rather than a
    bare `global` so `PLW0603` is happy and the state has a clear home.
    """

    __slots__ = ('_last_request_at',)

    def __init__(self) -> None:
        self._last_request_at: float = 0.0

    def wait_and_stamp(self) -> None:
        """Sleep so the next request is ≥ `_MIN_INTERVAL_SECONDS` after the last.

        `time.monotonic` so a wall-clock change can't break the math.
        """
        now = time.monotonic()
        wait = _MIN_INTERVAL_SECONDS - (now - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        # Stamp after the (possible) sleep, so the *next* call sees this one.
        self._last_request_at = time.monotonic()


_LINKHUT_THROTTLE = _LinkHutThrottle()


def _throttle_request(_request: httpx.Request) -> None:
    """Wait so this request goes out ≥ `_MIN_INTERVAL_SECONDS` after the previous one.

    Installed as an httpx `'request'` event hook on the LinkHut client. The
    hook fires once per request, immediately before the request leaves the
    process — so `time.sleep` here is the right place to enforce the
    etiquette rate limit. The `request` argument is required by httpx's
    hook signature but unused here.
    """
    _LINKHUT_THROTTLE.wait_and_stamp()


# httpx.Timeout separates the four phases so a slow DNS lookup and a slow read
# can be distinguished in logs and tuned independently. Pool is generous since
# the clients are reused across requests.
_LINKHUT_TIMEOUT = httpx.Timeout(10.0, connect=5.0, read=30.0, write=10.0, pool=5.0)
_SCRAPE_TIMEOUT = httpx.Timeout(10.0, connect=5.0, read=15.0, write=10.0, pool=5.0)


@lru_cache(maxsize=1)
def _linkhut_client() -> httpx.Client:
    """Return a memoized httpx.Client configured for the LinkHut API.

    Headers and base URL come from `config`; the bearer token is read from
    `LH_PAT` on first construction so this function is safe to call before
    the environment is fully loaded — the first real API call is what fails
    if the token is missing.

    Etiquette compliance wired into this client:
      - `User-Agent` identifies the library (etiquette rule 3).
      - `'request'` event hook enforces ≥1s spacing (rule 1).
      - `HTTPTransport(retries=1)` retries connect-level failures once so a
        momentary DNS hiccup doesn't surface as a `RequestError`.

    Back-off for 500/999 (etiquette rule 2) is handled in `make_get_request`
    because retries need to inspect `response.status_code` and re-dispatch
    through the same content-type path; a `'response'` event hook can't do
    that without re-reading the body.
    """
    load_dotenv()
    pat = os.getenv('LH_PAT')
    if not pat:
        raise RequestError('LH_PAT environment variable not set')
    headers = LINKHUT_HEADER.copy()
    headers['Authorization'] = headers['Authorization'].format(PAT=pat)
    headers['User-Agent'] = (
        f'linkhut-lib/{_PACKAGE_VERSION} (+https://github.com/shubxam/linkhut-lib)'
    )
    transport = httpx.HTTPTransport(retries=1)
    return httpx.Client(
        base_url=LINKHUT_BASEURL,
        headers=headers,
        timeout=_LINKHUT_TIMEOUT,
        transport=transport,
        event_hooks={'request': [_throttle_request]},
    )


@lru_cache(maxsize=1)
def _scrape_client() -> httpx.Client:
    """Return a memoized httpx.Client for arbitrary web-page fetches.

    Used by `get_link_meta` to retrieve the title/description for a target
    URL. No PAT — just a browser-style User-Agent so some servers don't
    refuse the request as bot traffic.

    Not subject to LinkHut etiquette — this client talks to third-party
    sites, not to api.ln.ht.
    """
    return httpx.Client(
        headers={'User-Agent': firefox_user_agent},
        timeout=_SCRAPE_TIMEOUT,
    )


def make_get_request(
    url: str,
    client: httpx.Client,
    payload: dict[str, str] | None = None,
) -> GETResponse:
    """Make a GET request through the provided client and return a structured response.

    The caller passes the right client (`_linkhut_client()` for the LinkHut API,
    `_scrape_client()` for arbitrary pages) so headers, timeouts, and pooling
    are configured once.

    Args:
        url (str): The URL to make the request to.
        client (httpx.Client): The client to use for the request.
        payload (dict[str, str] | None): Optional query parameters for the request.

    Returns:
        GETResponse: The structured response object.

    Raises:
        RequestError: If
          - the HTTP response has unknown content-type [not application/json or text/html]
          - HTTP response has status code 4xx or 5xx
          - there is a network-related error
          - an unexpected error occurs during the request.
    """
    try:
        logger.debug(f'making get request to following url: {url}')
        if payload is None:
            payload = {}
        # For the LinkHut client, `url` is expected to be relative (it's used as
        # the suffix to base_url). For the scrape client, `url` is absolute.
        response = client.get(url, params=payload)
        # Etiquette rule 2: 500/999 mean the API throttled us. Back off once
        # and retry. Other 4xx/5xx are not retried — they're caller errors,
        # not throttle signals. The throttle hook still fires for the retry
        # so we keep ≥1s spacing.
        if response.status_code in (500, 999):
            logger.warning(
                f'LinkHut returned {response.status_code}; '
                f'backing off {_THROTTLE_BACKOFF_SECONDS}s and retrying once.'
            )
            time.sleep(_THROTTLE_BACKOFF_SECONDS)
            response = client.get(url, params=payload)
        # Surface 4xx/5xx before parsing the body so JSON-shaped error
        # responses don't get silently coerced into APIResponse and
        # masquerade as not-found.
        response.raise_for_status()
        status_code: int = response.status_code
        request_url: str = response.url.__str__()
        content_type_str: str = response.headers.get('content-type', '')
        if 'application/json' in content_type_str:
            content_type = 'application/json'
            # pydantic.Json accepts raw bytes/strings and parses to a Python
            # value on validation. Don't pre-parse with `response.json()` —
            # the field rejects Python dicts (it expects JSON-encoded input).
            data = APIResponse(content_json=response.content)
        elif 'text/html' in content_type_str:
            content_type = 'text/html'
            data = HTMLResponse(
                content_soup=BeautifulSoup(response.text, 'html.parser')
            )
        else:
            raise RequestError(
                f"Unsupported content type: {content_type_str}. Expected 'application/json' or 'text/html'."
            )
        response_object: GETResponse = GETResponse(
            status_code=status_code,
            content_type=content_type,
            url=request_url,
            data=data,
        )
        return response_object

    except httpx.HTTPStatusError as exc:
        raise RequestError(
            f'HTTP error occurred: {exc.response.text}',
            status_code=exc.response.status_code,
            response_data=exc.response.json()
            if exc.response.headers.get('content-type', '').startswith(
                'application/json'
            )
            else None,
        ) from exc
    except httpx.RequestError as exc:
        raise RequestError(
            f'Network error occurred while requesting {exc.request.url!r}: {exc}'
        ) from exc
    except Exception as e:
        raise RequestError(f'An unexpected error occurred: {e}') from e


def linkhut_api_call(action: LinkHutEndpoint, payload: dict[str, str]) -> APIResponse:
    """Make an API call to the specified LinkHut endpoint and return the response.

    Args:
        action (str): The API action to perform (e.g., "bookmark_create")
        payload (dict[str, str], optional): Query parameters for the request

    Returns:
        Response: The response object containing the API response data.

    Raises:
        RequestError: If
          - the HTTP GET Response has unknown content-type [not application/json or text/html]
          - HTTP response has status code 4xx or 5xx
          - there is a network-related error
          - an unexpected error occurs during the request.

    """
    # Note: Different API endpoints return different data, let the calling function handle the extraction and exception handling.
    # calling functions will define how to handle the exception and the replacement values to use if http request fails.
    client = _linkhut_client()
    url: str = action.value  # relative; client.base_url resolves it
    logger.debug(
        f'making request to {client.base_url}{url} with header {client.headers}'
    )
    response: GETResponse = make_get_request(url=url, client=client, payload=payload)
    if not isinstance(response.data, APIResponse):
        raise RequestError(f'Expected APIResponse but got {type(response.data)}')
    return response.data


def get_link_meta(dest_url: str) -> tuple[str, str]:
    """Fetch the url metadata.

    Args:
        dest_url (str): The URL to fetch the title for.

    Returns:
        - str: The title of the link.
        - description: The description of the link.


    Note: If title fetching fails due to network errors or access restrictions,
      returns the URL as the title.
    """
    logger.debug(f'making request to get title : {dest_url}')

    try:
        client = _scrape_client()
        response: GETResponse = make_get_request(url=dest_url, client=client)
        if not isinstance(response.data, HTMLResponse):
            logger.error(
                f'Expected HTMLResponse but got {type(response.data)} for URL: {dest_url}'
            )
            return dest_url, ''

        # Extract the title from the HTML content
        soup: BeautifulSoup = response.data.content_soup  # type: ignore[attr-defined]

        # use the open graph title and description if available.
        # `select_one` returns `Tag | None` (so `.get` is valid); `find` is
        # typed as `PageElement | None` in BeautifulSoup's stubs, which would
        # require a suppression on `.get`.
        og_title_tag = soup.select_one('meta[property="og:title"]')
        open_graph_title: str = (
            str(og_title_tag.get('content', '')) if og_title_tag is not None else ''
        )
        og_desc_tag = soup.select_one('meta[property="og:description"]')
        open_graph_description: str = (
            str(og_desc_tag.get('content', '')) if og_desc_tag is not None else ''
        )

        # Fallback to the HTML title if Open Graph title is not available
        title_tag = soup.select_one('title')
        html_title: str = title_tag.text.strip() if title_tag is not None else ''

        title: str = open_graph_title or html_title or dest_url
        desc: str = open_graph_description or ''

        # function is supposed to send link title, so we send link title by handling the exceptions here.
        return title, desc
    except httpx.RequestError as e:
        logger.warning(f'Network error while fetching title for {dest_url}: {e}')
        return dest_url, ''
    except (KeyError, AttributeError, TypeError) as e:
        # Title extraction can hit unexpected shape mismatches in third-party
        # HTML; surface the error but fall back to the URL rather than crash.
        logger.error(f'An error occurred while fetching title for {dest_url}: {e}')
        return dest_url, ''


def get_tags_suggestion(dest_url: str) -> list[Tag]:
    """Fetch tags suggestion for a link using the LinkHut API.

    Args:
        dest_url (str): The URL of the link to fetch tags for.

    Returns:
        list[Tag]: A list of suggested `Tag` objects (empty on failure).

    Note: returns an empty list if the request fails or no suggested tags
    are found.
    """
    action: LinkHutEndpoint = LinkHutEndpoint.TAG_SUGGEST
    payload: dict[str, str] = {
        'url': dest_url,
    }

    logger.debug(f'fetching suggested tags for : {dest_url}')

    try:
        response: APIResponse = linkhut_api_call(action=action, payload=payload)
        body: Any = response.content_json
        if not isinstance(body, list):
            logger.warning(
                f'Unexpected tag suggestion response shape for {dest_url}: {body!r}'
            )
            return []
        tags: list[Tag] = []
        # ty 0.0.x doesn't narrow the type of `body` from `Any` to `list[...]`
        # through the isinstance check above, so we work directly off `body`
        # and use a single-element bind.
        popular: list[str] = (
            body[0].get('popular', []) if body and isinstance(body[0], dict) else []
        )
        recommended: list[str] = (
            body[1].get('recommended', [])
            if len(body) > 1 and isinstance(body[1], dict)
            else []
        )
        tags.extend(Tag(name=tag) for tag in popular)
        tags.extend(Tag(name=tag) for tag in recommended)
        return tags
    except RequestError as e:
        # if there is a network error or the API is down, we handle that in the
        # following exception.
        logger.warning(f'Failed to fetch tags for {dest_url}: {e}')
        return []


def tags_in_api_format(tags: list[Tag]) -> str:
    """Return tags in string format separated by +."""
    return '+'.join(tag.name for tag in tags)
