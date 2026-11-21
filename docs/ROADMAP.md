# mam-audiofinder — Expansion Brief

Brief for Claude Code. Read this whole document, then `AGENTS.md` and `DEV_NOTES.md`, before writing any code.

---

## ⚠️ MAM rules come first — read before anything else

MyAnonamouse rule **1.7 Bots, Automation, and Scraping** (updated 2026-10-07) governs everything in this project. A violation can get Raygan's account restricted or disabled, and he is responsible for anything done under his account, intended or not. **If any requirement in this brief conflicts with the rules, the rules win.** In that case, stop and ask; don't look for a workaround.

What the rule says, in summary (full text in `docs/MAM_RULES.md`; allowed endpoints in `docs/MAM_API_ALLOWLIST.md`):

- Only site functions **listed in MAM's API Documentation** (`/api/list.php`) or **approved by site administrators** may be automated. This applies to every kind of automation: bots, scripts, user scripts, AI assistants, browser agents, LLM tools.
- **No scraping** of site content, and no re-displaying or re-skinning the site.
- Approved tools authenticate **only with a `mam_id` cookie** generated in Preferences → Security. **Never** use a login with email/password: no automated, headless or CLI login, and no stored credentials.
- Login credentials must never be given to any human or AI tool.
- MAM does not recommend or support AI assistants or LLM tools. If they're used, the account owner bears full responsibility.

### Non-negotiable rules for this codebase

1. **Allowlist of MAM endpoints and parameters.** All MAM HTTP traffic goes through one module (`mam.py`). It may call only the endpoints **and parameters** listed in `docs/MAM_API_ALLOWLIST.md`, which Raygan filled in from the API Documentation. Currently that's two endpoints: the JSON search and the torrent download. Any request to an unlisted URL, or with an unlisted parameter, must raise `MamEndpointNotAllowed` and not be sent. Add a test that enforces this.
   - **The `fl` parameter on `download.php` must never be sent.** It spends a freeleech wedge, even on VIP torrents, with no refunds. The guard rejects any download URL containing it. The scheduler, auto-grab and any MCP tool can never set it.
2. **No HTML from MAM, ever.** Never fetch or parse MAM HTML pages. Use only documented JSON endpoints and documented `.torrent` download URLs. Links to MAM pages in the UI (e.g. `/t/<id>`) are fine: the user's own browser opens them; the app never fetches them.
3. **Cookie-only auth.** The only credential is the user-supplied `mam_id` cookie. No username/password fields, login flows, session refresh by login, or browser automation, ever.
4. **Honest client identity.** Stop sending a spoofed browser `User-Agent` and fake `Origin`/`Referer` headers (current code does this; see Phase 0). Send an honest UA such as `mam-audiofinder/<version>`, unless the API Documentation specifies different headers. If the documented endpoints require something specific, follow the docs exactly.
5. **Respect documented limits.** Apply any rate limit or frequency guidance in the API Documentation. Where none is documented, keep unattended traffic minimal (see the scheduler limits in Phase 1) and err on the side of fewer requests.
6. **Fail closed.** On auth failure, unexpected status codes, or anything resembling a block or rate-limit response, stop all automated MAM activity and notify the user. Never retry aggressively and never try alternative endpoints as a fallback.
7. **Scheduled searching is opt-in and conservative.** The search endpoint is listed in the API Documentation, so automating it falls within rule 1.7, but no rate limits are documented. The wishlist scheduler (Phase 2) therefore ships **disabled by default** (`WISHLIST_SCHEDULER_ENABLED=false`), so every user of the public repo has to turn it on deliberately. It also uses the conservative limits in Phase 2. If MAM publishes rate limits later, add them to the allowlist doc and apply whichever limit is lower.

### Rules for Claude Code during development

- **Claude Code must never contact MyAnonamouse in any way**: no `curl`, no fetch tool, no browser, no "quick test". Do not open the API Documentation page yourself; work from `docs/MAM_API_ALLOWLIST.md`.
- **Never read, print, request, or handle the MAM cookie** or the contents of `.env` / `/data/config.json`. Don't ask Raygan to paste them. Never put real cookie values in code, tests, fixtures, logs or commit messages.
- All MAM behaviour is developed and tested against **sanitized fixtures** that Raygan captures himself. If a fixture is missing, ask for it; don't guess at response shapes beyond what's documented.
- Logging must redact the cookie and any `dl` hashes or passkeys.
- Any real-world test against MAM is run **by Raygan, manually**, after he has reviewed the code path.

