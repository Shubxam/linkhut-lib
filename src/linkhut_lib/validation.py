"""Pure-function validators for the LinkHut API.

Each helper raises a `LinkHutError` subclass on bad input. These functions
are pure: no class state, no I/O. Designed to be unit-tested in isolation
and reused from both `linkhut_lib.py` and the model field validators in
`models.py`.
"""

import re
from datetime import date, datetime

from .exceptions import InvalidDateFormatError, InvalidTagFormatError


def validate_tag(name: str) -> str:
    """Ensure tag name is alphanumeric and not empty."""
    if not name.replace('-', '').replace('_', '').isalnum():
        raise InvalidTagFormatError(f'Invalid characters present in tag name: {name}')
    return name


def validate_date(datetime_obj: datetime | str | date) -> datetime:
    """Ensure date is a valid datetime object or string.

    Accepts `datetime`, `date`, or ISO-formatted strings (the latter via
    `datetime.fromisoformat`). Strings missing the time component are
    rejected — the LinkHut API requires `CCYY-MM-DDThh:mm:ssZ` per
    https://docs.linkhut.org/posts.html. For the strict wire-format check
    used by `get_bookmarks`, see `validate_dt_strict`.
    """
    if isinstance(datetime_obj, str):
        try:
            return datetime.fromisoformat(datetime_obj)
        except ValueError as e:
            raise InvalidDateFormatError(
                f'Invalid date string format: {datetime_obj}'
            ) from e
    if isinstance(datetime_obj, datetime):
        return datetime_obj
    # `datetime` is a subclass of `date`, so this catches `date` and any
    # future `datetime`-like type. Reaching here with anything else would
    # raise `AttributeError` from `isoformat()` — fail loudly with a clear
    # message instead.
    if hasattr(datetime_obj, 'isoformat'):
        return datetime.fromisoformat(datetime_obj.isoformat())
    raise TypeError('Date must be a datetime object or an ISO formatted string.')


# LinkHut wire format per https://docs.linkhut.org/posts.html: literal
# `CCYY-MM-DDThh:mm:ssZ` — capital T separator, capital Z suffix, all
# components required. `datetime.fromisoformat` in Python 3.13 accepts the
# `Z` suffix but tolerates shorter strings like `2025-01-01`, so we
# enforce the full shape with a regex before parsing.
_DT_STRICT_RE: re.Pattern[str] = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')


def validate_dt_strict(value: str) -> datetime:
    """Validate a LinkHut `dt` query parameter.

    The LinkHut `/v1/posts/get` and `/v1/posts/all` endpoints require
    `CCYY-MM-DDThh:mm:ssZ` (capital T separator, capital Z suffix, all
    components required). Anything else will be rejected server-side;
    we catch it here so the caller gets a clear `InvalidDateFormatError`
    instead of a vague `RequestError`.

    Args:
        value: The `dt` string the caller intends to send.

    Returns:
        A `datetime` parsed from the input.

    Raises:
        InvalidDateFormatError: If `value` does not match the strict format.
    """
    if not isinstance(value, str) or not _DT_STRICT_RE.match(value):
        raise InvalidDateFormatError(
            f'Invalid dt format: {value!r}. '
            "Expected 'CCYY-MM-DDThh:mm:ssZ' (literal T separator, Z suffix)."
        )
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
