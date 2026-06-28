# linkhut-lib

[![PyPI version](https://badge.fury.io/py/linkhut-lib.svg)](https://badge.fury.io/py/linkhut-lib)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Python client for the [LinkHut](https://linkhut.org) bookmarking service API.
Thin wrapper over `httpx` with pydantic models for typed responses, automatic
title/tag fetching, and rate-limit-aware retries.

`linkhut-lib` powers the [`linkhut-cli`](https://pypi.org/project/linkhut-cli/)
command-line tool; this library is the public Python API it calls under the
hood.

## Why use this library?

The [LinkHut HTTP API](https://docs.linkhut.org/) is a small JSON-over-HTTP
surface but it has a few sharp edges that this library smooths over:

- **Rate limiting.** The API documents a ≥1-second cadence between calls
  and a single retry on `500` / `999` responses. `linkhut-lib` enforces
  both via an `httpx` event hook and a one-shot back-off, so callers
  don't have to.
- **User-Agent.** Default `httpx` user agents tend to get banned. The
  library identifies itself as `linkhut-lib/<version>` and includes a
  contact URL.
- **Wire-format quirks.** `dt` must be `CCYY-MM-DDThh:mm:ssZ` (literal
  `T` separator, literal `Z` suffix). The library rejects bad strings
  with `InvalidDateFormatError` before the HTTP call, so callers get a
  clear error instead of a server-side rejection.
- **No silent URL rewriting.** `linkhut-lib` validates URLs but never
  rewrites them — LinkHut etiquette forbids silent URL mutation.

If you only want a CLI, use [`linkhut-cli`](https://pypi.org/project/linkhut-cli/).
If you want to embed LinkHut access in a Python application — a webhook
handler, a periodic sync job, a Jupyter notebook, a script that triages
incoming links — this library is the entry point.

## Installation

```bash
# using uv
uv add linkhut-lib

# using pip
pip install linkhut-lib
```

## Configuration

The client reads one environment variable:

- `LH_PAT` — your LinkHut API token, found at <https://linkhut.org/settings/api>.

A `.env` file in the working directory is also picked up automatically:

```dotenv
LH_PAT=your-api-token
```

## Quick start

```python
from linkhut_lib import (
    create_bookmark,
    get_bookmarks,
    update_bookmark,
    delete_bookmark,
    BookmarkCreateResult,
    CreateOutcome,
)

# Add a bookmark
result = create_bookmark(
    url='https://example.com/article',
    title='An interesting article',
    tags='python, linkhut-lib',
    to_read=True,
)
if result.outcome == CreateOutcome.CREATED:
    print(f'Created: {result.url}')

# Fetch the most recent 10 bookmarks
recent = get_bookmarks(count=10)

# Update an existing bookmark (strict: raises if URL not bookmarked)
update_bookmark(
    url='https://example.com/article',
    new_tag='reviewed',
    new_to_read=False,
)
```

## API reference

The library exposes module-level functions. There is no client object to
instantiate — the LinkHut token is read from the environment on first use
and memoized for the process lifetime.

### `create_bookmark(url, ...)`

Create a new bookmark. The title is auto-fetched from the destination page
if not given, and tags are auto-suggested from the page content if not
given and `fetch_tags=True` (the default).

```python
from linkhut_lib import create_bookmark, CreateOutcome

result = create_bookmark(
    url='https://example.com/article',
    title='An interesting article',       # optional — fetched if omitted
    tags='python, linkhut-lib',            # optional — suggested if omitted
    note='Read this later',                # optional
    to_read=True,                          # optional, default False
    private=False,                         # optional, default False
    replace=False,                         # optional, default False
    fetch_tags=True,                       # optional, default True
)

result.outcome   # CreateOutcome: CREATED | REPLACED | ALREADY_EXISTS
result.url       # the URL you passed in
result.bookmark  # dict[str, str] — server-shape payload
```

**Raises**: `InvalidURLError` (bad URL), `BookmarkExistsError` (URL
already bookmarked and `replace=False`), `RequestError` (network or
non-`done` API response).

### `get_bookmarks(tag, date, url, count)`

Fetch bookmarks. Without arguments this returns the 15 most recent
bookmarks. With `count` it returns the most recent N. With `tag`, `date`,
or `url` it returns bookmarks matching the filter.

```python
from linkhut_lib import get_bookmarks

# Most recent 15 (the LinkHut default)
recent = get_bookmarks()

# Last N
last_ten = get_bookmarks(count=10)

# Filter by tag, date, or URL
python_posts = get_bookmarks(tag='python')
specific = get_bookmarks(url='https://example.com/article')
by_date = get_bookmarks(date='2026-06-01')

# Multi-tag AND-filter (joins with '+' per LinkHut docs)
multi = get_bookmarks(tag=['python', 'testing'])
```

`tag` accepts a `str` or a `list[str]`. For `count > 0` (the recent
endpoint), only a single tag is allowed; pass a string or a
single-element list. For `count == 0` (the get endpoint), a list is
joined with `+` to AND-filter per
<https://docs.linkhut.org/posts.html>.

`date` must match the documented `CCYY-MM-DDThh:mm:ssZ` format
(literal `T` separator, literal `Z` suffix). `count` is clamped to
1..100 on the recent endpoint.

**Returns**: a `list[dict[str, str]]` of server-shape bookmark payloads.

**Raises**: `ValueError` (bad `count` or multi-tag list on `/recent`),
`InvalidDateFormatError` (bad `dt` string), `BookmarkNotFoundError` (no
matching bookmark), `RequestError`.

### `update_bookmark(url, ...)`

**Strict update.** Changes an existing bookmark's tags, notes, privacy
setting, or to-read status. Raises `BookmarkNotFoundError` if the URL
isn't already bookmarked — use `upsert_bookmark` if you want the
create-on-miss behavior.

```python
from linkhut_lib import update_bookmark

update_bookmark(
    url='https://example.com/article',
    new_tag='reviewed',                   # appends by default
    new_to_read=False,                    # marks as read
)
```

`replace=False` (the default) appends tags and notes to the existing
values; `replace=True` overwrites them. Passing `new_to_read` and/or
`new_private` with no other change writes through to the existing
state and returns a `NO_OP` outcome if the state already matches.

**Returns**: `BookmarkUpdateResult` with `.outcome` (`UPDATED` or
`NO_OP`), `.url`, and `.bookmark`.

**Raises**: `BookmarkNotFoundError` (URL not bookmarked),
`RequestError` (no update parameters given).

### `upsert_bookmark(url, ...)`

Like `update_bookmark`, but creates the bookmark if it doesn't exist
yet. The pre-`linkhut-lib 0.1.0` behavior of `update_bookmark`
(implicit create-on-update) lives here, so callers that relied on it
can opt in explicitly.

```python
from linkhut_lib import upsert_bookmark

result = upsert_bookmark(
    url='https://example.com/article',
    new_tag='reviewed',
)
result.outcome   # UpdateOutcome: UPDATED | UPSERTED | NO_OP
```

**Returns**: `BookmarkUpdateResult`.

**Raises**: `RequestError` (no update parameters given). Does **not**
raise on missing bookmarks — it creates them.

### `get_reading_list(count=5)`

Returns the most recent `count` bookmarks tagged `unread`. Thin
wrapper around `get_bookmarks(tag='unread', count=count)`.

```python
from linkhut_lib import get_reading_list

unread = get_reading_list(count=10)
```

**Returns**: a `list[dict[str, str]]`.

**Raises**: `BookmarkNotFoundError` (no `unread` bookmarks),
`RequestError`.

### `delete_bookmark(url)`

Delete the bookmark with the given URL.

```python
from linkhut_lib import delete_bookmark

delete_bookmark(url='https://example.com/article')
# {'bookmark_deletion': 'success'}
```

**Returns**: a `dict[str, str]` confirmation on success.

**Raises**: `InvalidURLError`, `BookmarkNotFoundError` (URL not
bookmarked), `RequestError`.

### `rename_tag(old_tag, new_tag)` and `delete_tag(tag)`

```python
from linkhut_lib import rename_tag, delete_tag

rename_tag(old_tag='python', new_tag='py')
# {'tag_renaming': 'success'}

delete_tag(tag='obsolete-tag')
# {'tag_deletion': 'success'}
```

**Returns**: a `dict[str, str]` confirmation on success.

**Raises**: `InvalidTagFormatError` (tag name has spaces or special
characters), `RequestError` (tag not found, or non-`done` API
response).

## Typed result models

`create_bookmark`, `update_bookmark`, and `upsert_bookmark` return
typed pydantic models instead of bare dicts. This makes the
"did this call create, update, or no-op?" question explicit in your
code instead of implicit in the response shape.

```python
from linkhut_lib import (
    create_bookmark,
    update_bookmark,
    upsert_bookmark,
    BookmarkCreateResult,
    BookmarkUpdateResult,
    CreateOutcome,
    UpdateOutcome,
)

# Branch on outcome
result = create_bookmark(url='https://example.com')
match result.outcome:
    case CreateOutcome.CREATED:
        print(f'New: {result.url}')
    case CreateOutcome.REPLACED:
        print(f'Replaced: {result.url}')
    case CreateOutcome.ALREADY_EXISTS:
        # Raised in practice, but the enum exists for completeness.
        ...
```

`result.bookmark` is the server-shape payload dict (the same shape
`get_bookmarks` returns) so callers can read fields directly without
re-parsing the API response.

## Pydantic model classes

The library also exposes pydantic models for parsing the LinkHut
wire format yourself, validating user input, or working with the
`get_bookmarks` return value:

- `Bookmark` — full bookmark with `url`, `title`, `created_at`,
  `note`, `tags`, `public`, `toread`, and `hash` fields. Accepts
  LinkHut's `href` / `description` / `time` / `extended` / `tag` /
  `shared` / `toread` aliases on input.
- `Tag` — single tag with format validation.
- `Date` — bookmark timestamp with format validation.
- `Url` — URL with `HttpUrl` validation.
- `APIResponse`, `HTMLResponse`, `GETResponse` — lower-level
  response wrappers, mostly for internal use.

```python
from linkhut_lib import Bookmark

bookmark = Bookmark.model_validate({
    'href': 'https://example.com/article',
    'description': 'An interesting article',
    'extended': 'Read this later',
    'tag': 'python linkhut-lib',
    'time': '2026-06-21T10:00:00Z',
    'shared': 'yes',
    'toread': 'no',
})
print(bookmark.title)   # 'An interesting article'
print(bookmark.url)     # 'https://example.com/article/'
print(bookmark.tags)    # [Tag(name='python'), Tag(name='linkhut-lib')]
```

## Error handling

Every public function raises a `LinkHutError` subclass on failure.
Catch the base class for a blanket handler, or the specific subclass
when you want to react differently:

| Exception | Raised when |
|-----------|-------------|
| `BookmarkExistsError` | `create_bookmark` finds an existing entry and `replace=False`. |
| `BookmarkNotFoundError` | `get_bookmarks`, `delete_bookmark`, or `update_bookmark` finds nothing matching the filter. |
| `InvalidDateFormatError` | A `date=` argument isn't `CCYY-MM-DDThh:mm:ssZ` (literal `T` separator, literal `Z` suffix). |
| `InvalidTagFormatError` | A tag name is empty, too long, or contains non-alphanumeric characters. |
| `InvalidURLError` | A `url=` argument isn't a valid HTTP(S) URL. |
| `RequestError` | The LinkHut API returns a non-`done` result code, or a network/HTTP error occurs. Carries `.status_code` and `.response_data` when available. |

`update_bookmark` and `upsert_bookmark` also raise `RequestError` if
no update parameters are given (callers must specify at least one
of `new_tag`, `new_note`, `new_private`, `new_to_read`).

## Requirements

- Python 3.13+
- `httpx`, `pydantic`, `beautifulsoup4`, `loguru`, `python-dotenv`

## License

MIT License — see [LICENSE](LICENSE) for details.