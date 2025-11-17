# Hardcover API Implementation Audit

**Date:** 2025-11-17
**Auditor:** Claude
**Source:** Official Hardcover Documentation - [Searching.mdx](https://raw.githubusercontent.com/hardcoverapp/hardcover-docs/refs/heads/main/src/content/docs/api/guides/Searching.mdx)

---

## Executive Summary

This audit compares our Hardcover API implementation against the official documentation to identify discrepancies that may be causing test failures, particularly with series book queries.

**Key Findings:**
1. ✅ **Search endpoint** implementation is mostly correct
2. ⚠️ **Series fields** have important distinctions between search and direct queries
3. ❌ **Critical Gap:** `series_by_pk` endpoint is NOT documented in official docs
4. ⚠️ **Field availability** differs between search results and individual series queries

---

## Official Documentation Summary

### Search Endpoint Response Structure

According to the official docs, the search endpoint returns:

```json
{
  "search": {
    "ids": [...],           // Array of result IDs in order
    "results": {...},       // Objects from Typesense index
    "query": "...",         // Echoed parameter
    "query_type": "...",    // Echoed parameter
    "page": 1,              // Echoed parameter
    "per_page": 25          // Echoed parameter
  }
}
```

The `results` object from Typesense contains:
```json
{
  "found": N,               // Total matches
  "hits": [                 // Array of results
    {
      "document": {...},    // Actual data
      "highlight": {...}    // Optional highlighting
    }
  ]
}
```

### Series Search Fields

When `query_type: "series"`, the document contains:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string/int | Series ID |
| `name` | string | Series name |
| `slug` | string | URL slug |
| `author_name` | string | **Primary author name (STRING FIELD)** |
| `author` | object | **Author object with {id, name, image, slug}** |
| `books` | array | **List of book TITLES (strings, top 5)** |
| `books_count` | int | Total number of books |
| `primary_books_count` | int | Books with integer positions only |
| `readers_count` | int | Sum of readers (non-distinct) |

**Default search parameters:**
- fields: `name,books,author_name`
- weights: `2,1,1`
- sort: `_text_match:desc,readers_count:desc`

---

## Implementation Audit

### ✅ search_series() Function (Lines 281-438)

**Status:** MOSTLY CORRECT

**What we do:**
1. ✅ Correctly use GraphQL search endpoint
2. ✅ Correctly parse `results -> hits -> document` structure
3. ✅ Extract: `id`, `name`, `author_name`, `books_count`/`primary_books_count`, `readers_count`
4. ✅ Handle both dict and list response formats (defensive)
5. ✅ Cache results properly

**Issues found:**
1. ⚠️ **We DON'T use the `author` object from search results**
   - Search results include BOTH `author_name` (string) AND `author` (object)
   - We only extract `author_name` field
   - We ignore the richer `author` object data (id, image, slug)

2. ⚠️ **We DON'T use the `books` field**
   - Search results include `books` array (top 5 book titles as strings)
   - We completely ignore this field
   - Could be useful for verification/matching

**Current extraction (line 390-396):**
```python
series_list.append({
    "series_id": doc.get("id"),
    "series_name": doc.get("name", ""),
    "author_name": doc.get("author_name", ""),  # ✅ Correct for search
    "book_count": doc.get("primary_books_count", doc.get("books_count", 0)),
    "readers_count": doc.get("readers_count", 0)
})
```

---

### ❌ list_series_books() Function (Lines 440-542)

**Status:** CRITICAL ISSUE - USING UNDOCUMENTED ENDPOINT

**The Problem:**

We use `series_by_pk(id:)` endpoint which is **NOT documented** in the official Hardcover API documentation. This is a completely different endpoint than the search endpoint.

**What we're doing:**
```graphql
query GetSeriesBooks($seriesId: Int!) {
  series_by_pk(id: $seriesId) {    # ❌ UNDOCUMENTED ENDPOINT
    id
    name
    author {                       # Using author object
      id
      name
    }
    books(order_by: {position: asc}) {  # ❌ Different structure than search
      id
      title
      subtitle
      position
      published_year
      image
      authors {
        id
        name
      }
    }
  }
}
```

**Issues:**

1. ❌ **Endpoint not in official docs**
   - We're using `series_by_pk` which doesn't appear in the official documentation
   - We don't know if this is stable, deprecated, or subject to change
   - Field structure may differ from search results

2. ⚠️ **Books field structure differs**
   - In **search results**: `books` = array of strings (book titles)
   - In **series_by_pk**: `books` = array of complex objects (full book details)
   - This inconsistency is confusing and undocumented

3. ⚠️ **Author field assumption**
   - Recent fix (commit 2b7d9b3) changed from `author_name` string to `author` object
   - Fix was correct IF `series_by_pk` doesn't have `author_name` field
   - But we can't verify this against official docs since endpoint isn't documented

4. ⚠️ **No fallback to search endpoint**
   - If `series_by_pk` fails or is removed, we have no fallback
   - We could potentially reconstruct series books from repeated searches

---

## Discrepancies Found

### 1. Field Name Inconsistency: author_name vs author

**Official docs say:**
- Series search results have **BOTH** `author_name` (string) AND `author` (object)

**Our code assumes:**
- `search_series()`: Uses `author_name` ✅
- `list_series_books()`: Uses `author` object (extracted from undocumented endpoint) ⚠️

**Why this matters:**
- If `series_by_pk` endpoint changes or is removed, our code breaks
- We can't verify the fix against official documentation

### 2. Books Field Structure Difference

**In search results (documented):**
```json
"books": [
  "Harry Potter and the Sorcerer's Stone",
  "Harry Potter and the Chamber of Secrets",
  ...
]
```
- Array of strings (book titles only)
- Limited to top 5

**In series_by_pk (undocumented):**
```json
"books": [
  {
    "id": 123,
    "title": "...",
    "subtitle": "...",
    "position": 1,
    "authors": [...]
  },
  ...
]
```
- Array of complex objects
- Full details, ordered by position

**Issue:** These are completely different data structures with the same field name!

### 3. Unused Fields from Search Results

We're not using valuable data available in search results:
- `author` object (has id, image, slug)
- `books` array (could validate against expected titles)
- `slug` field (could be useful for URLs)

---

## Test Failure Analysis

### Actual Test Output (2025-11-17)

```
======================================================================
  Series Books Test: ID 997
======================================================================

📚 Fetching books for series ID 997...
❌ GraphQL errors: [{'message': "field 'books' not found in type: 'series'",
    'extensions': {'path': '$.selectionSet.series_by_pk.selectionSet.books',
                   'code': 'validation-failed'}}]
⚠️  Series 997 not found
❌ Series 997 not found
```

### 🚨 CRITICAL FINDING: The `books` field does NOT exist in `series_by_pk` query!

**Error message:** `"field 'books' not found in type: 'series'"`

This is the smoking gun. Our GraphQL query in `list_series_books()` tries to fetch:

```graphql
series_by_pk(id: $seriesId) {
  id
  name
  author { id, name }
  books(order_by: {position: asc}) {    # ❌ THIS FIELD DOESN'T EXIST!
    id
    title
    # ... etc
  }
}
```

**Root cause:**
1. ❌ The `series` type in `series_by_pk` query does **NOT** have a `books` field
2. ❌ We're trying to query a field that doesn't exist in the GraphQL schema
3. ⚠️ The `books` field DOES exist in search results, but with different structure (array of strings)
4. ⚠️ We have no documented way to get detailed book information for a series

**Previous fix (commit 2b7d9b3):**
- Changed `author_name` → `author` object ✅
- But didn't address the `books` field issue ❌

**Why we missed this:**
- The undocumented `series_by_pk` endpoint has different schema than search
- We assumed `books` would be available, but it's not
- Official docs only show `books` in search results (as strings, not objects)

---

## Recommendations

### 🚨 IMMEDIATE FIX REQUIRED

**The `list_series_books()` function is completely broken because:**
1. ❌ It queries a `books` field that doesn't exist in `series_by_pk`
2. ❌ We have no documented way to get book details for a series
3. ❌ The function will ALWAYS fail with validation error

**Three possible approaches:**

#### Option 1: Remove the `books` field from query (SIMPLEST)
```graphql
query GetSeriesBooks($seriesId: Int!) {
  series_by_pk(id: $seriesId) {
    id
    name
    author { id, name }
    # Remove books field entirely
  }
}
```
- Returns only series metadata (id, name, author)
- No book details available
- Function becomes essentially useless
- ❌ Defeats the purpose of `list_series_books()`

#### Option 2: Use ONLY the search endpoint (RECOMMENDED)
```graphql
query SearchSeries($query: String!) {
  search(query: $query, query_type: "Series") {
    results  # Contains: books (array of title strings)
  }
}
```
- Use the documented search endpoint
- Returns `books` field as array of strings (book titles)
- Limited to top 5 books
- No detailed book info (position, authors, etc.)
- ✅ Stable, documented API
- ⚠️ Less functionality

#### Option 3: Query books separately (COMPLEX, UNCERTAIN)
```graphql
# First get series info (without books)
query GetSeries($seriesId: Int!) {
  series_by_pk(id: $seriesId) {
    id
    name
    author { id, name }
  }
}

# Then search for books in that series (if such query exists?)
query SearchBooks($seriesId: Int!) {
  books(where: {series_id: {_eq: $seriesId}}) {
    id
    title
    # ...
  }
}
```
- Requires TWO API calls
- Second query structure is UNKNOWN (not documented)
- May not even exist
- More complex, more points of failure

### Immediate Actions (Before Fixing)

1. **Introspect the GraphQL schema** (if Hardcover allows it)
   ```graphql
   query IntrospectSeries {
     __type(name: "series") {
       fields {
         name
         type { name }
       }
     }
   }
   ```
   - Find out what fields ACTUALLY exist on `series` type
   - See if there's a different way to get books

2. **Check if books query exists separately**
   ```graphql
   query {
     __schema {
       queryType {
         fields {
           name
           description
         }
       }
     }
   }
   ```
   - List all available queries
   - See if there's a `books(where: ...)` query

### Short-term Fixes (Choose One)

#### ✅ RECOMMENDED: Pivot to search endpoint only

**Rationale:**
- Official docs ONLY document the search endpoint
- Search results include `books` field (as strings)
- Stable, supported API
- Simpler code, fewer points of failure

**Implementation:**
```python
async def list_series_books(self, series_id: int):
    """
    List books in a series using search endpoint.
    NOTE: Returns book titles only, limited to top 5.
    """
    # Step 1: Get series info via search
    # (We'd need to search by series name, which we may not have)
    # This approach has limitations!

    # Alternative: Store books from search_series() results
    # Don't make a separate call at all
```

**Limitations:**
- Only get book titles (strings), not full details
- Limited to top 5 books
- No position/ordering information
- May need to refactor how we use series data

#### ⚠️ ALTERNATIVE: Remove list_series_books() entirely

**If the function isn't critical:**
- Comment out or remove the broken function
- Update tests to skip it
- Use only search_series() for series discovery
- Accept that we can't get detailed book lists

**Impact:**
- Reduces functionality
- Simplifies codebase
- No dependency on undocumented endpoints
- Tests will pass

### Long-term Improvements

1. **Request official documentation from Hardcover**
   - Ask if `series_by_pk` is supported
   - Ask how to get book details for a series
   - Request GraphQL schema documentation

2. **Enhance search_series() to capture all available data**
   - Include `books` array (titles) from search results
   - Include `author` object (not just `author_name`)
   - Include `slug` and other metadata
   - Store this in cache for later use

3. **Consider book-centric approach**
   - Instead of "get books in series"
   - Do "search books by series name"
   - Use book search with series filter (if available)

---

## Critical Questions (ANSWERED)

### 1. Is `series_by_pk` a stable endpoint?
**Answer:** ❌ UNKNOWN - Not documented, and the schema is different from our expectations

- Not in official docs
- The `series` type doesn't have a `books` field
- Could be internal/unstable/deprecated
- Should NOT continue using it without documentation

### 2. Why do tests still fail after the fix?
**Answer:** ✅ IDENTIFIED - We're querying a field that doesn't exist!

- Error: `"field 'books' not found in type: 'series'"`
- The `author` fix was correct, but `books` field doesn't exist
- GraphQL validation fails before the query even executes
- Not an edge case - fundamental schema mismatch

### 3. Should we pivot to documented APIs only?
**Answer:** ✅ YES - Strongly recommended

- Official docs ONLY cover search endpoint
- Search endpoint is stable and supported
- `series_by_pk` is risky without documentation
- Better to have limited but reliable functionality

---

## Summary of Findings

### What We Got Right ✅

1. **search_series()** - Mostly correct implementation
   - Uses documented endpoint
   - Parses response structure correctly
   - Extracts author_name properly
   - Handles errors defensively

2. **Recent author fix** - Was necessary and correct
   - `series_by_pk` has `author` object, not `author_name` string
   - Extraction logic is sound

### What We Got Wrong ❌

1. **Using undocumented `series_by_pk` endpoint**
   - Not in official API docs
   - Schema assumptions were incorrect
   - No way to verify correctness

2. **Assuming `books` field exists in series_by_pk**
   - Field doesn't exist in the `series` type
   - Query fails with validation error
   - Makes `list_series_books()` completely broken

3. **Not capturing `books` from search results**
   - Search results include `books` array (titles)
   - We ignore this data
   - Could have used it instead of separate query

### Data Structure Inconsistencies

**Search endpoint** (documented):
```json
{
  "author_name": "Brandon Sanderson",  // ✅ String
  "author": { "id": 123, "name": "..." },  // ✅ Object
  "books": ["Book 1", "Book 2", ...]  // ✅ Array of strings
}
```

**series_by_pk endpoint** (undocumented):
```json
{
  "author_name": ???,  // ❌ Doesn't exist
  "author": { "id": 123, "name": "..." },  // ✅ Object (confirmed)
  "books": ???  // ❌ Doesn't exist!
}
```

---

## Final Recommendation

### 🎯 DECISION REQUIRED: Choose one approach

#### Option A: Remove `list_series_books()` function (SIMPLEST)
- Comment out the broken function
- Update test to skip it
- Use only `search_series()` for series discovery
- Accept limited book data (titles only, top 5)
- **Timeline:** 10 minutes
- **Risk:** Low

#### Option B: Refactor to use only search endpoint (BETTER)
- Enhance `search_series()` to return `books` array
- Remove `list_series_books()` or make it return cached search data
- Stick to documented APIs only
- **Timeline:** 1-2 hours
- **Risk:** Low

#### Option C: Introspect schema and find correct query (UNCERTAIN)
- Try GraphQL introspection to discover correct fields/queries
- May find a way to get book details
- May discover it's impossible
- **Timeline:** Unknown (2-4 hours of experimentation)
- **Risk:** Medium-High (may waste time if no solution exists)

### ✅ RECOMMENDED: Option B
Refactor to use documented search endpoint exclusively, enhance data capture to include books array from search results.

---

## Next Steps (DO NOT IMPLEMENT YET - WAIT FOR APPROVAL)

1. ✅ **Audit complete** - documented all findings
2. ⏸️ **Wait for user decision** - which option to implement?
3. ⏸️ **Implement chosen approach**
4. ⏸️ **Update tests to match new behavior**
5. ⏸️ **Verify all tests pass**

---

## Conclusion

The `list_series_books()` function is fundamentally broken because it queries a `books` field that doesn't exist in the `series_by_pk` endpoint. This endpoint is undocumented, and we made incorrect assumptions about its schema.

**The fix is NOT to modify the query** - the field simply doesn't exist.

**The real question is:** Do we need detailed book information, or can we work with the limited book data (titles only) available in the documented search endpoint?

**Audit Status:** ✅ COMPLETE - Ready for implementation decisions
