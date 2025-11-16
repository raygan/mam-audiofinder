# Series Tab Data Mapping

This document maps Hardcover API data structures to MAM AudioFinder's existing card helper and UI components.

## Current Data Structures

### MAM Search Result (app/routes/search.py)
```python
{
    "id": str,              # MAM torrent ID
    "title": str,           # Book title
    "author_info": str,     # Flattened author data
    "narrator_info": str,   # Flattened narrator data
    "format": str,          # File format (MP3, M4B, etc.)
    "size": int,            # File size in bytes
    "seeders": int,
    "leechers": int,
    "added": str,           # Date added (ISO format)
    "dl": str,              # Download URL
    "in_abs_library": bool  # Whether item exists in ABS
}
```

### Card Helper Input (app/static/js/components/cardHelper.js)
```javascript
{
    title: string,          // Required
    author: string,         // Required
    coverUrl: string,       // Optional, can be null
    mamId: string,          // MAM torrent ID
    formats: Array<string>, // ['MP3', 'M4B']
    versionsCount: number,  // Number of versions
    inLibrary: boolean,     // ABS library status
    description: string,    // Optional description
    onClick: Function,      // Click handler
    cardClass: string,      // CSS class (default: 'showcase-card')
    showDescription: boolean // Whether to show description
}
```

## Hardcover API Structures

### Series Search Result
```graphql
query SearchSeries($name: String!) {
  series(where: {name: {_ilike: $name}}, limit: 10) {
    id                    # Int - Hardcover series ID
    name                  # String - Series name
    author_name           # String - Primary author
    primary_books_count   # Int - Books with integer positions
    readers_count         # Int - Total readers across series
  }
}
```

**Mapped to UI:**
```javascript
{
    seriesId: number,           // Hardcover series.id
    seriesName: string,         // series.name
    authorName: string,         // series.author_name
    bookCount: number,          // series.primary_books_count
    readersCount: number,       // series.readers_count
    matchScore: number          // Computed: fuzzy match confidence (0-100)
}
```

### Series Books Result
```graphql
query GetSeriesBooks($seriesId: Int!) {
  series_by_pk(id: $seriesId) {
    id
    name
    books(order_by: {position: asc}) {
      id                  # Int - Hardcover book ID
      title               # String - Book title
      position            # Float - Series position (1, 2, 2.5, etc.)
      published_year      # Int
      image               # String - Cover URL
      authors {
        id                # Int
        name              # String
      }
    }
  }
}
```

**Mapped to Card Helper:**
```javascript
// Transform Hardcover book to card helper format
function hardcoverBookToCard(book, seriesInfo) {
    return {
        title: book.title,
        author: book.authors.map(a => a.name).join(', '),
        coverUrl: book.image || null,
        mamId: '',                    // Empty initially - will be filled if MAM match found
        formats: [],                  // Empty initially - from MAM data
        versionsCount: 0,             // Will be updated with MAM search results
        inLibrary: false,             // Will be checked against ABS
        description: '',              // Optional - from ABS or Hardcover

        // Series-specific metadata
        seriesId: seriesInfo.id,
        seriesName: seriesInfo.name,
        position: book.position,
        publishedYear: book.published_year,
        hardcoverId: book.id,

        // Display helpers
        positionLabel: formatPosition(book.position), // "Book 1", "Book 2.5"
        cardClass: 'series-book-card'
    };
}

function formatPosition(pos) {
    if (!pos) return '';
    if (pos % 1 === 0) return `Book ${pos}`;
    return `Book ${pos}`; // Shows as "Book 2.5" for novellas
}
```

## Unified Title Normalization

To enable "Series Search" button on any card, we need a unified title field.

### Normalization Rules
```javascript
function normalizeTitle(title) {
    if (!title) return '';

    return title
        .toLowerCase()
        .trim()
        // Remove leading articles
        .replace(/^(the|a|an)\s+/i, '')
        // Remove subtitles (after colon or dash)
        .replace(/[:\-–—].+$/, '')
        // Remove special characters
        .replace(/[^\w\s]/g, '')
        // Normalize whitespace
        .replace(/\s+/g, ' ')
        .trim();
}
```

