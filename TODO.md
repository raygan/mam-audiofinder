# TODO: Flatten UI with Tree View Implementation

## Overview
Add web UI controls for the flatten feature with:
- Checkbox to enable/disable flattening per-import
- Tree view to preview file structure
- Chapter detector that auto-recommends flatten for multi-disc structures

## Status: ✅ COMPLETED

All tasks have been implemented and documented.

## Tasks

### Backend

- [x] Create GET /qb/torrent/{hash}/tree endpoint
  - ✅ Fetch torrent files from qBittorrent API
  - ✅ Use actual filesystem if qBittorrent data unavailable
  - ✅ Return file structure with paths and sizes

- [x] Add chapter detector helper function
  - ✅ Use existing extract_disc_track() logic
  - ✅ Detect multi-disc structure patterns
  - ✅ Return recommendation flag

- [x] Update ImportBody model
  - ✅ Add optional `flatten: bool | None` parameter
  - ✅ Defaults to None (uses global FLATTEN_DISCS setting)

- [x] Modify /import endpoint logic
  - ✅ Accept per-request flatten parameter
  - ✅ Fallback to FLATTEN_DISCS if not provided
  - ✅ Update response to include flatten status

### Frontend

- [x] Add flatten checkbox to import form
  - ✅ Position between title and torrent selector
  - ✅ Label: "Flatten multi-disc structure"
  - ✅ Default unchecked, auto-set by detector

- [x] Add tree view button and collapsible panel
  - ✅ "📁 View Files" button next to torrent selector
  - ✅ Collapsible tree display showing file structure
  - ✅ Show before/after preview when flatten enabled

- [x] Implement chapter detector integration
  - ✅ Fetch tree data when torrent selected
  - ✅ Auto-check flatten if multi-disc detected
  - ✅ Show detection hint message
  - ✅ Trigger auto-detection for matched torrents

- [x] Add tree view rendering logic
  - ✅ Hierarchical file display with icons
  - ✅ Toggle between original and flattened view
  - ✅ Show file renaming preview

### Testing

- [x] Python syntax validation
  - ✅ All Python files compile without errors
  - ✅ No syntax errors detected

- [ ] Manual testing (requires running application)
  - Test multi-disc audiobook import
  - Test single-file audiobook import
  - Test various naming patterns

### Documentation

- [x] Update CLAUDE.md
  - ✅ Document new API endpoint
  - ✅ Explain chapter detector logic
  - ✅ Update UI workflow description
  - ✅ Add to Recent Features section

## Implementation Notes

- Ensure qBittorrent tree data is real (from API), fallback to filesystem
- Chapter detector uses extract_disc_track() from utils.py
- Tree view updates live when flatten checkbox toggled
- Per-request flatten overrides global FLATTEN_DISCS setting
