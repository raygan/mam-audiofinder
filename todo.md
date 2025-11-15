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
- [ ] Add mode selector  
- [ ] Group by normalized title  
- [ ] Render shared cover  
- [ ] List grouped torrent options  
- [ ] Responsive layout  
- [ ] Lazy-load covers  
- [ ] Propagate cover URLs to qB imports  

---

## ✔ 6. Code Cleanup & Progressive Search Rendering — *Completed*
- [x] Split `main.py` into modules  
- [x] Move migrations out of runtime  
- [x] Standardize logging  
- [x] Implement `CoverService`  
- [x] Progressive image rendering  

---

## 7. Metadata & Testing Prep
- [ ] Add `abs_description` migration  
- [ ] Fetch synopsis fields  
- [ ] Add tests package  
- [ ] Document progressive workflow  

---

## 8. ABS Import Verification
- [ ] Review verification flow  
- [ ] Add DB columns  
- [ ] Implement `verify_import`  
- [ ] Update import route  
- [ ] Surface verification state  
- [ ] Add regression tests  

---

## 9. ABS Metadata Delivery Strategy
- [ ] Prototype metadata.json  
- [ ] Compare upload endpoint  
- [ ] Document approach  
- [ ] Read upload API  
- [ ] Add env fields  
- [ ] Implement path translation  
- [ ] Add upload worker/endpoint  
- [ ] Store ABS upload status  
- [ ] Document feature  

---

## 10. Top-Level Task Bar
- [ ] Add persistent task bar  
- [ ] Extract to helper  
- [ ] Design logs view  
- [ ] Evaluate additional destinations  

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

