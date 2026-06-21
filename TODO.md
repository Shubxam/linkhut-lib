# TODO — linkhut-lib architecture review follow-ups

Generated from the architecture review of `linkhut-lib`. Items are grouped by
category and prioritized within each. **Do the P0 items before tagging `0.2.0`.**

Priority legend:

- **P0** — Release-blocker. The current `0.1.x` shape cannot ship to PyPI in
  this state.
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

- [ ] **[P1] Split `update_bookmark` into strict + upsert variants.**
      `update_bookmark` silently creates a new bookmark if the URL isn't found
      (`linkhut_lib.py:189-297`). A typo'd URL creates a bookmark instead of
      raising. Split into:
      - `update_bookmark(url, ...)` — strict, raises `BookmarkNotFoundError`
        if missing.
      - `upsert_bookmark(url, ...)` — creates if missing (current behavior).
      *Why:* implicit create-on-update is a footgun; the function is two
      behaviors glued together.

- [ ] **[P1] Make `create_bookmark` / `update_bookmark` return a consistent
      typed result.** `create_bookmark` returns the outbound payload dict;
      `update_bookmark` returns `fetched_bookmark` (server data) in the no-op
      case and `create_bookmark`'s return in the success case — two different
      shapes from one function. Pick one return type and stick to it.
      Candidate: a typed `CreateResult` carrying `result_code` plus normalized
      fields, or a `Bookmark` model.
      *Why:* public API is a contract; users shouldn't get different shapes
      from the same function.

- [ ] **[P1] Resolve the `tag` overload in `get_bookmarks`.** `tag` is
      documented as "filter by tags" but in the `count > 0` branch it silently
      takes only the first tag (`linkhut_lib.py:67-70`). Either:
      1. Type it as `tag: str | list[str] = ''` and document the multi-tag
         behavior per endpoint, or
      2. Add a separate `get_recent_bookmarks(count, tag=None)` function.
      *Why:* users pass `tag='python,rust'` and silently get only `python`
      results. Small UX trap.

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
round-trip — but **none of the seven public functions**. The httpx
`MockTransport` pattern in the etiquette tests extends to every function in
5-10 lines each.

- [ ] **[P1] Add `tests/test_create_bookmark.py`** — happy path, title
      auto-fetch, tag suggestion, replace=False (already-exists raises),
      replace=True, private/to_read flag handling.

- [ ] **[P1] Add `tests/test_update_bookmark.py`** — strict variant (raises
      on missing), upsert variant (creates on missing), tag/note
      concatenation, replace flag behavior, no-op return.

- [ ] **[P1] Add `tests/test_delete_bookmark.py`** — happy path, missing
      bookmark raises.

- [ ] **[P1] Add `tests/test_get_bookmarks.py`** — recent endpoint, get
      endpoint with date/url/tag filters, default-no-args case,
      `something went wrong` result code mapping to
      `BookmarkNotFoundError`, `_result_code` helper for non-dict bodies.

- [ ] **[P1] Add `tests/test_rename_tag.py`** and **`tests/test_delete_tag.py`** —
      happy path, invalid tag name raises `InvalidTagFormatError`,
      non-`done` result code raises `RequestError`.

- [ ] **[P1] Add `tests/test_get_reading_list.py`** — wraps `get_bookmarks`
      with `tag='unread'`; covers the `BookmarkNotFoundError` re-raise
      path (`linkhut_lib.py:339-348`).

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

- [ ] **[P1] Reconcile `[project.optional-dependencies]` and
      `[dependency-groups]`.** Both define a `dev` group. Pick one. New uv
      style is `[dependency-groups]` (PEP 735). Move everything there and
      drop `optional-dependencies`.

- [ ] **[P1] Drop `src` from `testpaths` in `[tool.pytest.ini_options]`.**
      `testpaths = ["src", "tests"]` causes pytest to scan production code.
      Tests live in `tests/`; remove `src`.

- [ ] **[P1] Fix `requires-python` vs classifiers mismatch.**
      `requires-python = ">=3.13"` but classifiers list `Python :: 3.11` and
      `Python :: 3.12`. Remove the unsupported versions from classifiers.

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

- [ ] **[P1] Add `CHANGELOG.md`** with an `## [Unreleased]` section. The
      publishing doc uses `gh release create --generate-notes` but a
      checked-in `CHANGELOG.md` is what PyPI renders and what contributors
      read first.

- [ ] **[P1] Verify CI runs `ruff check` + `ruff format --check` +
      `codespell` + `ty check` + `pytest` + `uv build`** on Python 3.13 and
      3.14. The publishing doc says GitHub Actions call `uv` directly;
      confirm the matrix matches the classifiers in pyproject.

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

- [ ] **[P3] Cut a `0.2.0` release** once the P0/P1 items above are done.
      The version bump signals "API changed" and gives you a clean semver
      boundary before introducing the optional `LinkhutLib` class.

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
"shippable 0.2.0." Everything else can land in 0.2.x point releases.

---

*Generated from the architecture review. See `docs/development.md` for the
broader workflow.*