# Frontend Architecture

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Architecture Patterns](#architecture-patterns)
  - [Multi-Page Application](#multi-page-application)
  - [Dependency Injection](#dependency-injection)
  - [Event-Driven Communication](#event-driven-communication)
- [Core Services](#core-services)
  - [api.js (~180 lines)](#apijs-180-lines)
  - [router.js (~115 lines)](#routerjs-115-lines)
  - [utils.js (~30 lines)](#utilsjs-30-lines)
- [Services](#services)
  - [coverLoader.js (~180 lines)](#coverloaderjs-180-lines)
- [Views](#views)
  - [searchView.js (~230 lines)](#searchviewjs-230-lines)
  - [historyView.js (~180 lines)](#historyviewjs-180-lines)
  - [showcaseView.js (~610 lines)](#showcaseviewjs-610-lines)
  - [logsView.js (~80 lines)](#logsviewjs-80-lines)
- [Components](#components)
  - [importForm.js (~400 lines)](#importformjs-400-lines)
  - [libraryIndicator.js](#libraryindicatorjs)
- [Page Controllers](#page-controllers)
  - [search.js (~130 lines)](#searchjs-130-lines)
  - [history.js (~120 lines)](#historyjs-120-lines)
  - [showcase.js (~140 lines)](#showcasejs-140-lines)
  - [logs.js (~110 lines)](#logsjs-110-lines)
- [Styling](#styling)
  - [CSS Architecture](#css-architecture)
  - [Theme Variables](#theme-variables)
  - [Responsive Design](#responsive-design)
  - [Component Styles](#component-styles)
- [Development Workflow](#development-workflow)
  - [Adding a New Page](#adding-a-new-page)
  - [Adding a New Component](#adding-a-new-component)
  - [Debugging Tips](#debugging-tips)
- [Performance Optimization](#performance-optimization)
  - [Lazy Loading](#lazy-loading)
  - [Debouncing](#debouncing)
  - [Request Batching](#request-batching)
  - [Caching](#caching)
  - [Minimal Reflows](#minimal-reflows)
- [Testing](#testing)
  - [Manual Testing Checklist](#manual-testing-checklist)
  - [Browser Compatibility](#browser-compatibility)

## Overview

The frontend is a **multi-page application** built with:
- **Vanilla JavaScript ES6 modules** - No frameworks, no build step
- **Jinja2 templates** - Server-rendered HTML pages
- **Event-driven architecture** - Custom events for inter-component communication
- **URL state management** - Shareable, bookmarkable search/filter states
- **Progressive enhancement** - Works without JavaScript, enhanced with it

**Philosophy:** Keep it simple. No webpack, no React, no complexity. Just modern browser features.

## Project Structure

```
app/static/
├── js/
│   ├── core/                      # Core services (~315 lines)
│   │   ├── api.js                 # Centralized API client (180 lines, 11 methods)
│   │   ├── router.js              # URL state management (115 lines)
│   │   └── utils.js               # Utilities (30 lines)
│   │
│   ├── services/                  # Shared services (~180 lines)
│   │   └── coverLoader.js         # Progressive cover loading
│   │
│   ├── views/                     # Page views (~1,220 lines)
│   │   ├── searchView.js          # Search form + results (230 lines)
│   │   ├── historyView.js         # History table + import (180 lines)
│   │   ├── showcaseView.js        # Grouped grid view (610 lines)
│   │   └── logsView.js            # Log viewer (80 lines)
│   │
│   ├── components/                # Reusable components (~400 lines)
│   │   ├── importForm.js          # Import modal with multi-disc detection
│   │   └── libraryIndicator.js    # "In library" badge component
│   │
│   └── pages/                     # Page entry points (~500 lines)
│       ├── search.js              # Search page controller
│       ├── history.js             # History page controller
│       ├── showcase.js            # Showcase page controller
│       └── logs.js                # Logs page controller
│
└── css/
    └── styles.css                 # Global styles
```

## Architecture Patterns

### Multi-Page Application

Unlike Single Page Applications (SPAs), each route is a separate HTML page:

- `/` → `templates/search.html` → loads `pages/search.js`
- `/history` → `templates/history.html` → loads `pages/history.js`
- `/showcase` → `templates/showcase.html` → loads `pages/showcase.js`
- `/logs` → `templates/logs.html` → loads `pages/logs.js`

**Benefits:**
- Simpler architecture (no client-side routing complexity)
- Better SEO (server-rendered pages)
- Faster initial page load (no framework overhead)
- Native browser navigation (back/forward work correctly)

**Trade-off:**
- Full page reload on navigation
- State doesn't persist between pages (mitigated by URL state)

### Dependency Injection

Views and components receive their DOM references via constructor:

```javascript
// searchView.js
class SearchView {
  constructor(refs) {
    this.searchForm = refs.searchForm;
    this.resultsContainer = refs.resultsContainer;
    this.loadingSpinner = refs.loadingSpinner;
  }
}

// search.js (page controller)
const view = new SearchView({
  searchForm: document.getElementById('search-form'),
  resultsContainer: document.getElementById('results'),
  loadingSpinner: document.getElementById('loading')
});
```

**Benefits:**
- Testable (can inject mock DOM elements)
- Explicit dependencies (no hidden globals)
- Reusable (same view, different DOM elements)

### Event-Driven Communication

Custom events enable loose coupling between components:

```javascript
// Component A: Dispatches event
document.dispatchEvent(new CustomEvent('torrentAdded', {
  detail: { hash, title }
}));

// Component B: Listens for event
document.addEventListener('torrentAdded', (e) => {
  console.log('Torrent added:', e.detail.title);
  refreshHistory();
});
```

**Events Used:**
- `torrentAdded` - Fired when user adds torrent to qBittorrent
- `importCompleted` - Fired when import finishes
- `routerStateChange` - Fired when URL state changes
- `coverLoaded` - Fired when cover image loads

**Benefits:**
- Components don't need references to each other
- Easy to add new listeners without modifying emitters
- Debugging with DevTools event listener inspector

## Core Services

### api.js (~180 lines)

Centralized API client with 11 methods.

**Methods:**

```javascript
// Search
api.search(params)                    // POST /search
api.getShowcase(params)               // GET /api/showcase

// History
api.getHistory()                      // GET /api/history
api.deleteHistory(id)                 // DELETE /api/history/{id}
api.verifyHistoryItem(id)             // POST /api/history/{id}/verify

// qBittorrent
api.addTorrent(mamId, dl)             // POST /add
api.getQBTorrents(filters)            // GET /qb/torrents
api.getTorrentTree(hash)              // GET /qb/torrent/{hash}/tree

// Import
api.importTorrent(data)               // POST /import

// Covers
api.fetchCover(params)                // POST /api/covers/fetch

// Logs
api.getLogs()                         // GET /api/logs
```

**Features:**
- Cache-busting headers on all requests
- JSON request/response handling
- Error handling with user-friendly messages
- Consistent response parsing

**Example Usage:**

```javascript
import { api } from '../core/api.js';

try {
  const results = await api.search({ title: 'Foundation', limit: 50 });
  renderResults(results);
} catch (error) {
  showError(error.message);
}
```

### router.js (~115 lines)

URL state management for shareable/bookmarkable pages.

**Features:**
- Parse query parameters from URL
- Push state to browser history
- Handle popstate (browser back/forward)
- Restore UI state from URL

**URL Schemas:**

**Search Page:**
```
/?title=Foundation&author=Asimov&limit=100
```

**Showcase Page:**
```
/showcase?q=Ender&limit=50&detail=enders-game
```
- `detail` parameter opens detail view for specific title

**Usage Example:**

```javascript
import { router } from '../core/router.js';

// Parse URL on page load
const state = router.getState();
if (state.title) {
  searchForm.querySelector('[name="title"]').value = state.title;
  performSearch();
}

// Update URL when search submitted
router.setState({ title: 'Foundation', limit: 100 });
```

**popstate Handling:**

```javascript
window.addEventListener('popstate', () => {
  const state = router.getState();
  restoreUIFromState(state);
});
```

### utils.js (~30 lines)

Utility functions for common operations.

**Functions:**

```javascript
// XSS prevention
escapeHtml(str)  // Escapes <, >, &, ", '

// File size formatting
formatSize(bytes)  // 1234567 → "1.2 MB"
```

**Example:**

```javascript
import { escapeHtml, formatSize } from '../core/utils.js';

const html = `<div>${escapeHtml(userInput)}</div>`;
const size = formatSize(torrent.size);  // "42.3 GB"
```

## Services

### coverLoader.js (~180 lines)

Progressive cover loading with lazy loading and retry logic.

**Features:**
- **Lazy loading:** Only fetches covers when they enter viewport (IntersectionObserver)
- **Retry logic:** 3 attempts with random jitter (0-300ms)
- **State management:** Tracks loading/loaded/error states per row
- **Graceful degradation:** Shows placeholder on error

**Usage:**

```javascript
import { CoverLoader } from '../services/coverLoader.js';

const loader = new CoverLoader();

// Add row to be loaded
loader.addRow(rowElement, {
  mam_id: '12345',
  title: 'Foundation',
  author: 'Isaac Asimov'
});

// Covers load automatically when rows enter viewport
```

**Workflow:**

```
1. Row enters viewport (IntersectionObserver triggers)
2. Check if already loaded/loading (skip if yes)
3. Add random jitter (0-300ms) to spread requests
4. Call api.fetchCover(mam_id, title, author)
5. On success: Update img src, mark loaded
6. On error: Retry up to 3 times
7. On final failure: Show placeholder image
```

**State Tracking:**

```javascript
// Internal state map
{
  'row-123': {
    loading: true,
    loaded: false,
    error: null,
    retries: 1,
    coverUrl: null
  }
}
```

## Views

### searchView.js (~230 lines)

Search form and results rendering.

**Responsibilities:**
- Handle search form submission
- Render search results table
- Progressive cover loading
- "Add to qBittorrent" buttons
- Library indicators ("Already in library" badges)

**Key Methods:**

```javascript
class SearchView {
  constructor(refs)                   // Initialize with DOM refs
  init()                              // Set up event listeners
  async performSearch(params)         // Execute search via API
  renderResults(results)              // Render results table
  renderRow(result, index)            // Render single result row
  handleAddClick(mamId, dl)           // Add torrent to qBittorrent
}
```

**Result Row Structure:**

```html
<tr>
  <td class="cover-cell">
    <div class="cover-container">
      <img class="skeleton" />  <!-- Placeholder, replaced by CoverLoader -->
      <div class="in-library-indicator">✓</div>  <!-- If in_abs_library -->
    </div>
  </td>
  <td class="title-cell">{title}</td>
  <td class="author-cell">{author}</td>
  <td class="narrator-cell">{narrator}</td>
  <td class="format-cell">{format}</td>
  <td class="size-cell">{size}</td>
  <td class="seeders-cell">{seeders}</td>
  <td class="actions-cell">
    <button class="add-btn" data-mam-id="{mam_id}" data-dl="{dl}">Add</button>
  </td>
</tr>
```

**Cover Loading Integration:**

```javascript
// After rendering all rows
this.coverLoader = new CoverLoader();
rows.forEach(row => {
  this.coverLoader.addRow(row, {
    mam_id: result.mam_id,
    title: result.title,
    author: result.author
  });
});
```

### historyView.js (~180 lines)

History table with live torrent states and import functionality.

**Responsibilities:**
- Fetch and render history entries
- Show live torrent progress from qBittorrent
- Display verification status badges
- Import button opens ImportForm modal
- Manual re-verification ("🔄 Verify" button)
- Delete history entries

**Key Methods:**

```javascript
class HistoryView {
  constructor(refs)
  init()
  async loadHistory()                 // Fetch history + live states
  renderHistory(entries)              // Render table
  renderRow(entry)                    // Render single row
  showImportForm(entry)               // Open import modal
  async handleVerify(id)              // Manual re-verification
  async handleDelete(id)              // Delete entry
}
```

**Status Badges:**

```javascript
// Verification status
switch (entry.abs_verify_status) {
  case 'verified':
    badge = '<span class="badge badge-success" title="Verified">✓</span>';
    break;
  case 'mismatch':
    badge = '<span class="badge badge-warning" title="Mismatch">⚠</span>';
    break;
  case 'not_found':
    badge = '<span class="badge badge-error" title="Not found">✗</span>';
    break;
  case 'unreachable':
    badge = '<span class="badge badge-neutral" title="Unreachable">?</span>';
    break;
}
```

**Progress Display:**

```javascript
// Live torrent progress
if (entry.qb_state === 'downloading') {
  progress = `<div class="progress-bar">
    <div class="progress-fill" style="width: ${entry.qb_progress}%"></div>
    <span class="progress-text">${entry.qb_progress}%</span>
  </div>`;
}
```

**Import Form Integration:**

```javascript
import { ImportForm } from '../components/importForm.js';

showImportForm(entry) {
  const modal = new ImportForm({
    torrentHash: entry.qb_hash,
    torrentName: entry.title,
    onSuccess: () => this.loadHistory()  // Refresh on success
  });
  modal.show();
}
```

### showcaseView.js (~610 lines)

Grouped grid view with detail mode.

**Responsibilities:**
- Fetch grouped search results from `/api/showcase`
- Render card-based grid layout
- Handle card clicks → detail view
- Detail view: Full-screen with versions table
- URL state management (grid ↔ detail transitions)
- Progressive cover loading
- Description display with expand/collapse

**Key Methods:**

```javascript
class ShowcaseView {
  constructor(refs)
  init()
  async performSearch(params)         // Fetch grouped results
  renderGrid(groups)                  // Render card grid
  renderCard(group)                   // Render single card
  showDetail(group)                   // Show detail view
  hideDetail()                        // Return to grid
  showDetailByIdentifier(id)          // Restore detail from URL
  updateURL(params)                   // Update browser history
}
```

**Grid Card Structure:**

```html
<div class="showcase-card" data-normalized-title="{normalized_title}">
  <div class="card-cover">
    <img class="skeleton" />  <!-- Loaded progressively -->
    <div class="in-library-indicator">✓</div>  <!-- If in_abs_library -->
    <div class="version-badge">{total_versions} versions</div>
  </div>
  <div class="card-content">
    <h3 class="card-title">{display_title}</h3>
    <p class="card-author">{author}</p>
    <p class="card-narrator">{narrator}</p>
    <p class="card-formats">{formats}</p>
  </div>
</div>
```

**Detail View Structure:**

```html
<div class="detail-view">
  <div class="detail-header">
    <button class="close-btn">← Back</button>
    <h2>{display_title}</h2>
  </div>
  <div class="detail-body">
    <div class="detail-cover">
      <img src="{cover_url}" />
    </div>
    <div class="detail-info">
      <p><strong>Author:</strong> {author}</p>
      <p><strong>Narrator:</strong> {narrator}</p>
      <p><strong>Formats:</strong> {formats}</p>

      <!-- Description (if available) -->
      <div class="description">
        <p class="description-text">{description}</p>
        <button class="show-more">Show more</button>
        <p class="description-source">via Audiobookshelf</p>
      </div>

      <!-- Versions table -->
      <table class="versions-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Format</th>
            <th>Size</th>
            <th>Seeders</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {versions.map(v => renderVersionRow(v))}
        </tbody>
      </table>
    </div>
  </div>
</div>
```

**URL State Management:**

```javascript
// User clicks card
showDetail(group) {
  renderDetailView(group);
  this.updateURL({ detail: group.normalized_title });
}

// User clicks back button
hideDetail() {
  showGridView();
  this.updateURL({ detail: null });
}

// Browser back/forward
window.addEventListener('popstate', () => {
  const state = router.getState();
  if (state.detail) {
    this.showDetailByIdentifier(state.detail);
  } else {
    this.hideDetail();
  }
});
```

**Cover Loading:**

```javascript
// Custom implementation (not CoverLoader service)
loadCover(card, group) {
  const img = card.querySelector('img');

  // Fetch cover with retry
  this.fetchCoverWithRetry(group.mam_id, group.display_title, group.author)
    .then(coverUrl => {
      img.src = coverUrl;
      img.classList.remove('skeleton');
    })
    .catch(() => {
      img.src = '/static/placeholder.png';
      img.classList.remove('skeleton');
    });
}

async fetchCoverWithRetry(mam_id, title, author, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      // Random jitter to spread requests
      await new Promise(r => setTimeout(r, Math.random() * 300));
      const result = await api.fetchCover({ mam_id, title, author });
      return result.cover_url;
    } catch (error) {
      if (i === retries - 1) throw error;
    }
  }
}
```

**Description Expand/Collapse:**

```javascript
renderDescription(description) {
  const isLong = description.length > 200;
  const preview = isLong ? description.slice(0, 200) + '...' : description;

  return `
    <div class="description">
      <p class="description-text ${isLong ? 'collapsed' : ''}">${escapeHtml(preview)}</p>
      ${isLong ? '<button class="show-more">Show more</button>' : ''}
      <p class="description-source">via Audiobookshelf</p>
    </div>
  `;
}

// Click handler
descriptionContainer.addEventListener('click', (e) => {
  if (e.target.matches('.show-more')) {
    const text = e.target.previousElementSibling;
    text.classList.toggle('collapsed');
    e.target.textContent = text.classList.contains('collapsed') ? 'Show more' : 'Show less';
  }
});
```

### logsView.js (~80 lines)

Simple log viewer with filtering.

**Responsibilities:**
- Fetch logs from `/api/logs`
- Render with syntax highlighting
- Filter by log level (INFO, WARNING, ERROR)
- Auto-refresh option

**Key Methods:**

```javascript
class LogsView {
  constructor(refs)
  init()
  async loadLogs()                    // Fetch and render logs
  renderLogs(logs)                    // Render log entries
  filterLogs(level)                   // Filter by level
}
```

**Log Entry Rendering:**

```javascript
renderLogEntry(log) {
  const levelClass = `log-${log.level.toLowerCase()}`;
  return `
    <div class="log-entry ${levelClass}">
      <span class="log-timestamp">${log.timestamp}</span>
      <span class="log-level">${log.level}</span>
      <span class="log-message">${escapeHtml(log.message)}</span>
    </div>
  `;
}
```

## Components

### importForm.js (~400 lines)

Import modal with multi-disc detection and flatten preview.

**Responsibilities:**
- Torrent selection dropdown
- Destination path input
- Multi-disc detection (automatic checkbox)
- File tree visualization
- Flatten preview (before/after)
- Form validation
- Import execution

**Constructor:**

```javascript
new ImportForm({
  torrentHash,      // Pre-selected torrent (optional)
  torrentName,      // Display name (optional)
  onSuccess         // Callback on successful import
})
```

**Workflow:**

```
1. Show modal
2. Fetch available torrents from qBittorrent
3. User selects torrent
4. Fetch file tree for selected torrent
5. Analyze tree for multi-disc structure
6. If multi-disc detected: Auto-check "Flatten" checkbox
7. If flatten enabled: Show before/after preview
8. User enters destination path
9. User submits form
10. Call api.importTorrent()
11. On success: Call onSuccess() callback
12. Close modal
```

**Multi-Disc Detection:**

```javascript
async analyzeTree(hash) {
  const tree = await api.getTorrentTree(hash);

  // Check for disc patterns
  const hasMultiDisc = tree.multi_disc_detected;

  if (hasMultiDisc) {
    this.flattenCheckbox.checked = true;
    this.showTreePreview(tree);
  }
}
```

**Tree Preview:**

```javascript
renderTreePreview(tree) {
  // Before flatten
  const before = `
    Book Title/
    ├── Disc 01/
    │   ├── Track 01.mp3
    │   └── Track 02.mp3
    └── Disc 02/
        ├── Track 01.mp3
        └── Track 02.mp3
  `;

  // After flatten
  const after = `
    Book Title/
    ├── Part 001.mp3
    ├── Part 002.mp3
    ├── Part 003.mp3
    └── Part 004.mp3
  `;

  return `<div class="tree-preview">
    <div class="before"><h4>Before</h4><pre>${before}</pre></div>
    <div class="after"><h4>After</h4><pre>${after}</pre></div>
  </div>`;
}
```

### libraryIndicator.js

"Already in library" badge component.

**Usage:**

```javascript
import { createLibraryIndicator, addLibraryIndicator } from '../components/libraryIndicator.js';

// Create indicator element
const indicator = createLibraryIndicator(inLibrary);

// Add to cover container
const coverContainer = document.querySelector('.cover-container');
addLibraryIndicator(coverContainer, inLibrary);
```

**Rendering:**

```javascript
function createLibraryIndicator(inLibrary) {
  if (!inLibrary) return null;

  const indicator = document.createElement('div');
  indicator.className = 'in-library-indicator';
  indicator.textContent = '✓';
  indicator.title = 'Already in your library';
  return indicator;
}
```

**CSS:**

```css
.in-library-indicator {
  position: absolute;
  bottom: 4px;
  right: 4px;
  background: var(--success-color);
  color: white;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: bold;
  box-shadow: 0 2px 4px rgba(0,0,0,0.3);
}
```

## Page Controllers

### search.js (~130 lines)

Entry point for search page.

**Responsibilities:**
- Initialize SearchView
- Restore URL state on page load
- Health check
- Error handling

```javascript
import { SearchView } from '../views/searchView.js';
import { router } from '../core/router.js';

document.addEventListener('DOMContentLoaded', () => {
  const view = new SearchView({
    searchForm: document.getElementById('search-form'),
    resultsContainer: document.getElementById('results'),
    loadingSpinner: document.getElementById('loading')
  });

  view.init();

  // Restore state from URL
  const state = router.getState();
  if (state.title || state.author || state.narrator) {
    view.performSearch(state);
  }
});
```

### history.js (~120 lines)

Entry point for history page.

```javascript
import { HistoryView } from '../views/historyView.js';

document.addEventListener('DOMContentLoaded', () => {
  const view = new HistoryView({
    historyContainer: document.getElementById('history-table'),
    loadingSpinner: document.getElementById('loading')
  });

  view.init();
  view.loadHistory();

  // Auto-refresh every 30 seconds
  setInterval(() => view.loadHistory(), 30000);
});
```

### showcase.js (~140 lines)

Entry point for showcase page.

```javascript
import { ShowcaseView } from '../views/showcaseView.js';
import { router } from '../core/router.js';

document.addEventListener('DOMContentLoaded', () => {
  const view = new ShowcaseView({
    gridContainer: document.getElementById('showcase-grid'),
    detailContainer: document.getElementById('detail-view'),
    searchForm: document.getElementById('showcase-search'),
    loadingSpinner: document.getElementById('loading')
  });

  view.init();

  // Restore state from URL
  const state = router.getState();
  if (state.q) {
    view.performSearch({ q: state.q, limit: state.limit || 100 });

    // Restore detail view if in URL
    if (state.detail) {
      view.showDetailByIdentifier(state.detail);
    }
  }
});
```

### logs.js (~110 lines)

Entry point for logs page.

```javascript
import { LogsView } from '../views/logsView.js';

document.addEventListener('DOMContentLoaded', () => {
  const view = new LogsView({
    logsContainer: document.getElementById('logs-container'),
    levelFilter: document.getElementById('level-filter'),
    refreshBtn: document.getElementById('refresh-btn')
  });

  view.init();
  view.loadLogs();
});
```

## Styling

### CSS Architecture

**File:** `app/static/css/styles.css`

**Structure:**
- CSS variables for theming
- Reset/normalize
- Layout (flexbox-based)
- Components (buttons, cards, tables, forms)
- Page-specific styles
- Responsive breakpoints

### Theme Variables

```css
:root {
  /* Colors */
  --bg-primary: #1a1a1a;
  --bg-secondary: #2a2a2a;
  --bg-tertiary: #3a3a3a;
  --text-primary: #e0e0e0;
  --text-secondary: #a0a0a0;
  --accent: #8b2e2e;           /* Maroon */
  --accent-hover: #a64040;
  --success: #4a9b4a;
  --warning: #c4a000;
  --error: #c44040;

  /* Spacing */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;

  /* Typography */
  --font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-size-sm: 12px;
  --font-size-md: 14px;
  --font-size-lg: 16px;
  --font-size-xl: 20px;

  /* Borders */
  --border-radius: 4px;
  --border-color: #444;
}
```

### Responsive Design

**Breakpoints:**

```css
/* Mobile first approach */
@media (min-width: 768px) {
  /* Tablet */
}

@media (min-width: 1024px) {
  /* Desktop */
}

@media (min-width: 1440px) {
  /* Large desktop */
}
```

**Responsive Patterns:**

```css
/* Grid: 1 column → 2 columns → 3 columns → 4 columns */
.showcase-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--spacing-md);
}

/* Table: Horizontal scroll on mobile */
.table-container {
  overflow-x: auto;
}

@media (max-width: 767px) {
  table {
    min-width: 800px;  /* Force horizontal scroll */
  }
}
```

### Component Styles

**Buttons:**

```css
.btn {
  padding: var(--spacing-sm) var(--spacing-md);
  border: none;
  border-radius: var(--border-radius);
  background: var(--accent);
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.2s;
}

.btn:hover {
  background: var(--accent-hover);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

**Cards:**

```css
.card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  padding: var(--spacing-md);
  transition: transform 0.2s, box-shadow 0.2s;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
}
```

**Badges:**

```css
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: var(--font-size-sm);
  font-weight: bold;
}

.badge-success { background: var(--success); color: white; }
.badge-warning { background: var(--warning); color: black; }
.badge-error { background: var(--error); color: white; }
.badge-neutral { background: var(--bg-tertiary); color: var(--text-secondary); }
```

## Development Workflow

### Adding a New Page

1. **Create template** in `app/templates/my-page.html`:
   ```html
   {% extends "base.html" %}

   {% block content %}
   <div id="my-page-container"></div>
   {% endblock %}

   {% block scripts %}
   <script type="module" src="/static/js/pages/my-page.js"></script>
   {% endblock %}
   ```

2. **Create route** in `app/routes/basic.py`:
   ```python
   @router.get("/my-page", response_class=HTMLResponse)
   async def my_page(request: Request):
       return templates.TemplateResponse("my-page.html", {"request": request})
   ```

3. **Create view** in `app/static/js/views/myPageView.js`:
   ```javascript
   export class MyPageView {
     constructor(refs) {
       this.container = refs.container;
     }

     init() {
       // Set up event listeners
     }

     render() {
       // Render UI
     }
   }
   ```

4. **Create page controller** in `app/static/js/pages/my-page.js`:
   ```javascript
   import { MyPageView } from '../views/myPageView.js';

   document.addEventListener('DOMContentLoaded', () => {
     const view = new MyPageView({
       container: document.getElementById('my-page-container')
     });
     view.init();
     view.render();
   });
   ```

5. **Add navigation link** in `app/templates/base.html`:
   ```html
   <nav>
     <!-- ... existing links ... -->
     <a href="/my-page">My Page</a>
   </nav>
   ```

### Adding a New Component

1. **Create component file** in `app/static/js/components/myComponent.js`:
   ```javascript
   export class MyComponent {
     constructor(options) {
       this.options = options;
     }

     render() {
       // Return HTML string or DOM element
     }

     mount(container) {
       container.innerHTML = this.render();
       this.attachEventListeners();
     }

     attachEventListeners() {
       // Set up listeners
     }
   }
   ```

2. **Use in view**:
   ```javascript
   import { MyComponent } from '../components/myComponent.js';

   const component = new MyComponent({ prop: 'value' });
   component.mount(document.getElementById('target'));
   ```

### Debugging Tips

**Browser DevTools:**
- Console: Check for JavaScript errors
- Network: Inspect API calls, check request/response
- Elements: Inspect DOM, modify styles live
- Event Listeners: See what listeners are attached to elements

**Logging:**

```javascript
// Development logging
console.log('Search results:', results);
console.table(results);  // Nice table view for arrays
console.time('renderGrid');
renderGrid(groups);
console.timeEnd('renderGrid');
```

**Common Issues:**

**Cover not loading:**
- Check Network tab for 404/500 errors
- Verify API response has cover_url
- Check browser console for CORS errors

**Event not firing:**
- Verify event name matches exactly
- Check if listener is attached before event fires
- Use DevTools Event Listener inspector

**State not restoring from URL:**
- Check router.getState() returns expected values
- Verify URL format matches schema
- Check if state is applied before fetching data

## Performance Optimization

### Lazy Loading

**Covers:** Only load when in viewport
**Scripts:** Use `type="module"` with dynamic imports for code splitting
**Images:** `loading="lazy"` attribute on img tags

### Debouncing

```javascript
// Search input debounce
let debounceTimer;
searchInput.addEventListener('input', (e) => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    performSearch(e.target.value);
  }, 300);  // Wait 300ms after last keystroke
});
```

### Request Batching

**Cover fetches:** Random jitter spreads requests over time (prevents thundering herd)
**Library checks:** Backend batches all checks in single API call

### Caching

**API responses:** Backend caches MAM searches, ABS library checks
**Cover images:** Browser cache + local disk cache
**DOM references:** Store in view instance, don't re-query

### Minimal Reflows

```javascript
// Bad: Multiple reflows
for (let item of items) {
  container.appendChild(renderItem(item));  // Reflow on each append
}

// Good: Single reflow
const fragment = document.createDocumentFragment();
for (let item of items) {
  fragment.appendChild(renderItem(item));
}
container.appendChild(fragment);  // Single reflow
```

## Testing

### Manual Testing Checklist

**Search Page:**
- [ ] Search with title/author/narrator
- [ ] Add torrent to qBittorrent
- [ ] Cover images load progressively
- [ ] Library indicators appear
- [ ] URL updates with search params
- [ ] Back button restores search

**History Page:**
- [ ] History entries load with live states
- [ ] Verification badges display correctly
- [ ] Import button opens modal
- [ ] Manual verify button works
- [ ] Delete entry removes from list

**Showcase Page:**
- [ ] Grouped results display correctly
- [ ] Card clicks open detail view
- [ ] Detail view shows versions table
- [ ] Back button closes detail
- [ ] URL state preserves detail view
- [ ] Descriptions expand/collapse

**Import Modal:**
- [ ] Torrent selection populates
- [ ] Multi-disc detection auto-checks flatten
- [ ] Tree preview shows before/after
- [ ] Import succeeds and updates history
- [ ] Error messages display on failure

### Browser Compatibility

**Minimum versions:**
- Chrome/Edge: 90+
- Firefox: 88+
- Safari: 14+

**Required features:**
- ES6 modules
- async/await
- fetch API
- IntersectionObserver
- CSS Grid
- CSS Custom Properties

**No polyfills needed** for target browsers.