**Examples:**
- `"The Stormlight Archive: The Way of Kings"` → `"stormlight archive"`
- `"Harry Potter and the Philosopher's Stone"` → `"harry potter and the philosophers stone"`
- `"Project Hail Mary"` → `"project hail mary"`

### Card GUID Generation

Each card needs a unique identifier for event tracking.

```javascript
function generateCardGuid(mamId, title, author) {
    // Use MAM ID if available (unique per torrent)
    if (mamId) return `mam-${mamId}`;

    // Otherwise, generate hash from title + author
    const normalized = `${normalizeTitle(title)}||${normalizeAuthor(author)}`;
    return `card-${simpleHash(normalized)}`;
}

function normalizeAuthor(author) {
    if (!author) return '';
    return author.toLowerCase().trim().replace(/\s+/g, ' ');
}

function simpleHash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash).toString(36);
}
```

## Data Flow: Series Search Workflow

### 1. User Clicks "🔍 Series" Button on Card

**Frontend Event:**
```javascript
// Dispatched from search/history/showcase card
const seriesSearchEvent = new CustomEvent('series-search', {
    detail: {
        cardGuid: 'mam-123456',
        mamId: '123456',
        title: 'The Way of Kings',
        normalizedTitle: 'way of kings',
        author: 'Brandon Sanderson',
        originView: 'search'  // or 'history', 'showcase'
    }
});
document.dispatchEvent(seriesSearchEvent);
```

### 2. Backend Endpoint: POST /api/series/search

**Request:**
```javascript
{
    title: 'The Way of Kings',
    author: 'Brandon Sanderson',
    normalizedTitle: 'way of kings'  // Optional, backend can compute
}
```

**Response:**
```javascript
{
    query: {
        title: 'The Way of Kings',
        author: 'Brandon Sanderson',
        normalizedTitle: 'way of kings'
    },

    // Hardcover series matches
    hardcoverSeries: [
        {
            seriesId: 49075,
            seriesName: 'The Stormlight Archive',
            authorName: 'Brandon Sanderson',
            bookCount: 5,
            readersCount: 125000,
            matchScore: 95  // Fuzzy match confidence
        },
        // ... other potential matches
    ],

    // MAM results for the same query (enrichment)
    mamResults: [
        {
            id: '123456',
            title: 'The Way of Kings',
            author_info: 'Brandon Sanderson',
            format: 'MP3',
            // ... rest of MAM data
        },
        // ... more MAM results
    ],

    cached: false,  // Whether response came from cache
    timestamp: '2025-11-16T10:30:00Z'
}
```

### 3. Frontend Displays Series Matches

**UI Flow:**
```
1. Show modal/slide-in panel with series matches
2. Display series cards (name, author, book count, match score)
3. User clicks a series → Fetch books for that series
4. Display books in order (by position)
5. Each book shows:
   - Cover image
   - Title + position ("Book 2")
   - Published year
   - "Find on MAM" button (if not already matched)
   - "In Library" badge (if in ABS)
```

## Database Schema Requirements

### Migration 009: Series Cache Table

```sql
CREATE TABLE IF NOT EXISTS series_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT UNIQUE NOT NULL,        -- 'search:{hash}' or 'series:{id}'
    cache_type TEXT NOT NULL,               -- 'search' or 'books'

    -- Search cache fields
    query_title TEXT,
    query_author TEXT,
    query_normalized TEXT,

    -- Series cache fields
    series_id INTEGER,
    series_name TEXT,
    series_author TEXT,

    -- Cache data (JSON)
    response_data TEXT NOT NULL,            -- JSON blob of response

    -- Cache metadata
    cached_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,               -- TTL: 5 minutes from cached_at
    hit_count INTEGER DEFAULT 0,

    -- Indexes for quick lookup
    INDEX idx_cache_key (cache_key),
    INDEX idx_expires_at (expires_at),
    INDEX idx_series_id (series_id)
);

-- Cleanup trigger: delete expired entries daily
CREATE TRIGGER IF NOT EXISTS cleanup_expired_series_cache
AFTER INSERT ON series_cache
BEGIN
    DELETE FROM series_cache
    WHERE datetime(expires_at) < datetime('now');
END;
```

