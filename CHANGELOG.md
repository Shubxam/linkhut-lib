# Changelog

All notable changes to linkhut-lib are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - YYYY-MM-DD

### Breaking changes

- **`update_bookmark` is now strict.** It raises `BookmarkNotFoundError`
  when the URL is not bookmarked. The previous implicit create-on-update
  behavior has moved to the new `upsert_bookmark` function. Update any
  call sites that relied on the silent create.
- **`create_bookmark` and `upsert_bookmark` return a typed result**
  (`BookmarkCreateResult` / `BookmarkUpdateResult`) instead of the
  outbound payload dict. The result exposes `.outcome` (a `CreateOutcome`
  or `UpdateOutcome` enum), `.url`, and `.bookmark` (the server-shape
  dict). To get the same shape the previous code returned, read
  `result.bookmark`.

### Added

- **`upsert_bookmark(url, ...)`** — like `update_bookmark`, but creates
  the bookmark if the URL isn't already saved. This is the pre-0.2.0
  behavior, extracted so the strict path is the default.
- **`BookmarkCreateResult`** / **`BookmarkUpdateResult`** — typed result
  models for the bookmark write paths.
- **`CreateOutcome`** / **`UpdateOutcome`** enums — discriminator values
  on the typed results.
- **`get_bookmarks(tag=...)` accepts `str | list[str]`.** For
  `count > 0` (recent endpoint), only a single tag is allowed; a
  multi-element list raises `ValueError`. For `count == 0` (get
  endpoint), a list is joined with `+` to AND-filter.
- **`get_bookmarks` now enforces the documented wire format for `dt`.**
  Strings must match `CCYY-MM-DDThh:mm:ssZ` (literal T separator, Z
  suffix). Anything else raises `InvalidDateFormatError` before the API
  call.
- **`get_bookmarks` now clamps `count` to 1..100** on the recent
  endpoint, matching the documented bounds at
  https://docs.linkhut.org/posts.html. Out-of-range values raise
  `ValueError`.

### Changed

- The duplicate "no bookmarks found" branches in `get_bookmarks` were
  collapsed into a single check.

### Removed

- `[project.optional-dependencies]` from `pyproject.toml`. Dev tooling
  now lives exclusively in `[dependency-groups]` (PEP 735). The `dev`
  group contents are unchanged; CI's `uv sync --dev` invocation picks
  them up the same way.

### Documentation

- `CHANGELOG.md` introduced at the repo root.

### Known gaps

The following endpoints are documented at https://docs.linkhut.org/ but
not yet wrapped by `linkhut-lib` 0.2.0. Call them directly with
`httpx.Client` if you need them:

- `GET /v1/tags/get` — list all tags with usage counts.
- `GET /v1/posts/dates` — list dates with bookmark counts (optionally
  filtered by a single tag).
- `GET /v1/posts/all` — paginated bulk fetch with `start`, `results`,
  `fromdt`, `todt`.
- `GET /v1/posts/update` — last-update timestamp for incremental sync.
- `hashes` parameter on `GET /v1/posts/get` — fetch by MD5 hashes joined
  with `+`.
- `dt` parameter on `POST /v1/posts/add` — set the bookmark timestamp on
  create.

## [0.1.x]

Initial release. See git history for details.