---

## Why

mam-audiofinder is replacing Shelfmark as the primary tool for MAM downloads. It already does what Shelfmark gets wrong: it searches MAM with the user's raw text and takes metadata from MAM itself, so if a result appears it is downloadable and accurate. There is no metadata-first step, and that must stay true.

Two things are missing:

1. **Memory.** A search that finds nothing today is lost. The core addition is a **wishlist of saved MAM searches** that are re-checked periodically, within MAM's rules.
2. **Ebooks.** The app currently searches only Audiobooks. It should also find **ebooks** on MAM and import them into **Grimmory's ingest folder**, alongside the existing audiobook → Audiobookshelf flow.

## Guiding principles (keep these)

- **MAM rules first** (above).
- **MAM-first, metadata-never-first.** A wishlist item is a saved MAM query, not a book record from Audible/Hardcover/etc. No external metadata lookups.
- **Fast and phone-friendly.** The search page stays as fast as it is now. New features live on their own views.
- **One container.** No new services. Scheduling runs in-process; state stays in `/data/history.db` + `/data/config.json`.
- **Minimal dependencies.** Prefer stdlib/asyncio; justify any addition in `requirements.txt` per `AGENTS.md`.

## Current state (as of Dec 2025, v0.6)

- Single FastAPI app, `app/main.py` (~680 lines), vanilla JS front end, Jinja templates.
- Endpoints: `/search`, `/add`, `/history`, `DELETE /history/{id}`, `/qb/torrents`, `/import`, `/setup`, `/api/setup`, `/health`.
- MAM calls today, checked against the allowlist:
  - `POST /tor/js/loadSearchJSONbasic.php?dlLink=1`, hard-coded to `main_cat: ["13"]` (Audiobooks). ✅ Documented; all `tor` keys sent are documented.
  - `/tor/download.php/<dl>` passed to qB as a URL. ⚠️ Documented form requires **`?tid=<id>` appended**; the current code omits it.
  - Fallback: cookie-authenticated `GET /tor/download.php?id=<id>`, then `?tid=<id>`. ❌ `?id=` is **not documented**; only `?tid=` is.
  - Both calls send `User-Agent: Mozilla/5.0` plus `Origin`/`Referer` set to the MAM site. ❌ Browser impersonation; replace with an honest UA.
- SQLite `history` table, no uniqueness on `mam_id`. No auth (it sits behind Tailscale / Cloudflare Access). No tests.

## Phase 0 — Compliance audit and groundwork (do first)

### 0a. Compliance audit (blocking)

1. `docs/MAM_API_ALLOWLIST.md` and `docs/MAM_RULES.md` already exist; Raygan supplied them. Treat the allowlist as the spec for `mam.py`. Don't add to it; if something's missing, ask.
2. Implement the endpoint+parameter allowlist guard in `mam.py` (rule 1), including the hard block on `fl`, and the honest-UA change (rule 4). Remove the browser-spoofing headers.
3. **Fix downloads to use only the documented forms:**
   - Primary: hand qB the documented cookie-less URL `https://www.myanonamouse.net/tor/download.php/<dl>?tid=<id>`. The `?tid=` is currently missing.
   - Fallback, only if no `dl` hash is available: one cookie-authenticated `GET /tor/download.php?tid=<id>` and upload the bytes to qB.
   - Delete the `?id=` attempt. No other fallbacks.
   - Keep the MAM base URL fixed to `https://www.myanonamouse.net`; drop the configurable `MAM_BASE` (or validate it equals that host), so a misconfiguration can't send the cookie elsewhere.
4. Handle documented field-name quirks defensively: `title` vs `name`, `filetypes` vs `filetype`, and numbers and booleans delivered as strings.
5. Add `docs/MAM_COMPLIANCE.md`: a short checklist mapping each rule above to where the code enforces it (module, function, test). Update it in every phase.
6. Add a compliance section to `AGENTS.md` that points to this brief and `docs/MAM_COMPLIANCE.md`, so any future agent sees it first.
7. Update `README.md` with a plain statement: the app uses only documented MAM API endpoints with a `mam_id` cookie, never credentials; users are responsible for their own accounts under MAM rule 1.7.

Phase 0a is done when every MAM request in the codebase passes through the guard and the tests prove that unlisted endpoints, unlisted params, and `fl` are all rejected.

### 0b. Groundwork

