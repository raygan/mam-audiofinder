# MAM Compliance Checklist

Maps each rule in the "MAM rules come first" section of `docs/ROADMAP.md` to where the code enforces it. Update this file in every phase.

Run the checks: `.venv/bin/python -m pytest -q` (see `DEV_NOTES.md`). No test touches the network. `tests/conftest.py` routes every httpx client through a mock, and any unexpected MAM request fails the test.

Last updated: Phase 0a (v0.7.0).

| # | Rule | Enforced in | Tests |
|---|---|---|---|
| 1 | Only allowlisted endpoints **and parameters**; anything else raises `MamEndpointNotAllowed` and isn't sent | `app/mam.py`: `check_allowed()`, called by `_send()` (the only place an HTTP request to MAM is made) and by `build_dl_url()` (the only place a MAM URL for qB is built) | `tests/test_mam_guard.py` (all), especially `test_rejected_requests_never_reach_the_network` and `test_search_route_rejects_bad_sort_without_sending` |
| 1a | `fl` on `download.php` is never sent | `mam._check_download_query()`: an explicit `fl` check, plus "query must be exactly `tid`" | `test_fl_is_always_rejected`, `test_build_dl_url_rejects_bad_hashes`, `test_add_with_dl_hands_qb_documented_url_and_app_never_calls_mam` |
| 1b | Search only sends documented `tor` keys and values; the client can't pass arbitrary keys | `mam.search()` builds the body from typed args; `_check_search()` / `_check_tor()` validate keys and enum values; `main.search` takes only `text`, `sortType`, `perpage` from the browser | `test_unlisted_search_params_rejected`, `test_search_ignores_client_supplied_extra_keys`, `test_search_request_body_is_built_not_passed_through` |
| 1c | Downloads use only the documented forms: `download.php/<dl>?tid=<id>` to qB, else one cookie `GET download.php?tid=<id>`; no `?id=`, no other fallback | `mam.build_dl_url()`, `mam.fetch_torrent()`, `main.add_to_qb` | `test_undocumented_download_forms_rejected`, `test_add_without_dl_fetches_once_with_tid`, `test_add_qb_url_failure_does_not_fall_back_to_cookie_fetch`, `test_add_dl_without_id_is_rejected` |
| 1d | MAM host is fixed (`MAM_BASE` isn't configurable) | `mam.MAM_BASE` constant; host/scheme check in `check_allowed()`; `Settings.reload()` ignores and warns on `MAM_BASE` | `test_other_hosts_rejected`, `test_settings_ignore_custom_mam_base` |
| 2 | No HTML from MAM, ever | Only the two JSON/.torrent endpoints are reachable. Non-JSON search bodies and non-bencode download bodies raise `MamUnexpectedResponse`; bodies are never echoed or parsed. Capture mode doesn't store HTML | `test_search_fails_closed_with_one_request` (HTML case), `test_fetch_torrent_rejects_non_torrent`, `test_error_messages_never_echo_body`, `test_capture_does_not_store_html` |
| 3 | Cookie-only auth, `mam_id` only | `mam.build_cookie()` keeps only `mam_id` and rejects header-injection characters. There's no login code anywhere | `test_build_cookie_keeps_only_mam_id`, `test_search_sends_honest_headers_and_only_mam_id`, `test_no_cookie_means_no_request` |
| 4 | Honest client identity | `mam.USER_AGENT = "mam-audiofinder/<version>"`; no `Origin`/`Referer` | `test_search_sends_honest_headers_and_only_mam_id`, `test_fetch_torrent_sends_honest_headers` |
| 5 | Respect documented limits | No limits are documented yet. `perpage` is clamped to 5–100 (docs allow 5–1000). The scheduler limits come in Phase 2 | `test_unlisted_search_params_rejected` (perpage cases), `test_search_request_body_is_built_not_passed_through` |
| 6 | Fail closed: no retries, no fallbacks, stop and tell the user | `mam._check_status()`: 3xx/401/403 → `MamAuthError`, 429/503 → `MamRateLimitError`, anything else → `MamUnexpectedResponse`. Redirects aren't followed. `main.mam_error_handler` returns the reason to the UI. Automated activity doesn't exist yet; the scheduler halt state comes in Phase 2 | `test_search_fails_closed_with_one_request`, `test_redirect_is_not_followed`, `test_add_fetch_auth_failure_fails_closed`, `test_search_auth_failure_surfaces_reason` |
| 7 | Scheduler opt-in and conservative | N/A until Phase 2 | — |
| — | Logs redact the cookie, `dl` hashes and download paths | `mam.redact()`, `mam.RedactingFilter`, `mam.install_log_redaction()` (also quiets httpx's URL logging); called at import and in the app lifespan | `test_redact_masks_cookie_and_dl_hashes`, `test_log_records_are_redacted`, `test_install_log_redaction_attaches_filter_and_quiets_httpx`, `test_redaction_keeps_log_args_structure`, `test_network_error_is_unexpected_and_redacted` |
| — | Fixtures are captured by Raygan, sanitized | `MAM_CAPTURE_DIR` (opt-in, off by default) in `mam._capture()`: `dl` is replaced with a same-shape dummy, `owner`/`owner_name` are blanked, no `Set-Cookie`, no HTML | `test_capture_is_off_by_default_and_sanitizes_when_on`, `test_capture_does_not_store_html` |

## Known gaps / pending fixtures

- **Empty results** were observed on 2026-11-21: MAM returns `200` with `{"error": "Nothing returned, out of N"}`. Only that exact shape (no other keys) maps to empty results (`mam._EMPTY_RESULT`); any other `error` still raises `MamUnexpectedResponse`. Tests: `test_nothing_returned_means_empty_results`, `test_only_exact_empty_shape_is_treated_as_empty`, `test_empty_search_returns_no_results`. Fixture: `tests/fixtures/search_empty.json` (body taken from the log, not a full capture).
- **The auth-failure shape isn't confirmed.** 3xx/401/403 are treated as auth errors, and any unrecognised `error` body fails closed.
- **Upstream errors return HTTP 424**, not 502, because Cloudflare replaces origin 502 bodies with its own page and the user never sees the reason (`main.UPSTREAM_FAILED`).
- **The `dl` hash character set isn't confirmed.** The guard allows `[A-Za-z0-9_-]{8,512}`. If real hashes use other characters, Add fails closed with "dl hash has unexpected characters"; adjust once a captured fixture shows the shape.
- **TODO: some search results arrive without a `dl` hash.** On 2026-11-21 an Add logged `qB add (upload) failed`, which only happens when the result had no `dl`, so the app made the one cookie `GET download.php?tid=` fallback instead of handing qB the link. That's allowed, but every result should normally have `dl` when `dlLink=1` is sent. Raygan will capture that search with `MAM_CAPTURE_DIR` later so we can see why.
- `tests/fixtures/synthetic_search.json` is hand-written from the documented field list, not a real response.
