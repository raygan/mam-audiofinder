# Hardcover API Reference

This document provides a summary of the Hardcover API's public endpoints, focusing on their function and return formats.

## Unified Search Endpoint

The Hardcover API provides a single, unified search endpoint for accessing its data. It behaves similarly to a GraphQL query, allowing clients to specify the type of data to search, filtering criteria, and the desired return fields.

### `GET /api/search`

This is the primary endpoint for all search operations.

#### Parameters

| Name | Type | Description | Required |
|---|---|---|---|
| `q` | string | The search term. | Yes |
| `type` | string | The type of content to search for. Can be `book`, `author`, `list`, `user`, `character`, `publisher`, `series`, or `prompt`. Defaults to `book`. | No |
| `page` | integer | The page number for pagination. Defaults to `1`. | No |
| `per_page` | integer | The number of results to return per page. Defaults to `25`. | No |
| `sort` | string | A comma-separated list of fields to sort by, with direction (e.g., `_text_match:desc,books_count:desc`). | No |
| `fields` | string | A comma-separated list of attributes to search within for the given `type`. | No |
| `weights`| string | A comma-separated list of weights corresponding to the `fields` to prioritize certain attributes. | No |

---

### Return Format

The API returns a JSON object containing the search results and pagination details.

```json
{
  "query": "your search term",
  "query_type": "book",
  "page": 1,
  "per_page": 25,
  "ids": [
    "list of result IDs"
  ],
  "results": [
    {
      "id": "string",
      "title": "string",
      "pages": "number",
      "published_year": "number",
      "cover": "string (URL)",
      "authors": [
        {
          "id": "string",
          "name": "string"
        }
      ]
    }
  ]
}
```

### Search Types (`type`)

The behavior of the search endpoint and the structure of the objects in the `results` array depend on the `type` parameter.

#### `type=book` (Default)
- **Description:** Searches for books.
- **Default Search Fields:** `title`, `subtitle`, `series`, `author_names`, `description`
- **Result Object Fields:** `id`, `title`, `goodreads_id`, `pages`, `published_year`, `cover`, `authors`, and more.

#### `type=author`
- **Description:** Searches for authors.
- **Default Search Fields:** `name`, `name_personal`, `alternate_names`, `series_names`, `books`
- **Result Object Fields:** `id`, `name`, `goodreads_id`, `slug`, `image`, `books_count`, and more.

#### `type=list`
- **Description:** Searches for user-created lists.
- **Default Search Fields:** `name`, `user_name`, `description`
- **Result Object Fields:** `id`, `name`, `user_id`, `slug`, `description`, `entries_count`.

#### `type=user`
- **Description:** Searches for users.
- **Default Search Fields:** `name`, `username`
- **Result Object Fields:** `id`, `name`, `username`, `image`.

#### Other Types
The API also supports searching for `character`, `publisher`, `series`, and `prompt`, each with their own set of default fields and result structures.
