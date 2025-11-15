# Targeted UI & Cover Update Plan

## Table of Contents
1. Dark Background With Maroon Accents
2. Audiobookshelf Cover Fetch & Caching
3. Centralized Log Rotation
4. Sharable Search/History URLs
5. Grouped “Showcase” Search Mode
6. Code Cleanup & Progressive Rendering
7. Metadata & Testing Prep
8. ABS Import Verification
9. ABS Metadata Delivery Strategy
10. Top-Level Task Bar
11. Stretch Goal: Enhanced Search
12. COMPLETED FEATURE: Flatten UI With Tree View

---

## ✔ 1. Dark Background With Maroon Accents — *Completed*
- [x] Define new palette tokens  
- [x] Update `body`/`.app-shell` styles  
- [x] Restyle panels/cards  
- [x] Adjust typography  
- [x] Refresh button styles  
- [x] Update templates  
- [ ] Capture before/after screenshots

---

## ✔ 2. Audiobookshelf Cover Fetch & Caching — *Completed*
- [x] Add env vars + validation  
- [x] Implement `fetch_abs_cover`  
- [x] Extend DB schema  
- [x] Surface metadata in search rows  
- [x] Cache lookups  
- [x] Update `/api/covers/fetch` + service  
- [x] Add refresh endpoint  
- [x] Auto-heal missing-file cache cases  

---

## ✔ 3. Centralized Log Rotation (Default 5 Files) — *Completed*
- [x] Log destination setup  
- [x] Replace prints with logger  
- [x] Add log rotation env vars  
- [x] Ensure console logging works  
- [x] Document rotation behavior  

---

## ✔ 4. Sharable Search/History URLs — *Completed*
- [x] Define URL schema  
- [x] Push state on searches  
- [x] Parse URL on load  
- [x] Handle `popstate`  
- [x] Reflect filters in URL  

---

## 5. Display Covers With Grouped Searches (“Showcase” Mode)
- [ ] Create a new helper function for showcase_mode
- [ ] Create new page link from toolbar that shows showcase mode
- [ ] Add a search window from 'search bar' (default 100 results)
- [ ] Group searches by normalized title in audible style grid instead of a list table
- [ ] Render shared cover
- [ ] When a cover is clicked open the list of audiobooks in a list view below on title's own page  
- [ ] Responsive layout  
- [ ] Lazy-load covers  

---

## ✔ 6. Code Cleanup & Progressive Search Rendering — *Completed*
- [x] Split `main.py` into modules  
- [x] Move migrations out of runtime  
- [x] Standardize logging  
- [x] Implement `CoverService`  
- [x] Progressive image rendering  

---
## 7. Metadata & Testing Prep 
- [ ] Add a migration for abs_description (plus optional abs_description_source) and plumb it through /search + /history responses.
- [ ] Extend AudiobookshelfClient to fetch description/synopsis fields (e.g., /api/items/{id}) so the stretch goal has raw data available.
- [ ] Introduce a tests/ package with coverage for search payload construction and cover caching to keep regressions visible.
- [ ] Document the progressive cover workflow in README.md so future contributors understand how metadata flows from ABS → cache → UI. ## 8. ABS Import Verification
- [ ] Review abs-api-agents.md for the canonical import verification flow (endpoints, payloads, expected responses) so we align with existing automation.
- [ ] Add abs_verify_status + abs_verify_note columns via migration to record Audiobookshelf verification outcomes.
- [ ] Implement an ABS client helper (verify_import) that cross-checks imported titles/authors against /api/items (or the specific endpoint noted in abs-api-agents.md) and validates duration/file counts.
- [ ] Update the import route to call the verification helper post-import and persist the verdict (verified imported vs mismatch) along with any diagnostic note.
- [ ] Surface the verification state in /history output and update the frontend to display a green “Verified import” badge or a warning if ABS reports a mismatch.
- [ ] Add regression coverage/mocking around the verification call so failures don’t break imports when ABS is unreachable. ## 9. ABS Metadata Delivery Strategy
- [ ] Prototype feeding Audiobookshelf book metadata via a generated metadata.json alongside imported files; validate what fields ABS honors.
- [ ] Compare that with calling the ABS upload endpoint directly for metadata injection to determine which path keeps data fresher and simpler.
- [ ] Document the chosen approach (and trade-offs) so future ABS uploads keep descriptions, narrators, and cover hints in sync.
- [ ] Read the Audiobookshelf upload API (POST /api/upload) docs to understand required headers, JSON, and multipart fields.
- [ ] Add .env fields for ABS_UPLOAD_LIBRARY_ID and optional ABS_PATH_MAP (format local:/abs) so we can translate qBittorrent save paths into ABS-accessible paths.
- [ ] Implement path translation helper that maps a local filesystem path (e.g., /media/torrents/book) to the ABS server path (/audiobooks/book) using the map or defaults.
- [ ] Create a FastAPI endpoint or background job that, after import completion, calls the ABS upload API with the final file/folder, library ID, and metadata. Handle failures with retries and structured logging.
- [ ] Store upload response (ABS item id/status) in the history table to avoid duplicate uploads and power UI indicators.
- [ ] Document the new feature (env config, ABS permissions, expected behavior) in README/AGENTS so users can enable it safely.
---

## ✔ 10. Top-Level Task Bar — *Completed*
- [x] Add persistent task bar
- [x] Extract to helper
- [x] Design logs view
- [x] Evaluate additional destinations  

---

## Stretch Goal: Book Descriptions & Enhanced Search
- [ ] Fetch ABS descriptions  
- [ ] Optional Audible fallback  
- [ ] Display descriptions in grouped view  
- [ ] Add grouped filters  
- [ ] Document features  

---

# ✔ COMPLETED FEATURE — Flatten UI With Tree View

All backend, frontend, Python syntax validation, and documentation tasks are complete.

Remaining:  
- [x] Manual testing (run-time verification)

