Below is a **fully formatted Markdown API reference** extracted from your text document.
Everything comes **directly from the file** you uploaded.
Citation included: 

---

# 📚 Hardcover API — Search Endpoint Documentation

*Extracted from uploaded file* 

## Overview

The Hardcover API provides a unified **search endpoint** for querying multiple entity types (books, authors, series, characters, lists, prompts, publishers, users).
Internally, Hardcover uses **Typesense** for search indexing.

> ⚠️ *The API is under development; changes may occur without notice.*

---

# 🔍 Search Endpoint

### **Endpoint**

```
search(query, query_type, per_page, page, sort, fields, weights)
```

### **Required Parameter**

| Name    | Type   | Description                 |
| ------- | ------ | --------------------------- |
| `query` | string | What you want to search for |

### **Optional Parameters**

| Name         | Type                    | Default            | Description                                                                            |
| ------------ | ----------------------- | ------------------ | -------------------------------------------------------------------------------------- |
| `query_type` | string                  | `"book"`           | One of: `author`, `book`, `character`, `list`, `prompt`, `publisher`, `series`, `user` |
| `per_page`   | int                     | `25`               | Results per page                                                                       |
| `page`       | int                     | `1`                | Page number                                                                            |
| `sort`       | string                  | *(varies by type)* | Attribute(s) to sort by                                                                |
| `fields`     | array                   | *(varies)*         | Which attributes to search within                                                      |
| `weights`    | comma-separated numbers | *(varies)*         | Weights corresponding to each `field`                                                  |

### Important Notes

* `fields` and `weights` **must** be used together and must have matching lengths.
* Some attributes are objects or numeric, so they may be more useful for sorting than searching.

---

# 📦 API Response Fields

The search endpoint always returns the following:

| Field        | Description                       |
| ------------ | --------------------------------- |
| `ids`        | Array of result IDs (ordered)     |
| `results`    | Array of Typesense result objects |
| `query`      | The query you passed              |
| `query_type` | The applied query type            |
| `page`       | Page number                       |
| `per_page`   | Number of results per page        |

---

# 🧑‍💼 AUTHOR SEARCH

### Available Author Fields

* `alternate_names`
* `books` (top 5)
* `books_count`
* `image`
* `name`
* `name_personal`
* `series_names`
* `slug`

### Default Settings for `query_type: author`

```
fields:  name, name_personal, alternate_names, series_names, books
sort:    _text_match:desc, books_count:desc
weights: 3,3,3,2,1
```

### Example Query

```graphql
query BooksByRowling {
    search(
        query: "rowling",
        query_type: "Author",
        per_page: 5,
        page: 1
    ) {
        results
    }
}
```

---

# 📘 BOOK SEARCH

### Available Book Fields

* `activities_count`
* `alternative_titles`
* `audio_seconds`
* `author_names`
* `compilation`
* `content_warnings` (top 5)
* `contribution_types`
* `contributions`
* `cover_color`
* `description`
* `featured_series`
* `featured_series_position`
* `genres` (top 5)
* `isbns`
* `lists_count`
* `has_audiobook`
* `has_ebook`
* `moods` (top 5)
* `pages`
* `prompts_count`
* `rating`
* `ratings_count`
* `release_date_i`
* `release_year`
* `reviews_count`
* `series_names`
* `slug`
* `subtitle`
* `tags`
* `title`
* `users_count`
* `users_read_count`

### Default Settings for `query_type: book`

```
fields:   title, isbns, series_names, author_names, alternative_titles
sort:     _text_match:desc, users_count:desc
weights:  5,5,3,1,1
```

---

# 📥 Example Book Search Query

```graphql
query LordOfTheRingsBooks {
    search(
        query: "lord of the rings",
        query_type: "Book",
        per_page: 5,
        page: 1
    ) {
        results
    }
}
```

### Example Response (Truncated)

The document includes a **large example response** containing full Typesense `hits`, metadata, and highlight objects.
(Extracted example shows `found: 112` results and several full book objects.) 

---

# 🧩 Supported Query Types

```
author
book
character
list
prompt
publisher
series
user
```

---

# 📓 Summary

✔ Single universal **search endpoint**
✔ Flexible ranking & sorting
✔ Supports advanced Typesense highlight & match info
✔ Detailed fields for both books and authors
✔ Full example GraphQL queries & responses included

---