1. **Light module split.** Split into flat modules inside `app/`: `config.py`, `mam.py` (the only place MAM traffic happens), `qb.py`, `db.py`, `importer.py`, `wishlist.py`, `scheduler.py`, with `main.py` keeping routes. This is a deliberate exception to the "prefer helpers in main.py" line in `AGENTS.md`; update `AGENTS.md` to say so.
2. **Reusable functions.** `mam.search(...)` and `qb.add_from_mam(...)`, used by both the HTTP routes and the scheduler.
3. **Explicit error types.** `MamAuthError`, `MamRateLimitError`, `MamUnexpectedResponse`, `MamEndpointNotAllowed`. The scheduler relies on these to fail closed.
4. **Versioned schema migrations.** Use a `schema_version` table plus ordered SQL steps, replacing the try/except `ALTER TABLE` pattern. No Alembic.
5. **Test scaffold.** Use `pytest` with httpx `MockTransport` (or `respx`), fixtures only. Cover `/health`, `/search`, `/add`, the allowlist guard, and log redaction. Raygan provides sanitized search-response fixtures (one audiobook search, one ebook search, one auth-failure response) so the available fields can be inspected before designing filters.
6. **Housekeeping.** Replace `datetime.utcnow()` with timezone-aware UTC. Merge the duplicated history `INSERT` blocks into one helper. Fix the double `r.json()` in `qb_torrents`. Index `history.mam_id`.

## Phase 1 — Ebooks

### Search

- Add a media selector to the search form: **Audiobooks / Ebooks / Both** (default Audiobooks, remembered in `localStorage`, wrapped in try/catch).
- Map the selection to documented `main_cat` IDs: **`13` AudioBooks, `14` E-Books**. "Both" sends `["13","14"]` in one request, since `main_cat` is documented as an array.
- For ebooks, default `srchIn` to `title, author, series` (narrator is meaningless there).
- Results table shows a media-type badge. Format detection already recognises EPUB/PDF/MOBI/AZW3; prefer the format field documented in the API response over title-parsing.

### Download

- Separate qB categories per media type: `QB_CATEGORY_AUDIO` (default: the existing `mam-audiofinder`, for back-compat) and `QB_CATEGORY_EBOOK` (default `mam-audiofinder-ebooks`). Tags include `ebook` / `audiobook`.
- `history` gains a `media_type` column (`audiobook` | `ebook`), backfilled to `audiobook` for existing rows.

### Import to Grimmory

- New setting **`EBOOK_INGEST_DIR`**: the in-container path of Grimmory's ingest (BookDrop) folder. Add it to the setup page, `env.example`, the README, and both storage layout examples.
  - Raygan's host path: **`/mnt/user/media/Books/eBooks/bookdrop/`**. With the default single mount `MEDIA_ROOT=/mnt/user/media` → `/media`, that becomes **`EBOOK_INGEST_DIR=/media/Books/eBooks/bookdrop`**. Use this as the worked example in the README. Don't hard-code it (per `AGENTS.md`).
  - At startup and in setup, check that the directory exists and is writable by the container user (PUID 99 / PGID 100 on Unraid), and show a clear error if it isn't.
  - Write each file under a temporary name (e.g. `.partial`) in the ingest dir, then rename it into place, so Grimmory never picks up a half-copied file.
- Ebook import is **flat**: Grimmory ingests from the folder and does its own metadata and organisation, so drop the book file(s) directly into the ingest dir. Don't build Author/Title folders. Use `next_available`-style naming to avoid collisions.
- Copy only ebook files (`.epub .pdf .mobi .azw3 .azw .cbz .cbr .djvu .fb2`, configurable). Skip `.nfo`, `.txt`, images, `.cue`, etc. If a torrent holds several formats of one book, import according to a preference order (`EBOOK_FORMAT_PREFERENCE`, default `epub,azw3,mobi,pdf`), either the best one only or all of them (`EBOOK_IMPORT_ALL_FORMATS`, default false).
- **Copy, never hardlink or move, for ebooks** (`EBOOK_IMPORT_MODE`, default and recommended `copy`). Ingest tools commonly delete or rewrite files they process. A hardlinked file that gets rewritten (for example, metadata embedded into an EPUB) corrupts the seeding torrent, and a moved one stops seeding. MAM is ratio-based, so seeding integrity matters. Document this in the README.
- **Same caution for audiobooks:** document that `IMPORT_MODE=link` is only safe if Audiobookshelf is not set to embed metadata into files.
- The History/Import UI routes each completed torrent to the right importer by `media_type`. For ebooks it skips the Author/Title prompt, since Grimmory handles metadata.
- Post-import qB category change works as today, per media type (`QB_POSTIMPORT_CATEGORY_AUDIO` / `_EBOOK`).

