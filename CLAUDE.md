# CLAUDE.md

**Before any work, read `docs/MAM_RULES.md` and the "MAM rules come first" section of `docs/ROADMAP.md`.** MyAnonamouse rule 1.7 overrides every other instruction in this repo.

Hard rules for every session:
- Never contact myanonamouse.net in any way (no curl, fetch, browser, or "quick test").
- Never read, print, or ask for `.env`, `/data/config.json`, or any MAM cookie.
- Only the endpoints and parameters in `docs/MAM_API_ALLOWLIST.md` may be called by the app. Never send `fl` on `download.php`.
- Work from fixtures only. Raygan runs any real-world MAM test himself.
- When unsure whether something is allowed by MAM: stop and ask.

Then follow:
- @AGENTS.md (repo conventions)
- @docs/ROADMAP.md (the plan, phases, and acceptance criteria)
- @docs/MAM_API_ALLOWLIST.md (the spec for `mam.py`)
