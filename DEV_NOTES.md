# Dev Notes – mam-audiofinder

## Recent Key Changes Implemented

- Added a `Settings` helper in `app/main.py`:
  - Loads config from `/data/config.json` (or `APP_CONFIG_PATH`) and falls back to env vars.
  - Centralizes: `MAM_COOKIE`, `QB_URL`, `QB_USER`, `QB_PASS`, `DL_DIR`, `LIB_DIR`, `IMPORT_MODE`, `QB_INNER_DL_PREFIX`, `QB_PATH_MAP`, etc.
- Introduced explicit qB → app path mapping:
  - `settings.QB_PATH_MAP` is a list of `(qb_prefix, app_prefix)` pairs.
  - Populated from:
    - JSON config key `QB_PATH_MAP` (list of objects with `qb_prefix` / `app_prefix`), or
    - Env `QB_PATH_MAP="qb=/path;qb2=/path2"`, or
    - Fallback: `QB_INNER_DL_PREFIX` → `DL_DIR`.
  - `do_import` now uses this mapping in `map_qb_path`, with legacy Unraid heuristics left as secondary fallbacks.
- Added a first‑run setup wizard:
  - `GET /` serves `setup.html` if `needs_setup()` (no cookie, no lib dir, or no path map) and setup is not disabled via env.
  - `GET /setup` shows the wizard unless `DISABLE_SETUP` is set (then it returns 404).
  - `POST /api/setup` writes `/data/config.json` and calls `settings.reload()`.
  - UI files: `app/templates/setup.html`, `app/static/setup.js`.
- Setup UX tweaks:
  - Main page includes a “Setup / Configuration” button (hidden when `DISABLE_SETUP` is enabled).
  - The setup page title links back to `/`.
- Root‑level `AGENTS.md` documents repo conventions and agent guidance.

## Phase 0a (v0.7.0): MAM compliance

