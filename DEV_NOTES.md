# Dev Notes – mam-audiofinder (0.6-testing)

Branch: `0.6-testing`  
Purpose: make the app easier to run on diverse self‑hosted setups via explicit path mapping and a first‑run setup wizard.

## Key Changes Implemented

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
  - `GET /` serves `setup.html` if `needs_setup()` (no cookie, no lib dir, or no path map).
  - `GET /setup` always shows the wizard.
  - `POST /api/setup` writes `/data/config.json` and calls `settings.reload()`.
  - UI files: `app/templates/setup.html`, `app/static/setup.js`.
- Root‑level `AGENTS.md` documents repo conventions and agent guidance.

## How to Run for Testing

- Local dev (no Docker), from `app/`:
  - `uvicorn main:app --reload --host 0.0.0.0 --port 8080`
  - Optionally set `APP_CONFIG_PATH=../dev-config.json` to avoid writing into `/data`.
- Docker (on Unraid or similar):
  - Update `.env` for mounts and ports, then `docker compose up -d`.
  - First visit to `/` should trigger the setup wizard.

## Possible Next Steps

- Add a “Test qB connection” button on the setup page (hit `/api/v2/app/version`).
- Improve error messages when `map_qb_path` cannot resolve a path.
- Document `QB_PATH_MAP` usage more prominently in `README.md`.

