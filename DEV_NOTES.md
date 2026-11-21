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
   - later, once Phase 1 adds the selector, one ebook search.
3. Optional: an auth-failure capture. One way is to wait until the cookie expires naturally and run a search. Another is to temporarily paste a junk cookie in Setup and run one search. Only do this if you're comfortable sending one request with an invalid cookie.
4. Open the files in `<DATA_DIR>/fixtures/` and check them before sharing. They contain titles and your own `my_snatched`/`bookmarked` flags, but no cookie or real `dl` hash.
5. Copy them into `tests/fixtures/` in the repo, then remove `MAM_CAPTURE_DIR`.

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
  - `docker build -t ghcr.io/raygan/mam-audiofinder:0.6 -t ghcr.io/raygan/mam-audiofinder:latest .`
- Login to GHCR (once per machine):
  - `echo "$GHCR_PAT" | docker login ghcr.io -u raygan --password-stdin`
- Push tags:
  - `docker push ghcr.io/raygan/mam-audiofinder:0.6`
  - `docker push ghcr.io/raygan/mam-audiofinder:latest`
- Consumers update via:
  - `docker compose pull && docker compose up -d`

## Possible Next Steps

- Add a “Test qB connection” button on the setup page (hit `/api/v2/app/version`).
- Improve error messages when `map_qb_path` cannot resolve a path.
- Add a minimal `pytest` suite that mocks MAM/qB and exercises `/health`, `/search`, `/add`, `/qb/torrents`, and `/import` using a temp `/data` directory.
- Investigate adding real time download status for recently added torrents
- Investigate displaying artwork. Available via MAM API?
