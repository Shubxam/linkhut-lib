# TODO — linkhut-lib architecture review follow-ups

Generated from the architecture review of `linkhut-lib`. Items are grouped by
category and prioritized within each. **Do the P0 items before tagging `0.1.0`.**

> **0.1.0 progress:** P0 items complete. P1 API-correctness, build-config,
> and CHANGELOG items complete (2026-06-21). §2 P1 tests for the seven
> public functions landed on 2026-06-27 — see §2 for the new test files
> and §8 for the typed-result shapes and patterns those tests build on.

Priority legend:

- **P0** — Release-blocker. The current pre-release shape cannot ship
  to PyPI in this state.
- **P1** — Trust-blocker. New users will hit these within their first session
  and lose confidence.
- **P2** — Quality. The library works but the smell will rot if left.
- **P3** — Polish. Worth doing but not urgent.

---

## 1. Public API correctness

The interface users actually touch. Get this right before anything else.

- [x] **[P0] Fix README to match actual public API.** README shows
      `from linkhut_lib import LinkhutLib; client = LinkhutLib()` but no such
      class exists. The real API is module-level functions (`create_bookmark`,
      `get_bookmarks`, `update_bookmark`, `delete_bookmark`, `get_reading_list`,
      `rename_tag`, `delete_tag`) plus model classes (`Bookmark`, `Tag`, `Date`,
      `Url`, `APIResponse`, `HTMLResponse`). Either re-introduce a thin
      `LinkhutLib` class or rewrite the README with a real example.
      *Why:* the README is the first thing new users see; copy-paste failure
      means a 30-second abandonment. 15-minute fix.

- [x] **[P1] Split `update_bookmark` into strict + upsert variants.**
      `update_bookmark` silently creates a new bookmark if the URL isn't found
      (`linkhut_lib.py:189-297`). A typo'd URL creates a bookmark instead of
      raising. Split into:
      - `update_bookmark(url, ...)` — strict, raises `BookmarkNotFoundError`
        if missing.
      - `upsert_bookmark(url, ...)` — creates if missing (current behavior).
      *Why:* implicit create-on-update is a footgun; the function is two
      behaviors glued together.
      *Done 2026-06-21.* `update_bookmark` is now strict;
      `upsert_bookmark` holds the create-on-missing behavior. Both return
      `BookmarkUpdateResult` (see §8).

- [x] **[P1] Make `create_bookmark` / `update_bookmark` return a consistent
      typed result.** `create_bookmark` returns the outbound payload dict;
      `update_bookmark` returns `fetched_bookmark` (server data) in the no-op
      case and `create_bookmark`'s return in the success case — two different
      shapes from one function. Pick one return type and stick to it.
      Candidate: a typed `CreateResult` carrying `result_code` plus normalized
      fields, or a `Bookmark` model.
      *Why:* public API is a contract; users shouldn't get different shapes
      from the same function.
      *Done 2026-06-21.* New typed results:
      `BookmarkCreateResult` (`outcome: CreateOutcome`, `url`, `bookmark`) and
      `BookmarkUpdateResult` (`outcome: UpdateOutcome`, `url`, `bookmark`).
      See §8 for the exact shapes.

