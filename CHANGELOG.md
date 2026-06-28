# Changelog

All notable changes to linkhut-lib are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-28

First public release of `linkhut-lib` as a separately versioned Python
package. Previously the library code lived alongside the
[`linkhut-cli`](https://pypi.org/project/linkhut-cli/) CLI; this release
is the first time it ships on its own.

### Added

- **`upsert_bookmark(url, ...)`** — create-on-update path for users
  who want the previous implicit create behavior. Pass
  `upsert_bookmark(...)` instead of `update_bookmark(...)` to
  create the bookmark if it isn't already saved.
- **`BookmarkCreateResult`** / **`BookmarkUpdateResult`** — typed
  result models for the bookmark write paths. Both expose
  `.outcome` (a `CreateOutcome` or `UpdateOutcome` enum), `.url`,
  and `.bookmark` (the server-shape payload dict).
- **`CreateOutcome`** / **`UpdateOutcome`** enums — discriminator
  values on the typed results.
- **`get_bookmarks(tag=...)` accepts `str | list[str]`.** For
  `count > 0` (the recent endpoint), only a single tag is allowed;
  a multi-element list raises `ValueError`. For `count == 0` (the
  get endpoint), a list is joined with `+` to AND-filter per
  <https://docs.linkhut.org/posts.html>.
- **Strict `dt` format validation in `get_bookmarks`.** Strings must
  match `CCYY-MM-DDThh:mm:ssZ` (literal `T` separator, literal `Z`
  suffix). Anything else raises `InvalidDateFormatError` before the
  API call.
- **Count clamping in `get_bookmarks`.** The `count` parameter on
  the recent endpoint is now clamped to 1..100, matching the
  documented bounds at <https://docs.linkhut.org/posts.html>.
  Out-of-range values raise `ValueError` client-side.
- **`Tag`, `Date`, `Url`, `Bookmark` pydantic models** re-exported
  from the top-level `linkhut_lib` namespace for callers that want
  to parse or validate LinkHut wire-format payloads directly.
- **Throttled httpx client.** The `linkhut-lib` client enforces
  ≥1-second spacing between API calls (etiquette rule 1) and a
  single back-off retry on `500` / `999` responses (etiquette rule 2).
  The default `httpx` User-Agent (which gets banned) is replaced with
  `linkhut-lib/<version> (+contact URL)`.

### Changed

- **`update_bookmark` is now strict.** It raises
  `BookmarkNotFoundError` when the URL is not already bookmarked.
  The previous implicit create-on-update behavior moved to
  `upsert_bookmark`. Call sites that relied on the silent create
  should switch to `upsert_bookmark(url, ...)` with the same
  arguments.
- **`create_bookmark` and `upsert_bookmark` return a typed result**
  (`BookmarkCreateResult` / `BookmarkUpdateResult`) instead of the
  outbound payload dict. To get the same shape the old code
  returned, read `result.bookmark`.
- The duplicate "no bookmarks found" branches in `get_bookmarks`
  were collapsed into a single check.
- Internal state in `utils.py` moved from module-level globals
  into a small `_LinkHutThrottle` class so the rate-limiter state
  has a clear home.

### Removed

- None.

### Documentation

- `CHANGELOG.md` introduced at the repo root.
- README rewritten around the actual public API (the previous
  README documented a non-existent `LinkhutLib` class).

### Known gaps

The following endpoints are documented at <https://docs.linkhut.org/>
but not yet wrapped by `linkhut-lib` 0.1.0. Call them directly with
`httpx.Client` if you need them:

- `GET /v1/tags/get` — list all tags with usage counts.
- `GET /v1/posts/dates` — list dates with bookmark counts (optionally
  filtered by a single tag).
- `GET /v1/posts/all` — paginated bulk fetch with `start`, `results`,
  `fromdt`, `todt`.
- `GET /v1/posts/update` — last-update timestamp for incremental
  sync.
- `hashes` parameter on `GET /v1/posts/get` — fetch by MD5 hashes
  joined with `+`.
- `dt` parameter on `POST /v1/posts/add` — set the bookmark
  timestamp on create.