- New `app/mam.py` is the only module that talks to MAM. Its allowlist guard enforces `docs/MAM_API_ALLOWLIST.md`. Mapping: `docs/MAM_COMPLIANCE.md`.
- It sends an honest `User-Agent: mam-audiofinder/<version>` and no `Origin`/`Referer`. It sends only the `mam_id` cookie.
- `MAM_BASE` was removed (it's ignored with a warning if set).
- Downloads: qB gets `download.php/<dl>?tid=<id>`; with no `dl`, the app makes one cookie GET of `download.php?tid=<id>`. The `?id=` fallback is gone, and if qB rejects the URL there's no fallback.
- New env vars, internal and not user-facing: `APP_DB_PATH` (default `/data/history.db`, used by tests), and `MAM_CAPTURE_DIR` (fixture capture, below).

### Capturing sanitized MAM fixtures (Raygan only)

The tests need real response shapes. With `MAM_CAPTURE_DIR` set, the app writes a sanitized copy of each MAM response from a normal, user-initiated search or add. `dl` hashes become same-shape dummies (e.g. `AAaa00`), `owner`/`owner_name` are blanked, `Set-Cookie` isn't stored, and HTML bodies are never stored. It makes no extra requests. It's off by default; unset it when you're done.

1. Add `MAM_CAPTURE_DIR=/data/fixtures` to `.env` (or the container env) and restart.
2. In the web UI, do these searches yourself:
   - one audiobook search that returns results,
   - one search that returns nothing (e.g. `zzqqxxnotabook`),
   - one ebook search, and one Both search.
3. Optional: an auth-failure capture. One way is to wait until the cookie expires naturally and run a search. Another is to temporarily paste a junk cookie in Setup and run one search. Only do this if you're comfortable sending one request with an invalid cookie.
4. Open the files in `<DATA_DIR>/fixtures/` and check them before sharing. They contain titles and your own `my_snatched`/`bookmarked` flags, but no cookie or real `dl` hash.
5. Copy them into `tests/fixtures/` in the repo, then remove `MAM_CAPTURE_DIR`.

## Phase 0b (v0.7.0): groundwork

- `main.py` is split into `config.py`, `db.py`, `qb.py` and `importer.py`; `main.py` keeps the routes (see AGENTS.md). Behaviour is unchanged, and the Import tests were written before the move to prove it.
- `qb.add_from_mam(mam_id, dl, title)` is the single path for adding a MAM torrent to qB.
- `/import` is now async. qB calls are async, and file copying runs in a threadpool so it doesn't block the server. It no longer fetches the unused torrent properties.
- Versioned migrations: a `schema_version` table and `db.MIGRATIONS`. Migration 1 brings any older DB up to the v0.6 columns without touching rows; migration 2 indexes `history.mam_id`. They run on startup. **Back up `history.db` before the first start of 0.7.**
- Housekeeping: all timestamps are timezone-aware UTC (`db.utc_now()`), the double `r.json()` in `/qb/torrents` is gone, and history inserts go through one helper.
- Still open: see "Known gaps" in `docs/MAM_COMPLIANCE.md` (missing `dl` hash TODO, auth-failure fixture, `dl` character set).

## Phase 1 (v0.8.0): ebooks

- **Search:** an Audiobooks / Ebooks / Both selector (remembered per browser) maps to `main_cat` 13 / 14 / both in one request. Ebooks search title, author and series. Results carry `media_type`, `series`, and a `group` key.
- **Grouping** (`mam.group_key`): same media type, author ids and series id + number (or normalised title), plus narrator ids for audiobooks. The browser shows one row per book, with other versions behind a toggle.
- **qB:** `QB_CATEGORY_AUDIO`/`_EBOOK` and `QB_POSTIMPORT_CATEGORY_AUDIO`/`_EBOOK`, with the audio keys falling back to the pre-0.8 names. `QB_TAGS` defaults to `MAM`, and the `audiobook`/`ebook` tag is added per torrent.
- **History:** migration 3 adds `media_type`. `/import` routes by the History row, not the browser.
- **Ebook import** (`importer.ebook_choices` / `import_ebooks`): the user ticks formats per book. Files are always copied (never linked or moved), flat into `EBOOK_INGEST_DIR` via a hidden `.partial` and a rename. Every chosen path is validated before anything is copied.
- **Ingest folder:** `importer.ingest_dir_problem`. The Setup save and startup do a real write test; `/health` reports `ebook_ingest` without writing.
- **Real captures** now in `tests/fixtures/`: `search_audiobook.json`, `search_both.json`, `search_empty.json`.
- **Findings from real responses:** `dlLink` must be in the JSON body. `dl` is `<hash>?tid=<id>`. The count field is `found`. Newer qB returns 204 for login, 202 for a pending URL add and 409 for a duplicate. `my_snatched` lags by a few minutes.

## How to Run for Testing

- Tests (no network): `python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt`, then `.venv/bin/python -m pytest -q`.

- Local dev (no Docker), from `app/`:
  - `uvicorn main:app --reload --host 0.0.0.0 --port 8080`
  - Optionally set `APP_CONFIG_PATH=../dev-config.json` to avoid writing into `/data`.
- Docker (on Unraid or similar):
  - Update `.env` for mounts and ports, then `docker compose up -d`.
  - First visit to `/` on a fresh data directory should trigger the setup wizard (unless `DISABLE_SETUP` is set).

## Release Notes / Checklist (GHCR)

- Build and tag image from repo root:
  - `docker build -t ghcr.io/raygan/mam-audiofinder:<version> -t ghcr.io/raygan/mam-audiofinder:latest .`
- Login to GHCR (once per machine):
  - `echo "$GHCR_PAT" | docker login ghcr.io -u raygan --password-stdin`
- Push tags:
  - `docker push ghcr.io/raygan/mam-audiofinder:<version>`
  - `docker push ghcr.io/raygan/mam-audiofinder:latest`
- Consumers update via:
  - `docker compose pull && docker compose up -d`

## Possible Next Steps

- Add a “Test qB connection” button on the setup page (hit `/api/v2/app/version`).
- Improve error messages when `map_qb_path` cannot resolve a path.
- Add a minimal `pytest` suite that mocks MAM/qB and exercises `/health`, `/search`, `/add`, `/qb/torrents`, and `/import` using a temp `/data` directory.
- Investigate adding real time download status for recently added torrents
- Investigate displaying artwork. Available via MAM API?
