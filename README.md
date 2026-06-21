# linkhut-lib

Python client for the [LinkHut](https://linkhut.org) bookmarking service API.
Thin wrapper over `httpx` with pydantic models for typed responses, automatic
title/tag fetching, and rate-limit-aware retries.

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

## Usage

`linkhut-lib` exposes module-level functions — there is no client object to
instantiate. Import the functions and model classes you need:

```python
from linkhut_lib import (
    Bookmark,
    Date,
    Tag,
    Url,
    create_bookmark,
    delete_bookmark,
    delete_tag,
    get_bookmarks,
    get_reading_list,
    rename_tag,
    update_bookmark,
)
from linkhut_lib.exceptions import (
    BookmarkExistsError,
    BookmarkNotFoundError,
    InvalidDateFormatError,
    InvalidTagFormatError,
    InvalidURLError,
    RequestError,
)
```

### Create a bookmark

```python
result = create_bookmark(
    url='https://example.com/article',
    title='An interesting article',       # optional — fetched if omitted
    tags='python, linkhut-lib',            # optional — suggested if omitted
    note='Read this later',                # optional
    to_read=True,                          # optional, default False
    private=False,                         # optional, default False
    replace=False,                         # optional, default False
)
```

### List bookmarks

```python
# Most recent 15 bookmarks (the LinkHut default)
recent = get_bookmarks()

# Last N bookmarks
last_ten = get_bookmarks(count=10)

# Filter by tag, date, or URL
python_posts = get_bookmarks(tag='python')
specific = get_bookmarks(url='https://example.com/article')
by_date = get_bookmarks(date='2026-06-01')
```

### Update a bookmark

`update_bookmark` will create the bookmark if no entry exists for the URL
yet. Pass `new_tag`, `new_note`, `new_private`, or `new_to_read` to change a
single field. `replace=False` (the default) appends tags/notes; `replace=True`
overwrites them.

```python
update_bookmark(
    url='https://example.com/article',
    new_tag='reviewed',
    new_to_read=False,
)
```

### Reading list

```python
unread = get_reading_list(count=10)
```

### Delete a bookmark

```python
delete_bookmark(url='https://example.com/article')
```

### Tag operations

```python
rename_tag(old_tag='python', new_tag='py')
delete_tag(tag='py')
```

### Typed responses

Functions return plain `dict[str, str]` payloads that match the LinkHut wire
format. The pydantic models `Bookmark`, `Tag`, `Date`, and `Url` are available
when you want a typed object:

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
print(bookmark.title)     # 'An interesting article'
print(bookmark.url)       # 'https://example.com/article/'
print(bookmark.tags)      # [Tag(name='python'), Tag(name='linkhut-lib')]
```

## Error handling

Every public function raises a `LinkHutError` subclass on failure. Catch the
base class for a blanket handler, or the specific subclass when you want to
react differently:

| Exception | Raised when |
|-----------|-------------|
| `BookmarkExistsError` | `create_bookmark` finds an existing entry and `replace=False`. |
| `BookmarkNotFoundError` | `get_bookmarks` / `delete_bookmark` find nothing matching the filter. |
| `InvalidDateFormatError` | A `date=` argument isn't a valid ISO-8601 timestamp. |
| `InvalidTagFormatError` | A tag name is empty, too long, or contains non-alphanumeric characters. |
| `InvalidURLError` | A `url=` argument isn't a valid HTTP(S) URL. |
| `RequestError` | The LinkHut API returns a non-`done` result code, or a network/HTTP error occurs. |

## Requirements

- Python 3.13+
- httpx, pydantic, beautifulsoup4, loguru, python-dotenv

## License

MIT License — see [LICENSE](LICENSE) for details.