- [x] **[P1] Resolve the `tag` overload in `get_bookmarks`.** `tag` is
      documented as "filter by tags" but in the `count > 0` branch it silently
      takes only the first tag (`linkhut_lib.py:67-70`). Either:
      1. Type it as `tag: str | list[str] = ''` and document the multi-tag
         behavior per endpoint, or
      2. Add a separate `get_recent_bookmarks(count, tag=None)` function.
      *Why:* users pass `tag='python,rust'` and silently get only `python`
      results. Small UX trap.
      *Done 2026-06-21.* Went with option 1: `tag: str | list[str]`. For
      `count > 0`, multi-element lists raise `ValueError`; for `count == 0`,
      the list is joined with `+` to AND-filter (per the LinkHut docs at
      https://docs.linkhut.org/posts.html).
      *Extra wins while in the area:* added strict `dt` format validation
      (`CCYY-MM-DDThh:mm:ssZ`, literal T and Z) via `validation.validate_dt_strict`,
      and clamped `count` to 1..100 on the recent endpoint. Both match the
      documented wire format and previously could surface as server-side
      errors with no client-side guard.

- [ ] **[P2] Fix `Bookmark.model_dump` serialization to flatten `Url` and
      `Date`.** Right now `model_dump(by_alias=True, mode='json')` produces a
      nested dict (`{'href': {'url': '...'}, 'time': {'date': '...'}}`) but the
      LinkHut wire format is flat (`{'href': '...', 'time': '...'}`). Add
      `model_serializer`s on `Url` and `Date` so round-trip
      `model_validate(model_dump_json())` equals the original model.

- [ ] **[P2] Make `update_bookmark` no-op branch return the same shape as the
      success branch.** Even before the §3 split, the no-op `return
      fetched_bookmark` returns a different shape than the create-fallback path.

---

## 2. Test coverage

`tests/test_smoke.py` covers etiquette, validation helpers, and the pydantic
round-trip. As of 2026-06-27 the seven public functions each have a
dedicated test module (`tests/test_<name>.py`) using the
`tests/_helpers.py` helpers (`patch_api_call`, `done_responder`,
`StatefulResponder`). The full pytest run is 91 tests, all green.

- [x] **[P1] Add `tests/test_create_bookmark.py`** — happy path, title
      auto-fetch, tag suggestion, replace=False (already-exists raises),
      replace=True, private/to_read flag handling.
      *Done 2026-06-27.*

- [x] **[P1] Add `tests/test_update_bookmark.py`** — strict variant (raises
      on missing), tag/note concatenation, replace flag behavior, no-op
      return.
      *Done 2026-06-27.*

- [x] **[P1] Add `tests/test_upsert_bookmark.py`** — separate file
      covering the create-on-update behavior that lives in
      `upsert_bookmark` since the §1.1 split.
      *Done 2026-06-27.*

- [x] **[P1] Add `tests/test_delete_bookmark.py`** — happy path, missing
      bookmark raises.
      *Done 2026-06-27.*

- [x] **[P1] Add `tests/test_get_bookmarks.py`** — recent endpoint, get
      endpoint with date/url/tag filters, default-no-args case,
      `something went wrong` result code mapping to
      `BookmarkNotFoundError`, `_result_code` helper for non-dict bodies.
      *Done 2026-06-27.*

- [x] **[P1] Add `tests/test_rename_tag.py`** and **`tests/test_delete_tag.py`** —
      happy path, invalid tag name raises `InvalidTagFormatError`,
      non-`done` result code raises `RequestError`.
      *Done 2026-06-27.*

- [x] **[P1] Add `tests/test_get_reading_list.py`** — wraps `get_bookmarks`
      with `tag='unread'`; covers the `BookmarkNotFoundError` re-raise
      path.
      *Done 2026-06-27.*

- [ ] **[P2] Add `tests/test_models.py`** — `Bookmark.validate_tags` four
      branches (string, list of strings, list of Tags, mixed raises);
      `Url`/`Date`/`Tag` `__str__` methods; `Bookmark.__str__`.

- [ ] **[P2] Add `tests/test_utils.py`** — `make_get_request` content-type
      dispatch (JSON, HTML, unknown raises), `linkhut_api_call` error
      when response is non-APIResponse, `get_link_meta` OG vs `<title>`
      fallback, `get_tags_suggestion` response parsing (popular and
      recommended buckets).

- [ ] **[P2] Add `tests/test_exceptions.py`** — `RequestError.__str__`
      with and without `status_code`; full exception hierarchy root.

---

## 3. Dead code & cleanup

Code that exists but shouldn't, or that exists twice.

- [ ] **[P2] Delete dead `LinkPreview` config in `config.py`.**
      `LINKPREVIEW_HEADER` and `LINKPREVIEW_BASEURL` are unused. Either wire
      them up or remove them.

- [ ] **[P2] Remove duplicate branch in `get_bookmarks`.**
      `linkhut_lib.py:122-128` — the `if result_code == ... or not
      fetched_bookmarks` branch and the trailing `if not fetched_bookmarks`
      branch do literally the same thing. Pick one.
      *Done 2026-06-21* as part of the §1.1/§1.2/§1.3 refactor — the two
      duplicate "no bookmarks" branches were collapsed into a single
      raise. Move this to "done" next time the file is cleaned up.

- [ ] **[P2] Remove the `# type: ignore` in `models.py:130`.** Replace with a
      call to the existing `validate_url_string` helper, or fix the `Url.url`
      annotation. The inconsistency (some call sites use the helper, one
      uses raw construction) is the smell.

- [ ] **[P2] Remove the `_validate_date` / `validate_date` shadow in
      `utils.py:40-44`.** Decide which module owns validation
      (`validation.py` is the right answer) and import normally.

- [ ] **[P2] Compute `_PACKAGE_VERSION` once, in one place.** It's currently
      computed in both `__init__.py:24-26` and `utils.py:51-53`. Import
      `__version__` from `__init__` in `utils.py`.

- [ ] **[P2] Move `version('linkhut-lib')` lookup into `_linkhut_client()`.**
      Right now it runs at module import time, triggering metadata lookup
      even for users who only want to import `Tag`. Use `lru_cache` to
      memoize.

- [ ] **[P2] Replace `ValueError`/`TypeError` in `validation.py:13-22` with
      `InvalidDateFormatError`.** The library already defines the right
      exception; the validation module raises stdlib types instead.
      *Partially done 2026-06-21.* `validate_date` now raises
      `InvalidDateFormatError` on string-parsing failures. The `TypeError`
      for the `else` branch was kept (it covers a real type-system error
      rather than a format error) and is now followed by an explicit
      `isinstance(..., datetime)` short-circuit that keeps ty happy without
      needing `# type: ignore`.

- [ ] **[P2] Remove `dotenv` as a runtime dep** *or* move `load_dotenv()`
      out of `_linkhut_client` into a separate
      `linkhut_lib.dev.configure()` entry point. `python-dotenv` is for dev
      convenience, not production. Production users are paying for a `.env`
      reader they don't need.

- [ ] **[P3] Add a comment in `utils.py` documenting the import-graph
      boundary.** This module is the bottom — no other module should import
      from it except `linkhut_lib.py`. Prevents future circular imports.

---

## 4. pyproject.toml / build config

- [x] **[P1] Reconcile `[project.optional-dependencies]` and
      `[dependency-groups]`.** Both define a `dev` group. Pick one. New uv
      style is `[dependency-groups]` (PEP 735). Move everything there and
      drop `optional-dependencies`.
      *Done 2026-06-21.* Deleted `[project.optional-dependencies]`; the
      `dev` group now lives in `[dependency-groups]`. The CI workflow's
      `uv sync --all-extras --dev --frozen` becomes `uv sync --dev --frozen`
      (no `optional-dependencies` left for `--all-extras` to surface). CI
      workflow file still calls `--all-extras`; harmless no-op but worth
      cleaning up.

- [x] **[P1] Drop `src` from `testpaths` in `[tool.pytest.ini_options]`.**
      `testpaths = ["src", "tests"]` causes pytest to scan production code.
      Tests live in `tests/`; remove `src`.
      *Done 2026-06-21.* `testpaths = ["tests"]`. Verified with
      `uv run pytest --collect-only` — collects 13 tests from `tests/`
      only.

- [x] **[P1] Fix `requires-python` vs classifiers mismatch.**
      `requires-python = ">=3.13"` but classifiers list `Python :: 3.11` and
      `Python :: 3.12`. Remove the unsupported versions from classifiers.
      *Done 2026-06-21.* Classifiers now list only 3.13 and 3.14, matching
      the CI matrix in `.github/workflows/ci.yml`.

- [ ] **[P2] Move ruff ignores for tests/devtools into
      `tool.ruff.lint.per-file-ignores` and verify the current
      per-file-ignores block is complete.** Some current ignores are at the
      top level but only meaningful in tests — flag for review.

---

## 5. OSS-credibility checklist

For a library to be considered "real" by the community. None of these block
the next release; all block "people who aren't you" trusting the project.

- [x] **[P0] Verify a `LICENSE` file exists at the repo root.** Pyproject
      says `license = "MIT"` and README says "see LICENSE file for details."
      Confirm the file is present; add it if not. Release-blocker.

- [x] **[P1] Add `CHANGELOG.md`** with an `## [Unreleased]` section. The
      publishing doc uses `gh release create --generate-notes` but a
      checked-in `CHANGELOG.md` is what PyPI renders and what contributors
      read first.
      *Done 2026-06-21.* `CHANGELOG.md` added at the repo root with
      `[Unreleased]` and `[0.1.0]` sections. The 0.1.0 entry spells out
      the breaking changes (`update_bookmark` strict, typed result shapes),
      the additions (`upsert_bookmark`, `validate_dt_strict`, etc.), and
      a "Known gaps" section listing documented-but-unwrapped endpoints
      (`/v1/tags/get`, `/v1/posts/dates`, `/v1/posts/all`, `/v1/posts/update`,
      `hashes` and `dt` parameters).

- [x] **[P1] Verify CI runs `ruff check` + `ruff format --check` +
      `codespell` + `ty check` + `pytest` + `uv build`** on Python 3.13 and
      3.14. The publishing doc says GitHub Actions call `uv` directly;
      confirm the matrix matches the classifiers in pyproject.
      *Done 2026-06-21.* CI workflow (`.github/workflows/ci.yml`) runs
      `devtools/lint.py --check` (which wraps ruff check + format check +
      codespell + ty) and `pytest` on the Python 3.13/3.14 matrix. Pyproject
      classifiers now match the matrix (3.13 + 3.14 only). One nit: the CI
      step still passes `--all-extras`, which became a no-op after §4.1.
      Not blocking.

- [ ] **[P2] Add an issue template and a PR template** under
      `.github/ISSUE_TEMPLATE/` and `.github/PULL_REQUEST_TEMPLATE.md`. Low
      effort, high signal.

- [ ] **[P2] Add a "Why this library?" paragraph to the README**
      distinguishing `linkhut-lib` from `pinboard-python`, raw `httpx`, or
      other bookmarking SDKs. New users want to know why they should pick
      yours.

- [ ] **[P2] Add a Code of Conduct.** Standard for community OSS projects.
      The Contributor Covenant is the default.

- [ ] **[P3] Set up versioned docs (mkdocs or similar).** The `docs/` folder
      is good but not built. Optional before 1.0; required if you want
      Read the Docs.

- [ ] **[P3] Cut a `0.1.0` release** once the P0/P1 items above are done.
      The version bump signals "first public release" and gives a clean
      semver boundary before introducing the optional `LinkhutLib` class.

---

## 6. Documentation gaps in existing files

- [ ] **[P2] Add a comment to `Bookmark.validate_tags` explaining the
      duplicate-stripping via `set()`.** The current behavior silently
      de-dupes tags; users who pass `['python', 'python']` get one back.
      Worth a one-line docstring note.

- [ ] **[P2] Add a comment to `_scrape_client`'s Firefox User-Agent**
      explaining the trade-off (Cloudflare blocks default httpx UA; not
      pretending to be a real user, just identifying as a non-default
      library).

- [ ] **[P2] Add a comment to `make_get_request`'s 500/999 retry** clarifying
      that "single retry is per etiquette; further throttling surfaces as
      `RequestError` so callers can decide whether to back off further."

- [ ] **[P2] Add a comment to `LinkHutEndpoint.TAG_SUGGEST`** noting it lives
      under `/v1/posts/`, not `/v1/tags/` — counterintuitive for a tag
      operation.

- [ ] **[P2] Fix `LinkHutEndpoint.BOOKMARK_CREATE` → `/v1/posts/add`
      naming mismatch.** Either rename to `BOOKMARK_ADD` to match the path,
      or document why the name and path differ.

- [ ] **[P3] Add module-level docstring to `validation.py`** explaining it's
      pure-function validation, no class state, designed to be unit-tested in
      isolation.

---

## 7. Sequencing suggestion

If you only have a few hours, here's the order:

1. **Verify `LICENSE` exists** — 1 minute, release-blocker.
2. **Fix README** — 15 minutes, unblocks new users.
3. **Split `update_bookmark`** + tests — 1 hour, removes the biggest
   API surprise.
4. **Add tests for the remaining 5 public functions** — 2 hours,
   dramatically improves trust.
5. **Fix the `Bookmark.model_dump` serialization** — 30 minutes, removes a
   round-trip footgun.

That's ~4 hours of focused work and gets you from "mid-refactor" to
"shippable 0.1.0." Everything else can land in 0.1.x point releases.

---

## 8. Implementation notes — 0.1.0 refactor (2026-06-21)

Captured so the next contributor doesn't have to re-derive these shapes from
reading the code. All of the below is what shipped in this session.

### Typed result models (replaces the old `dict` return)

`create_bookmark`, `update_bookmark`, and `upsert_bookmark` now return
typed pydantic models. All three live in `src/linkhut_lib/models.py`:

```python
class CreateOutcome(StrEnum):
    CREATED = 'created'             # new bookmark created
    REPLACED = 'replaced'           # existing bookmark replaced (replace=True)
    ALREADY_EXISTS = 'already_exists'  # raised in practice (replace=False + duplicate)

class UpdateOutcome(StrEnum):
    UPDATED = 'updated'             # strict: matched existing, fields written
    UPSERTED = 'upserted'           # upsert: did not exist, was created
    NO_OP = 'no_op'                 # server-state already matched

class BookmarkCreateResult(BaseModel):
    outcome: CreateOutcome
    url: str
    bookmark: dict[str, str]   # server-shape payload (matches get_bookmarks)

class BookmarkUpdateResult(BaseModel):
    outcome: UpdateOutcome
    url: str
    bookmark: dict[str, str]
```

Caller pattern:

```python
result = create_bookmark(url='https://example.com', tags='python,rust')
if result.outcome == CreateOutcome.CREATED:
    print(result.bookmark['href'])
```

### API split

- `update_bookmark(url, ...)` — strict; raises `BookmarkNotFoundError` if
  the URL isn't bookmarked. New default behavior; was the footgun.
- `upsert_bookmark(url, ...)` — creates if missing, updates if present.
  Pre-`linkhut-lib` behavior, kept under a clearer name.

Both are exported from `linkhut_lib` alongside the typed results.

### `get_bookmarks(tag=...)` typing

`tag: str | list[str] = ''`. Per-endpoint semantics:

- `count > 0` (`/v1/posts/recent`): single tag only. A multi-element list
  raises `ValueError`. A single-element list is unwrapped.
- `count == 0` (`/v1/posts/get`): the list is joined with `+` to AND-filter
  per https://docs.linkhut.org/posts.html.

### `get_bookmarks(dt=...)` strict format

`dt` must match `CCYY-MM-DDThh:mm:ssZ` (literal T separator, Z suffix).
`datetime.fromisoformat` is too permissive — it accepts `2025-01-01` with no
time component, which the API then rejects. New helper in
`validation.py`:

```python
def validate_dt_strict(value: str) -> datetime:
    """Raise InvalidDateFormatError if value isn't CCYY-MM-DDThh:mm:ssZ."""
```

### `get_bookmarks(count=...)` bounds

`count` is now clamped to 1..100 on the recent endpoint, matching the
documented bounds. Out-of-range raises `ValueError` before any HTTP call.

### pyproject.toml changes

- Dropped `[project.optional-dependencies]`. Dev deps live in
  `[dependency-groups].dev` (PEP 735). CI's `uv sync --all-extras --dev`
  becomes `uv sync --dev` (with `--all-extras` a no-op — not removed yet,
  see P3 nit in §5.1).
- `testpaths = ["tests"]` (was `["src", "tests"]`).
- Classifiers dropped to 3.13/3.14 only, matching the CI matrix.

### Test pattern for §2 follow-up

The `httpx.MockTransport` + `pytest.MonkeyPatch` pattern in
`tests/test_smoke.py:121-229` extends to every public function in 5-10
lines. Recommended template for the deferred P1 tests:

```python
class TestCreateBookmark:
    def test_happy_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('LH_PAT', 'test-token')
        utils._linkhut_client.cache_clear()
        utils._LINKHUT_THROTTLE._last_request_at = 0.0
        monkeypatch.setattr(utils.time, 'sleep', lambda _: None)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={'result_code': 'done'},
                headers={'content-type': 'application/json'},
            )

        transport = httpx.MockTransport(handler)
        # ... patch utils.linkhut_api_call to use transport ...
        result = create_bookmark(url='https://example.com', title='Example')
        assert result.outcome == CreateOutcome.CREATED
```

(For full mock-isolation without monkey-patching `utils` internals,
patch `linkhut_lib.linkhut_lib.utils.linkhut_api_call` with a `Mock` that
returns a pre-built `APIResponse`. That's how the etiquette tests reach
the transport without going through `utils.linkhut_api_call`.)

### Verification baseline (before §2 follow-up)

The 13 smoke tests in `tests/test_smoke.py` pass on the refactored code:

```bash
make lint-check   # codespell + ruff check + ruff format --check + ty
make test         # pytest
```

Both must stay green as §2 tests are added.

---

*Generated from the architecture review. See `docs/development.md` for the
broader workflow. 0.1.0 implementation notes appended on 2026-06-21.*