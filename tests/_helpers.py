"""Test helpers for patching the HTTP and side-effect layers.

The public functions in `linkhut_lib.linkhut_lib` reach into `utils` for two
things: HTTP (`utils.linkhut_api_call`) and side-effect helpers
(`utils.get_link_meta`, `utils.get_tags_suggestion`). Both are patched per-test
so the public-function tests stay deterministic and fast — the helpers'
behavior is covered by `tests/test_smoke.py` and (eventually)
`tests/test_utils.py`.
"""

import json
from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

import pytest

from linkhut_lib.models import APIResponse, Tag

# Fake status code for the request-error propagation tests.
HTTP_SERVICE_UNAVAILABLE: int = 503


def make_api_response(body: dict[str, Any] | list[Any] | str | bytes) -> APIResponse:
    """Build an `APIResponse` from a dict / list / JSON string / bytes.

    Pydantic's `Json` field accepts any JSON-encoded input; passing the
    pre-built dict form via `model_validate({'content_json': body})` would
    not parse strings, so we go through `model_validate` with a JSON dump
    when the caller passes a dict/list.
    """
    if isinstance(body, (dict, list)):
        payload: bytes = json.dumps(body).encode()
    elif isinstance(body, str):
        payload = body.encode()
    else:
        payload = body
    return APIResponse(content_json=payload)


def patch_api_call(
    monkeypatch: pytest.MonkeyPatch,
    responder: Callable[..., APIResponse],
) -> None:
    """Patch `utils.linkhut_api_call` on the `linkhut_lib` module's import.

    `linkhut_lib.py` does `from . import utils` and then calls
    `utils.linkhut_api_call(...)`, so the lookup happens via the
    `linkhut_lib.utils` attribute. Patching the attribute (rather than the
    function on the utils module) keeps the patch scoped to the public-API
    callers and leaves `utils.linkhut_api_call` itself intact for the
    smoke tests.
    """
    monkeypatch.setattr(
        'linkhut_lib.linkhut_lib.utils.linkhut_api_call',
        responder,
    )


def last_payload(responder: Mock) -> dict[str, Any]:
    """Return the `payload` kwarg from the responder's most recent call.

    `linkhut_api_call` is always called as `linkhut_api_call(action=...,
    payload=...)` (see linkhut_lib.py), so `call_args.args` is empty and
    `call_args.kwargs['payload']` is what tests want.
    """
    return responder.call_args.kwargs['payload']


def last_action(responder: Mock) -> Any:
    """Return the `action` kwarg from the responder's most recent call."""
    return responder.call_args.kwargs['action']


def patch_link_meta(
    monkeypatch: pytest.MonkeyPatch,
    title: str = 'Mocked Title',
    description: str = 'Mocked description',
) -> None:
    """Patch `utils.get_link_meta` so `create_bookmark` doesn't hit the network."""

    def fake_meta(_url: str) -> tuple[str, str]:
        return title, description

    monkeypatch.setattr(
        'linkhut_lib.linkhut_lib.utils.get_link_meta',
        fake_meta,
    )


def patch_tags_suggestion(
    monkeypatch: pytest.MonkeyPatch,
    tags: list[str] | None = None,
) -> None:
    """Patch `utils.get_tags_suggestion` so it returns a fixed list of Tags."""

    def fake_suggest(_url: str) -> list[Tag]:
        return [Tag(name=t) for t in (tags or [])]

    monkeypatch.setattr(
        'linkhut_lib.linkhut_lib.utils.get_tags_suggestion',
        fake_suggest,
    )


def disable_tag_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch `utils.get_tags_suggestion` to return an empty list."""
    patch_tags_suggestion(monkeypatch, tags=[])


def done_responder(body: dict[str, Any] | list[Any] | None = None) -> Mock:
    """Return a `Mock` that mimics `linkhut_api_call(action, payload) -> APIResponse`.

    `unittest.mock.Mock` accepts any positional/keyword args and returns
    the configured value, which sidesteps the
    `ARG005 (unused-lambda-argument)` lint that bare lambdas trip when
    both args are unused. Use `responder.assert_called_with(...)` or
    `responder.call_args_list` to inspect what the function-under-test
    sent; use `StatefulResponder` instead when successive calls need
    different responses.
    """
    return Mock(return_value=make_api_response(body or {'result_code': 'done'}))


class StatefulResponder:
    """A responder that returns a different response for each successive call.

    Used by tests where the function-under-test makes multiple API calls
    in a known order (e.g., `get_bookmarks` → `create_bookmark`). The
    first N calls get `responses[0..N-1]`; the last response is reused
    if more calls arrive than responses.
    """

    def __init__(self, responses: list[APIResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[Any, Any]] = []

    def __call__(self, action: Any, payload: Any) -> APIResponse:
        self.calls.append((action, payload))
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[index]