### Acceptance criteria

- Searching "Ebooks" sends only the documented ebook category; "Both" sends both documented categories in a **single** request (if the API allows multiple categories in one request; otherwise ask).
- An ebook torrent with `book.epub`, `book.pdf`, `cover.jpg` and `info.nfo` results in exactly `book.epub` copied into the ingest folder by default.
- Ebook import never creates a hardlink, verified with a test that checks inode counts.
- Existing audiobook search/add/import behaviour is unchanged.

## Phase 2 — Wishlist

Built for both media types. **The scheduler ships disabled** until rule 7 is satisfied. Manual "check now" works regardless, because it's a user-initiated search.

### Data model

`wishlist` table:

| column | notes |
|---|---|
| `id` | PK |
| `query` | raw MAM search text, exactly as typed |
| `srch_in` | JSON list, default `["title","author","narrator"]` (for ebooks, a narrator search is meaningless; default to `["title","author"]`) |
| `media` | `audiobook`, `ebook`, or `both` |
| `label` | optional friendly name |
| `filters` | JSON (formats, min seeders, exclude terms…). Design it from the fields actually present in the fixtures/docs. |
| `mode` | `notify` (default) or `auto` |
| `status` | `active`, `matched`, `paused`, `done` |
| `created_at`, `last_checked_at`, `next_check_at`, `last_error` | scheduling + diagnostics |
| `check_interval_hours` | nullable; falls back to global default |

For `media = both`, track fulfilment per media type: the item is `done` only when both are satisfied (or the user marks it done).

`wishlist_seen`: `(wishlist_id, mam_id, first_seen_at, dismissed)`. A result is a **new match** only if its `mam_id` is not in `wishlist_seen` for that item, **and** not in `history`, **and** its documented `my_snatched` field is not true. That last check catches books Raygan grabbed outside this app; note MAM's 5–20 min update delay.

Useful documented filters for wishlist items: `searchType` (e.g. `active` to skip dead torrents, or `fl` / `fl-VIP` for freeleech-only), `browse_lang`, `startDate` (only torrents uploaded since the item was created, which keeps responses small), and `perpage` (a small value is fine for re-checks).

### Behaviour

- **Save from search.** An empty result shows **"Save to wishlist"**. Any search can also be saved via a button next to Search. Saving captures the query, search-in fields, media selection and sort.
- **Baseline on save.** Record current results as seen, so only future uploads count.
- **Scheduled re-check** (only when `WISHLIST_SCHEDULER_ENABLED=true`):
  - an in-process asyncio loop started on app startup; **one MAM request in flight at most**, with a randomized delay between requests (default 30–90 s);
  - global default interval **every 3 days** (`WISHLIST_INTERVAL_HOURS`), per-item override, with jitter on `next_check_at`;
  - a hard daily cap on scheduler-initiated MAM requests (`WISHLIST_MAX_REQUESTS_PER_DAY`, default **20**), plus any lower limit from the API Documentation;
  - a "Both" item uses one request covering both categories where the API allows it;
  - on any `MamAuthError` / `MamRateLimitError` / `MamUnexpectedResponse`: halt the scheduler, set a visible state (`halted: <reason>`), notify **once**, and resume only when the user clicks "Resume" after fixing the cause.
  - Document the single-worker requirement.
- **On new matches:**
  - `notify`: mark `matched`, store matches, notify. The user reviews and adds via the existing flow.
  - `auto`: choose the best match using filters (format preference, then seeders), add via `qb.add_from_mam`, write history, update fulfilment, notify. Default `notify`, because auto-grabbing spends ratio without a human decision.
- **Manual controls:** check now (counts toward the daily cap), pause/resume, edit, delete.

### UI

- New **Wishlist** view: query/label, media, status, last/next check, match count, actions. Inline match review with Add buttons.
- A header indicator for unreviewed matches and for scheduler state (disabled / running / halted).

### Notifications

A generic **webhook** (`NOTIFY_WEBHOOK_URL`, optional JSON body template) for new matches, auto-grabs, imports (optional) and scheduler halts. This covers Home Assistant webhooks and ntfy/Gotify/Apprise. Configurable in setup. Never include the cookie or download links in payloads.