### Migration 010: Torrent-Books Junction Table

For multi-book torrents (Phase 4):

```sql
CREATE TABLE IF NOT EXISTS torrent_books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    torrent_hash TEXT NOT NULL,             -- qBittorrent hash
    history_id INTEGER NOT NULL,            -- FK to history table
    position INTEGER,                       -- Book position in series
    hardcover_book_id INTEGER,              -- FK to Hardcover book ID

    -- Book metadata (denormalized for quick access)
    book_title TEXT,
    book_author TEXT,
    series_name TEXT,
    series_position REAL,

    -- Import tracking
    imported_at TEXT,
    abs_item_id TEXT,
    abs_verify_status TEXT,

    created_at TEXT DEFAULT (datetime('now')),

    FOREIGN KEY(history_id) REFERENCES history(id) ON DELETE CASCADE,
    INDEX idx_torrent_hash (torrent_hash),
    INDEX idx_history_id (history_id)
);
```

## API Endpoints to Implement

### Phase 1-2: Search & Series Data

1. **POST /api/series/search**
   - Input: title, author, normalizedTitle (optional)
   - Output: Hardcover series matches + enriched MAM results
   - Caching: 5 minutes

2. **GET /api/series/{series_id}/books**
   - Input: Hardcover series ID
   - Output: Ordered list of books in series
   - Caching: 5 minutes

3. **POST /api/series/match**
   - Input: Hardcover book ID, MAM search query
   - Output: Best MAM matches for that specific book
   - Used to find torrents for specific series books

### Phase 3-4: UI & Multi-Book

4. **GET /series** (page route)
   - Renders series.html template
   - Loads seriesView.js

5. **POST /api/import/multi-book**
   - Input: torrent_hash, books: [{title, author, position, ...}]
   - Output: Import results for each book
   - Special handling: single torrent → multiple ABS imports

## Frontend Components to Create

### 1. Series Search Button Component
```javascript
// app/static/js/components/seriesSearchButton.js
export function addSeriesSearchButton(cardElement, cardData) {
    const button = document.createElement('button');
    button.className = 'series-search-btn';
    button.innerHTML = '🔍 Series';
    button.title = 'Find series for this book';

    button.addEventListener('click', (e) => {
        e.stopPropagation();
        dispatchSeriesSearch(cardData);
    });

    return button;
}
```

### 2. Series View Module
```javascript
// app/static/js/views/seriesView.js
export class SeriesView {
    async showSeriesModal(seriesMatches) { }
    async showSeriesBooks(seriesId) { }
    async matchBookToMAM(hardcoverBookId, title, author) { }
}
```

### 3. Series Card Component
```javascript
// Reuse cardHelper.js but with series-specific data
createBookCard({
    title: book.title,
    author: book.authors[0].name,
    coverUrl: book.image,
    cardClass: 'series-book-card',
    // ... plus series metadata
})
```

## Summary

### Phase 0 Deliverables ✓
- [x] Confirmed Hardcover API schemas
- [x] Documented throttle/retry strategy
- [x] Mapped Series data to card_helper
- [x] Defined unified title normalization
- [x] Designed cache strategy (series_cache table)

### Ready for Phase 1
- Implement unified title + GUID in card helper
- Add "🔍 Series" button to all cards
- Build /api/series/search endpoint
- Update search results to include series context

### Data Transformation Summary
```
Hardcover Series → UI Series Card
Hardcover Book → Card Helper (with series metadata)
MAM Result → Enriched with Hardcover data
User Click → Series Search Event → Backend Fan-out → Cached Response
```