### API

- `GET/POST /wishlist`, `PATCH/DELETE /wishlist/{id}`, `POST /wishlist/{id}/check`
- `GET /wishlist/{id}/matches`, `POST /wishlist/{id}/matches/{mam_id}/dismiss`
- `GET /scheduler/status`, `POST /scheduler/resume`

### Acceptance criteria

- An empty search can be saved in one tap on a phone.
- With mocked MAM: an empty item that later returns a result produces exactly one match and one notification; the next check produces none.
- A result already in `history` never counts as a match.
- With the scheduler disabled, no MAM request ever happens without a user action (test).
- Halt-on-error stops all scheduled traffic and notifies once (test with mocked time).
- Delay, single-in-flight, and daily-cap limits are verified in tests.

## Phase 3 — Quality of life (optional, pick and choose)

- **Auto-import on completion.** Audiobooks go to Audiobookshelf (then trigger an ABS library scan via `ABS_URL`/`ABS_TOKEN`); ebooks go to the Grimmory ingest folder. This uses only qB and local files, so no MAM traffic.
- **Download status** on History rows from qB.
- **"Test connection" buttons.** qB uses `/api/v2/app/version`. The MAM test uses one documented call, and only when the user clicks it.
- **Cookie health:** show when MAM last returned an authenticated response, using data from normal user-initiated requests only (no extra polling).
- **Duplicate guard** on manual add.

## Phase 4 — Claude / Home Assistant voice control (MCP): needs a decision first

**Compliance caution.** MAM's rule names AI assistants and LLM tools explicitly. Searching and downloading through an LLM would be automation driven by an AI tool, which MAM does not recommend or support, and Raygan would be fully responsible for whatever the model triggers. **Don't build this phase unless Raygan explicitly confirms it after reviewing the rules** (or MAM staff approve it).

If it goes ahead, design it to keep the human in control:

- An MCP endpoint at `/mcp` inside the same app (one container), using the official MCP Python SDK. Optional bearer token (`MCP_TOKEN`).
- The LLM never talks to MAM directly. It can only call this app's functions, which inherit every rule above (allowlist, limits, fail-closed).
- **Read-mostly tools:** `wishlist_add`, `wishlist_list`, `wishlist_remove`, `recent_activity`, `download_status`. Adding to the wishlist is the safe voice action, because the scheduler and the user's review do the rest.
- **No direct grab tool by default.** If one is added later, it must create a *pending* request the user approves in the web UI before any MAM download happens.
- A `search_mam` tool, if included at all, counts toward a separate low daily cap and is user-confirmable.

## Out of scope

- Metadata-provider lookups (Audible, Hardcover, Goodreads).
- Non-MAM sources, Usenet, RSS/IRC announce watching.
- Any MAM HTML fetching, scraping, or page re-display.
- Any credential-based or browser-automated MAM login.
- Multi-user accounts and request/approval flows (beyond the MCP pending-request idea).

## Open decisions (for Raygan)

1. ✅ Allowlist filled in from the API Documentation (search + download). If MAM documents rate limits elsewhere, add them.
2. Scheduled wishlist searches: the search endpoint is documented, so it's within rule 1.7. The scheduler ships opt-in. Optionally ask MAM staff about acceptable frequency.
3. ✅ Grimmory ingest folder: `/mnt/user/media/Books/eBooks/bookdrop/` (`/media/Books/eBooks/bookdrop` in the container).
4. Default wishlist mode: **notify** (recommended) vs auto-grab.
5. Re-check interval: **3 days** (recommended) or other.
6. Notification target: Home Assistant webhook, ntfy, or both.
7. Whether Phase 4 (MCP) happens at all, given rule 1.7.
8. Versioning: Phase 0 → `0.7`, Phase 1 (ebooks) → `0.8`, Phase 2 (wishlist) → `0.9`; publish to GHCR per `DEV_NOTES.md`.

## Working agreements for Claude Code

- **Re-read the MAM rules section at the start of every session and before touching `mam.py`.**
- One branch per phase (`0.7-compliance`, `0.8-ebooks`, `0.9-wishlist`); small, focused commits per `AGENTS.md`.
- New config keys go into `Settings`, `env.example`, the README env table and (where user-facing) the setup page.
- Update `DEV_NOTES.md` and `docs/MAM_COMPLIANCE.md` at the end of each phase.
- When unsure whether something is allowed by MAM: **stop and ask.**
