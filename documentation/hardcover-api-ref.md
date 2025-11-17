Below is a **fully formatted Markdown API reference** extracted from your text document.
Everything comes **directly from the file** you uploaded.
Citation included: 

---

# 📚 Hardcover API — Search Endpoint Documentation

*Extracted from official Hardcover documentation: [Searching.mdx](https://raw.githubusercontent.com/hardcoverapp/hardcover-docs/refs/heads/main/src/content/docs/api/guides/Searching.mdx)*

## Implementation Notes

**Our MAM Audiobook Finder implementation uses ONLY the documented search endpoint.**

### What We Use
- ✅ `search()` endpoint - Fully documented, stable, supported
- ✅ `series_by_pk()` endpoint - **Only for basic series metadata (id, name, author)**
  - We do NOT query the `books` field (it doesn't exist in the schema)
  - Used to get series name when we have an ID, then we search for books

### Important Limitations
- **Books information**: Limited to book titles only (strings), up to 5 books per series
- **No detailed book data**: Position, subtitle, publication year, authors not available via documented API
- **Series books**: Retrieved via search endpoint, not from `series_by_pk.books` (that field doesn't exist)

### Why This Approach
The `series_by_pk` endpoint's `books` field is not documented and does not exist in the GraphQL schema (confirmed via API errors). To maintain stability and use only documented APIs, we:
1. Use `series_by_pk` for basic series info only (id, name, author)
2. Use `search(query_type: "series")` to get books array (as title strings)
3. Accept the limitation of having only book titles, not full book details

---

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
```
{
  "search": {
    "results": {
      "facet_counts": [],
      "found": 118,
      "hits": [
        {
          "document": {
            "alternate_names": [
              "Joanne Rowling",
              "Joanne K. Rowling",
              "J.K.Rowling",
              "Rowling, J.K.",
              "J. Rowling",
              "Rowling, Joanne K.",
              "Jo Murray",
              "J K Rowling",
              "Rowling J.K.",
              "J.K. Rowling (author)",
              "Rowling Joanne",
              "J.K. Rowling",
              "J.K. ROWLING",
              "Rowling J K",
              "J K ROWLING",
              "Newt Scamander",
              "JOANNE K. ROWLING",
              "Kennilworthy Whisp",
              "JK Rowling",
              "JK Rowlings",
              "jk rowling",
              "R.K Rowling",
              "J. K Rowling",
              "J.K Rowling",
              "Rowling J. K.",
              "J. K. Rowling (Auteur)",
              "J.k. Rowling",
              "Rowling, J. K."
            ],
            "books": [
              "Harry Potter and the Sorcerer's Stone",
              "Harry Potter and the Chamber of Secrets",
              "Harry Potter and the Prisoner of Azkaban",
              "Harry Potter and the Goblet of Fire",
              "Harry Potter and the Order of the Phoenix"
            ],
            "books_count": 116,
            "id": "80626",
            "image": {
              "color": "#eed8ce",
              "color_name": "Silver",
              "height": 461,
              "id": 31962,
              "url": "https://assets.hardcover.app/authors/80626/5543033-L.jpg",
              "width": 468
            },
            "name": "J.K. Rowling",
            "series_names": [
              "Harry Potter Korean Split-Volume Paperback",
              "Wizarding World",
              "Happy Potter",
              "הארי פוטר",
              "Pottermore Presents",
              "Uit de Schoolbibliotheek van Zweinstein",
              "Harry Potter #1",
              "From the Wizarding Archive",
              "Harry Potter Japanese Split-Volume Children's Edition",
              "Harry Potter",
              "Pottermore presenta",
              "Harry Potter, #5",
              "Harry Potter si Pocalul de Foc.",
              "La colección de Harry Potter",
              "Fantastic Beasts and Where to Find Them",
              "Гарри Поттер",
              "Hogwarts Library Books",
              " Wizarding World",
              "Хари Потър",
              "Harry Potter and the Sorcerer's Stone: Minalima Edition (Harry Potter, Book 1)",
              "Harry Potter si prizonierul din Azkaban.",
              "Harry potter",
              "Harry Potter si Piatra Filosofala.",
              "Fantastic Beasts: The Original Screenplay",
              "PottermorePresents",
              "Harry Potter-serien",
              "La série de livres Harry Potter",
              "Harry Potter and the Half-Blood Prince",
              "Harry Potter and the Cursed Child: Parts One and Two",
              "The Ickabog",
              "Harry Potter and the Philosopher’s Stone",
              "Harry Potter and the Chamber of Secrets",
              "Harry Potter and the Prisoner of Azkaban",
              "Harry Potter and the Goblet of Fire",
              "Harry Potter and the Order of the Phoenix",
              "Harry Potter and the Deathly Hallows",
              "The Christmas Pig",
              "Hogwarts Library",
              "Harry Potter-sarjan",
              "Harry Potter"
            ],
            "slug": "jk-rowling-1965"
          },
          "highlight": {
            "alternate_names": [
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "Joanne <mark>Rowling</mark>"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "Joanne K. <mark>Rowling</mark>"
              },
              {
                "matched_tokens": [],
                "snippet": "J.K.Rowling"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "<mark>Rowling</mark>, J.K."
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "J. <mark>Rowling</mark>"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "<mark>Rowling</mark>, Joanne K."
              },
              {
                "matched_tokens": [],
                "snippet": "Jo Murray"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "J K <mark>Rowling</mark>"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "<mark>Rowling</mark> J.K."
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "J.K. <mark>Rowling</mark> (author)"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "<mark>Rowling</mark> Joanne"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "J.K. <mark>Rowling</mark>"
              },
              {
                "matched_tokens": [
                  "ROWLING"
                ],
                "snippet": "J.K. <mark>ROWLING</mark>"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "<mark>Rowling</mark> J K"
              },
              {
                "matched_tokens": [
                  "ROWLING"
                ],
                "snippet": "J K <mark>ROWLING</mark>"
              },
              {
                "matched_tokens": [],
                "snippet": "Newt Scamander"
              },
              {
                "matched_tokens": [
                  "ROWLING"
                ],
                "snippet": "JOANNE K. <mark>ROWLING</mark>"
              },
              {
                "matched_tokens": [],
                "snippet": "Kennilworthy Whisp"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "JK <mark>Rowling</mark>"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "JK <mark>Rowling</mark>s"
              },
              {
                "matched_tokens": [
                  "rowling"
                ],
                "snippet": "jk <mark>rowling</mark>"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "R.K <mark>Rowling</mark>"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "J. K <mark>Rowling</mark>"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "J.K <mark>Rowling</mark>"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "<mark>Rowling</mark> J. K."
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "J. K. <mark>Rowling</mark> (Auteur)"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "J.k. <mark>Rowling</mark>"
              },
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "<mark>Rowling</mark>, J. K."
              }
            ],
            "name": {
              "matched_tokens": [
                "Rowling"
              ],
              "snippet": "J.K. <mark>Rowling</mark>"
            }
          },
          "highlights": [
            {
              "field": "name",
              "matched_tokens": [
                "Rowling"
              ],
              "snippet": "J.K. <mark>Rowling</mark>"
            },
            {
              "field": "alternate_names",
              "indices": [
                0,
                1,
                3,
                4,
                5
              ],
              "matched_tokens": [
                [
                  "Rowling"
                ],
                [
                  "Rowling"
                ],
                [
                  "Rowling"
                ],
                [
                  "Rowling"
                ],
                [
                  "Rowling"
                ]
              ],
              "snippets": [
                "Joanne <mark>Rowling</mark>",
                "Joanne K. <mark>Rowling</mark>",
                "<mark>Rowling</mark>, J.K.",
                "J. <mark>Rowling</mark>",
                "<mark>Rowling</mark>, Joanne K."
              ]
            }
          ],
          "text_match": 578730123365187600,
          "text_match_info": {
            "best_field_score": "1108091338752",
            "best_field_weight": 3,
            "fields_matched": 2,
            "num_tokens_dropped": 0,
            "score": "578730123365187610",
            "tokens_matched": 1,
            "typo_prefix_score": 0
          }
        },
        {
          "document": {
            "alternate_names": [],
            "books": [
              "Art"
            ],
            "books_count": 1,
            "id": "133870",
            "image": {
              "color": "#ebede1",
              "color_name": "Beige",
              "height": 500,
              "id": 162685,
              "url": "https://assets.hardcover.app/books/133870/8014974-L.jpg",
              "width": 292
            },
            "name": "Nick Rowling",
            "name_personal": "Nick Rowling",
            "series_names": [],
            "slug": "nick-rowling"
          },
          "highlight": {
            "name": {
              "matched_tokens": [
                "Rowling"
              ],
              "snippet": "Nick <mark>Rowling</mark>"
            },
            "name_personal": {
              "matched_tokens": [
                "Rowling"
              ],
              "snippet": "Nick <mark>Rowling</mark>"
            }
          },
          "highlights": [
            {
              "field": "name",
              "matched_tokens": [
                "Rowling"
              ],
              "snippet": "Nick <mark>Rowling</mark>"
            },
            {
              "field": "name_personal",
              "matched_tokens": [
                "Rowling"
              ],
              "snippet": "Nick <mark>Rowling</mark>"
            }
          ],
          "text_match": 578730123365187600,
          "text_match_info": {
            "best_field_score": "1108091338752",
            "best_field_weight": 3,
            "fields_matched": 2,
            "num_tokens_dropped": 0,
            "score": "578730123365187610",
            "tokens_matched": 1,
            "typo_prefix_score": 0
          }
        },
        {
          "document": {
            "alternate_names": [],
            "books": [
              "QualityLand",
              "Die Känguru-Chroniken",
              "QualityLand 2.0",
              "Das Känguru-Manifest",
              "Die Känguru-Offenbarung"
            ],
            "books_count": 33,
            "id": "239801",
            "image": {
              "color": "#515151",
              "color_name": "Gray",
              "height": 200,
              "id": 35911,
              "url": "https://assets.hardcover.app/authors/239801/7314387-L.jpg",
              "width": 200
            },
            "name": "Marc-Uwe Kling",
            "name_personal": "Joanne K. Rowling",
            "series_names": [
              "QualityLand",
              "Die Känguru-Comics",
              "Neinhorn",
              "Die Känguru-Chroniken"
            ],
            "slug": "marc-uwe-kling"
          },
          "highlight": {
            "name": {
              "matched_tokens": [],
              "snippet": "Marc-Uwe Kling"
            },
            "name_personal": {
              "matched_tokens": [
                "Rowling"
              ],
              "snippet": "Joanne K. <mark>Rowling</mark>"
            }
          },
          "highlights": [
            {
              "field": "name_personal",
              "matched_tokens": [
                "Rowling"
              ],
              "snippet": "Joanne K. <mark>Rowling</mark>"
            }
          ],
          "text_match": 578730123365187600,
          "text_match_info": {
            "best_field_score": "1108091338752",
            "best_field_weight": 3,
            "fields_matched": 1,
            "num_tokens_dropped": 0,
            "score": "578730123365187609",
            "tokens_matched": 1,
            "typo_prefix_score": 0
          }
        },
        {
          "document": {
            "alternate_names": [
              "J. K. Rowling"
            ],
            "books": [
              "The Cuckoo's Calling",
              "The Silkworm",
              "Career of Evil",
              "Lethal White",
              "Troubled Blood"
            ],
            "books_count": 16,
            "id": "200048",
            "image": {
              "color": "#a66961",
              "color_name": "Gray",
              "height": 1000,
              "id": 6010702,
              "url": "https://assets.hardcover.app/author/200048/009f764c-36d3-4ce1-a57e-51ee462fb05f.jpg",
              "width": 667
            },
            "name": "Robert Galbraith",
            "name_personal": "Robert Galbraith",
            "series_names": [
              "Корморан Страйк",
              "A Cormoran Strike Novel #6",
              "4",
              "Cormoran Strike",
              "A Cormoran Strike Novel",
              "קורמורן סטרייק",
              "A Cormoran Strike Novel #7",
              "En Cormoran Strike-roman",
              "cormoran strike"
            ],
            "slug": "robert-galbraith"
          },
          "highlight": {
            "alternate_names": [
              {
                "matched_tokens": [
                  "Rowling"
                ],
                "snippet": "J. K. <mark>Rowling</mark>"
              }
            ]
          },
          "highlights": [
            {
              "field": "alternate_names",
              "indices": [
                0
              ],
              "matched_tokens": [
                [
                  "Rowling"
                ]
              ],
              "snippets": [
                "J. K. <mark>Rowling</mark>"
              ]
            }
          ],
          "text_match": 578730123365187600,
          "text_match_info": {
            "best_field_score": "1108091338752",
            "best_field_weight": 3,
            "fields_matched": 1,
            "num_tokens_dropped": 0,
            "score": "578730123365187609",
            "tokens_matched": 1,
            "typo_prefix_score": 0
          }
        },
        {
          "document": {
            "alternate_names": [],
            "books": [
              "The Western Herbal Tradition: 2000 Years of Medicinal Plant Knowledge",
              "All Year Round: Christian Calendar of Celebrations"
            ],
            "books_count": 2,
            "id": "661650",
            "image": {},
            "name": "Marije Rowling",
            "series_names": [],
            "slug": "marije-rowling"
          },
          "highlight": {
            "name": {
              "matched_tokens": [
                "Rowling"
              ],
              "snippet": "Marije <mark>Rowling</mark>"
            }
          },
          "highlights": [
            {
              "field": "name",
              "matched_tokens": [
                "Rowling"
              ],
              "snippet": "Marije <mark>Rowling</mark>"
            }
          ],
          "text_match": 578730123365187600,
          "text_match_info": {
            "best_field_score": "1108091338752",
            "best_field_weight": 3,
            "fields_matched": 1,
            "num_tokens_dropped": 0,
            "score": "578730123365187609",
            "tokens_matched": 1,
            "typo_prefix_score": 0
          }
        }
      ],
      "out_of": 1173083,
      "page": 1,
      "request_params": {
        "collection_name": "Author_production_1760909157",
        "first_q": "rowling",
        "per_page": 5,
        "q": "rowling"
      },
      "search_cutoff": false,
      "search_time_ms": 4
    }
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
```
{
  "search": {
    "results": {
      "facet_counts": [],
      "found": 112,
      "hits": [
        {
          "document": {
            "activities_count": 0,
            "alternative_titles": [
              "Lord of the Rings"
            ],
            "author_names": [
              "Jane Chance"
            ],
            "compilation": false,
            "content_warnings": [],
            "contribution_types": [
              "Author"
            ],
            "contributions": [
              {
                "author": {
                  "id": 296597,
                  "image": {
                    "color": "#495d30",
                    "color_name": "Brown",
                    "height": 500,
                    "id": 323187,
                    "url": "https://assets.hardcover.app/books/296597/6804366-L.jpg",
                    "width": 446
                  },
                  "name": "Jane Chance",
                  "slug": "jane-chance"
                },
                "contribution": null
              }
            ],
            "cover_color": "Beige",
            "description": "\" With New Line Cinema's production of The Lord of the Rings film trilogy, the popularity of the works of J.R.R. Tolkien is unparalleled. Tolkien’s books continue to be bestsellers decades after their original publication. An epic in league with those of Spenser and Malory, The Lord of the Rings trilogy, begun during Hitler’s rise to power, celebrates the insignificant individual as hero in the modern world. Jane Chance’s critical appraisal of Tolkien’s heroic masterwork is the first to explore its “mythology of power”–that is, how power, politics, and language interact. Chance looks beyond the fantastic, self-contained world of Middle-earth to the twentieth-century parallels presented in the trilogy.",
            "featured_series": {},
            "genres": [],
            "has_audiobook": false,
            "has_ebook": false,
            "id": "510077",
            "image": {
              "color": "#d1d4d5",
              "color_name": "Beige",
              "height": 198,
              "id": 857634,
              "url": "https://assets.hardcover.app/external_data/59536021/a4d1692cd315c91310a7d29fee4c3221b1c71d78.jpeg",
              "width": 128
            },
            "isbns": [
              "0813138019",
              "9780813138015",
              "0813128056",
              "9780813128054"
            ],
            "lists_count": 0,
            "moods": [],
            "pages": 184,
            "prompts_count": 0,
            "rating": 0,
            "ratings_count": 0,
            "release_date": "2010-09-12",
            "release_year": 2010,
            "reviews_count": 0,
            "series_names": [],
            "slug": "lord-of-the-rings-2010",
            "tags": [],
            "title": "Lord of the Rings",
            "users_count": 0,
            "users_read_count": 0
          },
          "highlight": {
            "alternative_titles": [
              {
                "matched_tokens": [
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              }
            ],
            "title": {
              "matched_tokens": [
                "Lord",
                "of",
                "the",
                "Rings"
              ],
              "snippet": "<mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
            }
          },
          "highlights": [
            {
              "field": "title",
              "matched_tokens": [
                "Lord",
                "of",
                "the",
                "Rings"
              ],
              "snippet": "<mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
            },
            {
              "field": "alternative_titles",
              "indices": [
                0
              ],
              "matched_tokens": [
                [
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ]
              ],
              "snippets": [
                "<mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              ]
            }
          ],
          "text_match": 2314894167593451500,
          "text_match_info": {
            "best_field_score": "4419510927616",
            "best_field_weight": 5,
            "fields_matched": 2,
            "num_tokens_dropped": 0,
            "score": "2314894167593451562",
            "tokens_matched": 4,
            "typo_prefix_score": 0
          }
        },
        {
          "document": {
            "activities_count": 1087,
            "alternative_titles": [
              "The Lord of the Rings",
              "Il Signore degli Anelli",
              "Der Herr der Ringe - 3 Bände im Schuber. Die Gefährten - Die zwei Türme - Die Rückkehr des Königs",
              "El Señor de los Anillos - Apéndices",
              "Le Seigneur des Anneaux - L'intégrale",
              "Lord Of The Rings - One Volume Edition",
              "O Senhor dos Anéis",
              "O Senhor dos Anéis: 3 Volumes",
              "Ringdrotten",
              "Il Signore degli Anelli: Trilogia",
              "In de Ban van de Ring",
              "In de ban van de ring-trilogie",
              "Taru Sormusten herrasta",
              "Il signore degli anelli",
              "L'Infirmerie après les cours, Tome 1",
              "Le Seigneur des Anneaux, Intégrale :",
              "Le Seigneur des Anneaux",
              "Der Herr Der Ringe",
              "Władca Pierścieni. Trylogia",
              "Taru sormusten herrasta",
              "The Lord of The Rings",
              "Le Seigneur des Anneaux Intégrale",
              "Sagan om ringen",
              "Israel 201: Your Next-Level Guide to the Magic, Mystery, and Chaos of Life in the Holy Land",
              "Trilogía El Señor de los Anillos",
              "Władca pierścieni",
              "El señor de los anillos",
              "El Señor de los Anillos",
              "Sagan om Ringen: Härskarringen",
              "El Senor De Los Anillos (3 Volumes) I, Ii & Iii   La Cumunidad Del Anillo, Las Dos Torres, El Retorno Del Rey",
              "The Lord of the Rings ",
              "The Lord of the Rings Trilogy",
              "The Lord of the Rings Box Set",
              "The Lord Of The Rings: One Volume",
              "",
              "The Lord of the Rings. [Comprising The Fellowship of the Ring [with] The Two Towers [with] The Return of the King]. FIRST PAPERBACK EDITION. FIRST SINGLE-VOLUME EDITION",
              "J.R.R.Tolkien's Lord of the Rings",
              "Yüzüklerin Efendisi",
              "The Lord of the Rings by Tolkien, J.R.R..",
              "THE LORD OF THE RINGS: Book (1) One: The Fellowship of the Ring; Book (2) Two: The Two Towers; Book (3) Three: The Return of the King - Collector's Edition",
              "Lord of the Rings: The Fellowship of the Ring, The Two Towers, The Return of the King",
              "Der Herr der Ringe: In der Übersetzung von Margaret Carroux",
              "The Lord of the Rings Millennium Edition Boxed Set",
              "Spoločenstvo prsteňa",
              "Władca Pierścieni",
              "The Lord of Rings",
              "The lord of the rings",
              "新版指輪物語: 旅の仲間　上1",
              "Härskarringen",
              "The Fellowship of the Ring",
              "新版指輪物語: 王の帰還　上",
              "Shinpan yubiwa monogatari",
              "Lord of the Rings Trilogy Produced By the Mind's Eye Audio Cassette",
              "Der Herr der Ringe.",
              "The Lord of the Rings Performed by J.R.R. Tolkien",
              "The lord of the rings.",
              "The Lord of the Rings Boxed Set",
              "Lord of the Rings",
              "Vlastelin Kolets",
              "Властелин колец",
              "The Complete Lord of the Rings Trilogy",
              "Povestʹ o kolʹt︠s︡e",
              "Der Herr der Ringe",
              "Der Herr der Ringe: Die Gefährten / Die zwei Türme / Die Rückkehr des Königs",
              "Společentvo prstenu",
              "Illustrated Lord of the Rings Trilogy",
              "El senor de los anillos.",
              "Las Dos Torres",
              "The Lord Of The Rings",
              "Le Seigneur DES Anneaux",
              "Le Seigneur des Anneaux, 3 Volume Boxed Set Containing\" La Communeaute de l'Anneau; Les Deux Tours; Le retour du Roi: French Edition of Lord of the Rings, Containing",
              "The Lord of the Rings - Phil Dragash - Spotify",
              "The Lord of the Rings: Boxed Set",
              "Il Signore degli Anelli : Trilogia / Italian edition of The Lord of the Rings",
              "Возвращение короля",
              "La Comunidad del Anillo",
              "The Hobbit / The Lord of the Rings",
              "O señor dos aneis",
              "Властелин Колец",
              "The Lord of the Rings Illustrated"
            ],
            "author_names": [
              "J.R.R. Tolkien"
            ],
            "compilation": true,
            "content_warnings": [
              "war",
              "death",
              "Alcohol",
              "Grief",
              "Blood",
              "Animal cruelty",
              "Violence"
            ],
            "contribution_types": [
              "Author"
            ],
            "contributions": [
              {
                "author": {
                  "id": 132049,
                  "image": {
                    "color": "#5a5a5a",
                    "color_name": "Gray",
                    "height": 266,
                    "id": 33205,
                    "url": "https://assets.hardcover.app/authors/132049/6155606-L.jpg",
                    "width": 187
                  },
                  "name": "J.R.R. Tolkien",
                  "slug": "j-r-r-tolkien"
                },
                "contribution": null
              }
            ],
            "cover_color": "Purple",
            "description": "Originally published from 1954 through 1956, J.R.R. Tolkien's richly complex series ushered in a new age of epic adventure storytelling. A philologist and illustrator who took inspiration from his work, Tolkien invented the modern heroic quest novel from the ground up, creating not just a world, but a domain, not just a lexicon, but a language, that would spawn countless imitators and lead to the inception of the epic fantasy genre. Today, THE LORD OF THE RINGS is considered \"the most influential fantasy novel ever written.\" (THE ENCYCLOPEDIA OF FANTASY)\n\nDuring his travels across Middle-earth, the hobbit Bilbo Baggins had found the Ring. But the simple band of gold was far from ordinary; it was in fact the One Ring - the greatest of the ancient Rings of Power. Sauron, the Dark Lord, had infused it with his own evil magic, and when it was lost, he was forced to flee into hiding.\n\nBut now Sauron's exile has ended and his power is spreading anew, fueled by the knowledge that his treasure has been found. He has gathered all the Great Rings to him, and will stop at nothing to reclaim the One that will complete his dominion. The only way to stop him is to cast the Ruling Ring deep into the Fire-Mountain at the heart of the land of Mordor--Sauron's dark realm.\n\nFate has placed the burden in the hands of Frodo Baggins, Bilbo's heir...and he is resolved to bear it to its end. Or his own.",
            "featured_series": {
              "details": "1-3",
              "featured": true,
              "id": 3041,
              "position": 1,
              "series": {
                "books_count": 4,
                "id": 1130,
                "name": "The Lord of the Rings",
                "primary_books_count": 3,
                "slug": "the-lord-of-the-rings"
              },
              "unreleased": false
            },
            "featured_series_position": 1,
            "genres": [
              "Fantasy",
              "Fiction",
              "General",
              "Epic",
              "Classics",
              "Science fiction",
              "Baggins",
              "History",
              "War",
              "Adventure"
            ],
            "has_audiobook": true,
            "has_ebook": true,
            "id": "377938",
            "image": {
              "color": "#252a42",
              "color_name": "Purple",
              "height": 500,
              "id": 2168780,
              "url": "https://assets.hardcover.app/external_data/41547254/141872f0e71efe38f937b72879a5dea52e502db5.jpeg",
              "width": 333
            },
            "isbns": [
              "0261103252",
              "883010471X",
              "9788830104716",
              "8439597495",
              "9788439597490",
              "9782266286",
              "8595086354",
              "9788595086357",
              "8533613407",
              "9788533613409",
              "8900007580",
              "9788900007589",
              "8205365598",
              "9788205365599",
              "9027462712",
              "9789027462718",
              "9402304029",
              "9789402304022",
              "9789510499399",
              "9788845269707",
              "8830119008",
              "9788830119000",
              "9780544003",
              "2849651303",
              "9782849651308",
              "0618640150",
              "9780618640157",
              "2266286269",
              "9782266286268",
              "2266201727",
              "9782266201728",
              "8858705823",
              "9788858705827",
              "9780048232298",
              "9780007149148",
              "0261103253",
              "9780261103252",
              "0007124015",
              "9780007124015",
              "0048232009",
              "9780048232007",
              "0618260242",
              "9780618260249",
              "3608936394",
              "9783608936391",
              "9780618260584",
              "8377584557",
              "9788377584552",
              "9510333379",
              "9789510333372",
              "0044406797",
              "9780044406792",
              "9780345339710",
              "0061952877",
              "9780061952876",
              "0739409557",
              "9780739409558",
              "9782267050356",
              "9172632186",
              "9789172632189",
              "9657801281",
              "9789657801284",
              "8445001280",
              "838553511X",
              "9788385535119",
              "844500302X",
              "9788445003022",
              "9113011200",
              "9789113011202",
              "0544273443",
              "9780544273443",
              "0618260250",
              "9780618260256",
              "0618260293",
              "9780618260294",
              "0007136587",
              "9780007136582",
              "8435002012",
              "9788435002011",
              "0261102419",
              "9780261102415",
              "0261103202",
              "034524222X",
              "9780345242228",
              "0618153977",
              "9780618153978",
              "8422690306",
              "9788422690306",
              "9780261103870",
              "0618343997",
              "9780618343997",
              "8533614942",
              "9788533614949",
              "0261103873",
              "9780547890586",
              "0618129014",
              "9780618129010",
              "0395308550",
              "9780395308554",
              "0618037667",
              "9780618037667",
              "8071456063",
              "9788071456063",
              "8445073753",
              "9788445073759",
              "9788377582558",
              "0345214528",
              "9780345214522",
              "9784566023628",
              "9113012436",
              "9789113012438",
              "8818123211",
              "9788818123210",
              "8533615167",
              "9788533615168",
              "0395489318",
              "9780395489314",
              "4566023621",
              "9784566023697",
              "0008471290",
              "9780008471293",
              "0358653037",
              "9780358653035",
              "8845290050",
              "9788845290053",
              "8845292614",
              "9788845292613",
              "0063274736",
              "9780063274730",
              "0007273509",
              "9780007273508",
              "0008501319",
              "9780008501310",
              "0395489326",
              "9780395489321",
              "0618129022",
              "9780618129027",
              "360895855X",
              "9783608958553",
              "0898452236",
              "9780898452235",
              "0395272203",
              "9780395272206",
              "0395974682",
              "9780395974681",
              "9027481970",
              "9789027481979",
              "0553472283",
              "9780553472288",
              "0618346244",
              "9780618346240",
              "8445070320",
              "9788445070321",
              "0007525540",
              "9780007525546",
              "006191780X",
              "9780061917806",
              "9788845210273",
              "0544003411",
              "9780544003415",
              "9780007322596",
              "0807286087",
              "9780807286081",
              "0007203632",
              "9780007203635",
              "0553456539",
              "9780553456530",
              "9780261103207",
              "5170186150",
              "5040081766",
              "9785040081769",
              "2267013169",
              "9782267013160",
              "0007182368",
              "9780007182367",
              "0618401210",
              "9780618401215",
              "9781611748864",
              "004823091X",
              "9780048230911",
              "0618153969",
              "9780618153961",
              "5710000612",
              "0547951949",
              "9780547951942",
              "2266127454",
              "9782266127455",
              "5170188455",
              "9785170188451",
              "0261102303",
              "9780261102309",
              "3608932224",
              "9783608932225",
              "0007123817",
              "9780007123810",
              "0395193958",
              "9780395193952",
              "0618574999",
              "9780618574995",
              "3895840432",
              "9783895840432",
              "0618645616",
              "9780618645619",
              "2267011255",
              "9782267011258",
              "160283492X",
              "9781602834927",
              "0261102389",
              "9780261102385",
              "8845294773",
              "9788845294778",
              "1565115503",
              "9781565115507",
              "8533619626",
              "9788533619623",
              "0007149247",
              "9780007149247",
              "360895211X",
              "9783608952117",
              "951013208X",
              "9789510132081",
              "0007149131",
              "9780007149131",
              "0007172001",
              "9780007172009",
              "8020409262",
              "9788020409263",
              "3608935444",
              "9783608935448",
              "8422616335",
              "9788422616337",
              "0785918698",
              "9780785918691",
              "0261102958",
              "9780261102958",
              "0395595118",
              "9780395595114",
              "0007581149",
              "9780007581146",
              "0606305645",
              "9780606305648",
              "0261102346",
              "9780261102347",
              "2266032488",
              "9782266032483",
              "004823091x",
              "9780358439196",
              "0048230871",
              "9780048230874",
              "0739408259",
              "9780739408254",
              "0828818126",
              "9780828818124",
              "0586215751",
              "9780586215753",
              "000748836X",
              "9780007488360",
              "1559351209",
              "9781559351201",
              "0828867666",
              "9780828867665",
              "1402516274",
              "9781402516276",
              "274414777X",
              "9782744147777",
              "8445071793",
              "9788445071793",
              "8818123696",
              "9788818123692",
              "5768402128",
              "9785768402129",
              "8445070339",
              "9788445070338",
              "0586218696",
              "9780586218693",
              "1402505205",
              "9781402505201",
              "841688417X",
              "9788416884179",
              "0618260587",
              "0048231495",
              "9780048231499",
              "5352003124",
              "9785352003121",
              "0007489978",
              "9780007489978",
              "0261102435",
              "9780261102439",
              "360896035X",
              "9783608960358",
              "0358623405",
              "9780358623403",
              "039564738X",
              "0618517650",
              "9780618517657",
              "2070544338",
              "9782070544332"
            ],
            "lists_count": 678,
            "moods": [
              "Adventurous",
              "inspiring",
              "emotional",
              "hopeful",
              "challenging",
              "lighthearted",
              "sad",
              "nostalgic",
              "gripping",
              "Light-hearted"
            ],
            "pages": 1178,
            "prompts_count": 10,
            "rating": 4.550712489522213,
            "ratings_count": 1193,
            "release_date": "1954-01-01",
            "release_year": 1954,
            "reviews_count": 35,
            "series_names": [
              "The Lord of the Rings"
            ],
            "slug": "the-lord-of-the-rings",
            "subtitle": "The Fellowship of the Ring, The Two Towers, The Return of the King",
            "tags": [
              "Loveable Characters",
              "A mix driven",
              "Strong Character Development",
              "Diverse Characters",
              "Not Diverse Characters",
              "Weak Character Development",
              "Adapted to Film",
              "classic",
              "adventurous",
              "Fellowship"
            ],
            "title": "The Lord of the Rings",
            "users_count": 2732,
            "users_read_count": 1881
          },
          "highlight": {
            "alternative_titles": [
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              },
              {
                "matched_tokens": [],
                "snippet": "Il Signore degli Anelli"
              },
              {
                "matched_tokens": [],
                "snippet": "Der Herr der Ringe - 3 Bände im Schuber. Die Gefährten - Die zwei Türme - Die Rückkehr des Königs"
              },
              {
                "matched_tokens": [],
                "snippet": "El Señor de los Anillos - Apéndices"
              },
              {
                "matched_tokens": [],
                "snippet": "Le Seigneur des Anneaux - L'intégrale"
              },
              {
                "matched_tokens": [
                  "Lord",
                  "Of",
                  "The",
                  "Rings"
                ],
                "snippet": "<mark>Lord</mark> <mark>Of</mark> <mark>The</mark> <mark>Rings</mark> - One Volume Edition"
              },
              {
                "matched_tokens": [],
                "snippet": "O Senhor dos Anéis"
              },
              {
                "matched_tokens": [],
                "snippet": "O Senhor dos Anéis: 3 Volumes"
              },
              {
                "matched_tokens": [],
                "snippet": "Ringdrotten"
              },
              {
                "matched_tokens": [],
                "snippet": "Il Signore degli Anelli: Trilogia"
              },
              {
                "matched_tokens": [],
                "snippet": "In de Ban van de Ring"
              },
              {
                "matched_tokens": [],
                "snippet": "In de ban van de ring-trilogie"
              },
              {
                "matched_tokens": [],
                "snippet": "Taru Sormusten herrasta"
              },
              {
                "matched_tokens": [],
                "snippet": "Il signore degli anelli"
              },
              {
                "matched_tokens": [],
                "snippet": "L'Infirmerie après les cours, Tome 1"
              },
              {
                "matched_tokens": [],
                "snippet": "Le Seigneur des Anneaux, Intégrale :"
              },
              {
                "matched_tokens": [],
                "snippet": "Le Seigneur des Anneaux"
              },
              {
                "matched_tokens": [],
                "snippet": "Der Herr Der Ringe"
              },
              {
                "matched_tokens": [],
                "snippet": "Władca Pierścieni. Trylogia"
              },
              {
                "matched_tokens": [],
                "snippet": "Taru sormusten herrasta"
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "The",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>The</mark> <mark>Rings</mark>"
              },
              {
                "matched_tokens": [],
                "snippet": "Le Seigneur des Anneaux Intégrale"
              },
              {
                "matched_tokens": [],
                "snippet": "Sagan om ringen"
              },
              {
                "matched_tokens": [
                  "the",
                  "of",
                  "the"
                ],
                "snippet": "Israel 201: Your Next-Level Guide to <mark>the</mark> Magic, Mystery, and Chaos <mark>of</mark> Life in <mark>the</mark> Holy Land"
              },
              {
                "matched_tokens": [],
                "snippet": "Trilogía El Señor de los Anillos"
              },
              {
                "matched_tokens": [],
                "snippet": "Władca pierścieni"
              },
              {
                "matched_tokens": [],
                "snippet": "El señor de los anillos"
              },
              {
                "matched_tokens": [],
                "snippet": "El Señor de los Anillos"
              },
              {
                "matched_tokens": [],
                "snippet": "Sagan om Ringen: Härskarringen"
              },
              {
                "matched_tokens": [],
                "snippet": "El Senor De Los Anillos (3 Volumes) I, Ii & Iii   La Cumunidad Del Anillo, Las Dos Torres, El Retorno Del Rey"
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> "
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> Trilogy"
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> Box Set"
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "Of",
                  "The",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>Of</mark> <mark>The</mark> <mark>Rings</mark>: One Volume"
              },
              {
                "matched_tokens": [],
                "snippet": ""
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings",
                  "The",
                  "of",
                  "the",
                  "The",
                  "The",
                  "of",
                  "the"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>. [Comprising <mark>The</mark> Fellowship <mark>of</mark> <mark>the</mark> Ring [with] <mark>The</mark> Two Towers [with] <mark>The</mark> Return <mark>of</mark> <mark>the</mark> King]. FIRST PAPERBACK EDITION. FIRST SINGLE-VOLUME EDITION"
              },
              {
                "matched_tokens": [
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "J.R.R.Tolkien's <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              },
              {
                "matched_tokens": [],
                "snippet": "Yüzüklerin Efendisi"
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> by Tolkien, J.R.R.."
              },
              {
                "matched_tokens": [
                  "THE",
                  "LORD",
                  "OF",
                  "THE",
                  "RINGS",
                  "The",
                  "of",
                  "the",
                  "The",
                  "The",
                  "of",
                  "the"
                ],
                "snippet": "<mark>THE</mark> <mark>LORD</mark> <mark>OF</mark> <mark>THE</mark> <mark>RINGS</mark>: Book (1) One: <mark>The</mark> Fellowship <mark>of</mark> <mark>the</mark> Ring; Book (2) Two: <mark>The</mark> Two Towers; Book (3) Three: <mark>The</mark> Return <mark>of</mark> <mark>the</mark> King - Collector's Edition"
              },
              {
                "matched_tokens": [
                  "Lord",
                  "of",
                  "the",
                  "Rings",
                  "The",
                  "of",
                  "the",
                  "The",
                  "The",
                  "of",
                  "the"
                ],
                "snippet": "<mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>: <mark>The</mark> Fellowship <mark>of</mark> <mark>the</mark> Ring, <mark>The</mark> Two Towers, <mark>The</mark> Return <mark>of</mark> <mark>the</mark> King"
              },
              {
                "matched_tokens": [],
                "snippet": "Der Herr der Ringe: In der Übersetzung von Margaret Carroux"
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> Millennium Edition Boxed Set"
              },
              {
                "matched_tokens": [],
                "snippet": "Spoločenstvo prsteňa"
              },
              {
                "matched_tokens": [],
                "snippet": "Władca Pierścieni"
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>Rings</mark>"
              },
              {
                "matched_tokens": [
                  "The",
                  "lord",
                  "of",
                  "the",
                  "rings"
                ],
                "snippet": "<mark>The</mark> <mark>lord</mark> <mark>of</mark> <mark>the</mark> <mark>rings</mark>"
              },
              {
                "matched_tokens": [],
                "snippet": "新版指輪物語: 旅の仲間　上1"
              },
              {
                "matched_tokens": [],
                "snippet": "Härskarringen"
              },
              {
                "matched_tokens": [
                  "The",
                  "of",
                  "the"
                ],
                "snippet": "<mark>The</mark> Fellowship <mark>of</mark> <mark>the</mark> Ring"
              },
              {
                "matched_tokens": [],
                "snippet": "新版指輪物語: 王の帰還　上"
              },
              {
                "matched_tokens": [],
                "snippet": "Shinpan yubiwa monogatari"
              },
              {
                "matched_tokens": [
                  "Lord",
                  "of",
                  "the",
                  "Rings",
                  "the"
                ],
                "snippet": "<mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> Trilogy Produced By <mark>the</mark> Mind's Eye Audio Cassette"
              },
              {
                "matched_tokens": [],
                "snippet": "Der Herr der Ringe."
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> Performed by J.R.R. Tolkien"
              },
              {
                "matched_tokens": [
                  "The",
                  "lord",
                  "of",
                  "the",
                  "rings"
                ],
                "snippet": "<mark>The</mark> <mark>lord</mark> <mark>of</mark> <mark>the</mark> <mark>rings</mark>."
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> Boxed Set"
              },
              {
                "matched_tokens": [
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              },
              {
                "matched_tokens": [],
                "snippet": "Vlastelin Kolets"
              },
              {
                "matched_tokens": [],
                "snippet": "Властелин колец"
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> Complete <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> Trilogy"
              },
              {
                "matched_tokens": [],
                "snippet": "Povestʹ o kolʹt︠s︡e"
              },
              {
                "matched_tokens": [],
                "snippet": "Der Herr der Ringe"
              },
              {
                "matched_tokens": [],
                "snippet": "Der Herr der Ringe: Die Gefährten / Die zwei Türme / Die Rückkehr des Königs"
              },
              {
                "matched_tokens": [],
                "snippet": "Společentvo prstenu"
              },
              {
                "matched_tokens": [
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "Illustrated <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> Trilogy"
              },
              {
                "matched_tokens": [],
                "snippet": "El senor de los anillos."
              },
              {
                "matched_tokens": [],
                "snippet": "Las Dos Torres"
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "Of",
                  "The",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>Of</mark> <mark>The</mark> <mark>Rings</mark>"
              },
              {
                "matched_tokens": [],
                "snippet": "Le Seigneur DES Anneaux"
              },
              {
                "matched_tokens": [
                  "of",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "Le Seigneur des Anneaux, 3 Volume Boxed Set Containing\" La Communeaute de l'Anneau; Les Deux Tours; Le retour du Roi: French Edition <mark>of</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>, Containing"
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> - Phil Dragash - Spotify"
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>: Boxed Set"
              },
              {
                "matched_tokens": [
                  "of",
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "Il Signore degli Anelli : Trilogia / Italian edition <mark>of</mark> <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              },
              {
                "matched_tokens": [],
                "snippet": "Возвращение короля"
              },
              {
                "matched_tokens": [],
                "snippet": "La Comunidad del Anillo"
              },
              {
                "matched_tokens": [
                  "The",
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> Hobbit / <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              },
              {
                "matched_tokens": [],
                "snippet": "O señor dos aneis"
              },
              {
                "matched_tokens": [],
                "snippet": "Властелин Колец"
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> Illustrated"
              }
            ],
            "series_names": [
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              }
            ],
            "title": {
              "matched_tokens": [
                "The",
                "Lord",
                "of",
                "the",
                "Rings"
              ],
              "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
            }
          },
          "highlights": [
            {
              "field": "alternative_titles",
              "indices": [
                45,
                57,
                5,
                40,
                52
              ],
              "matched_tokens": [
                [
                  "The",
                  "Lord",
                  "of",
                  "Rings"
                ],
                [
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                [
                  "Lord",
                  "Of",
                  "The",
                  "Rings"
                ],
                [
                  "Lord",
                  "of",
                  "the",
                  "Rings",
                  "The",
                  "of",
                  "the",
                  "The",
                  "The",
                  "of",
                  "the"
                ],
                [
                  "Lord",
                  "of",
                  "the",
                  "Rings",
                  "the"
                ]
              ],
              "snippets": [
                "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>Rings</mark>",
                "<mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>",
                "<mark>Lord</mark> <mark>Of</mark> <mark>The</mark> <mark>Rings</mark> - One Volume Edition",
                "<mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>: <mark>The</mark> Fellowship <mark>of</mark> <mark>the</mark> Ring, <mark>The</mark> Two Towers, <mark>The</mark> Return <mark>of</mark> <mark>the</mark> King",
                "<mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> Trilogy Produced By <mark>the</mark> Mind's Eye Audio Cassette"
              ]
            },
            {
              "field": "title",
              "matched_tokens": [
                "The",
                "Lord",
                "of",
                "the",
                "Rings"
              ],
              "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
            },
            {
              "field": "series_names",
              "indices": [
                0
              ],
              "matched_tokens": [
                [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ]
              ],
              "snippets": [
                "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              ]
            }
          ],
          "text_match": 2314894167593451500,
          "text_match_info": {
            "best_field_score": "4419510927616",
            "best_field_weight": 1,
            "fields_matched": 3,
            "num_tokens_dropped": 0,
            "score": "2314894167593451531",
            "tokens_matched": 4,
            "typo_prefix_score": 0
          }
        },
        {
          "document": {
            "activities_count": 4,
            "alternative_titles": [
              "Bored of the Rings: A Parody of J.R.R. Tolkien's Lord of the Rings"
            ],
            "author_names": [
              "The Harvard Lampoon",
              "Henry N. Beard",
              "Douglas C. Kenney"
            ],
            "compilation": false,
            "content_warnings": [],
            "contribution_types": [
              "Author",
              "Author",
              "Author"
            ],
            "contributions": [
              {
                "author": {
                  "id": 306300,
                  "image": {
                    "color": "#73a1a3",
                    "color_name": "Purple",
                    "height": 375,
                    "id": 332811,
                    "url": "https://assets.hardcover.app/books/306300/8553347-L.jpg",
                    "width": 500
                  },
                  "name": "The Harvard Lampoon",
                  "slug": "the-harvard-lampoon"
                },
                "contribution": null
              },
              {
                "author": {
                  "id": 162050,
                  "image": {
                    "color": "#f1c87a",
                    "color_name": "Silver",
                    "height": 500,
                    "id": 189958,
                    "url": "https://assets.hardcover.app/books/162050/8602579-L.jpg",
                    "width": 310
                  },
                  "name": "Henry N. Beard",
                  "slug": "henry-n-beard"
                },
                "contribution": null
              },
              {
                "author": {
                  "id": 418389,
                  "image": {},
                  "name": "Douglas C. Kenney",
                  "slug": "douglas-c-kenney"
                },
                "contribution": null
              }
            ],
            "cover_color": "Brown",
            "featured_series": {
              "collection": null,
              "details": "3",
              "featured": false,
              "id": 96908,
              "position": 3,
              "series": {
                "books_count": 3,
                "id": 33701,
                "name": "Cardboard Box of the Rings",
                "primary_books_count": 3,
                "slug": "cardboard-box-of-the-rings"
              },
              "unreleased": false
            },
            "featured_series_position": 3,
            "genres": [],
            "has_audiobook": false,
            "has_ebook": false,
            "id": "705069",
            "image": {
              "color": "#551807",
              "color_name": "Brown",
              "height": 148,
              "id": 835068,
              "url": "https://assets.hardcover.app/edition/30695118/15348._SX98_.jpg",
              "width": 98
            },
            "isbns": [
              "0451452615",
              "9780451452610",
              "0451070542",
              "9780451070548"
            ],
            "lists_count": 15,
            "moods": [],
            "pages": 149,
            "prompts_count": 0,
            "rating": 2.5,
            "ratings_count": 10,
            "release_date": "1969-01-01",
            "release_year": 1969,
            "reviews_count": 0,
            "series_names": [
              "Lampoon Parodies",
              "Cardboard Box of the Rings"
            ],
            "slug": "bored-of-the-rings-a-parody-of-jrr-tolkiens-lord-of-the-rings",
            "subtitle": "A Parody of J.R.R. Tolkien's Lord of the Rings",
            "tags": [],
            "title": "Bored of the Rings: A Parody of J.R.R. Tolkien's Lord of the Rings",
            "users_count": 20,
            "users_read_count": 13
          },
          "highlight": {
            "alternative_titles": [
              {
                "matched_tokens": [
                  "of",
                  "the",
                  "Rings",
                  "of",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "Bored <mark>of</mark> <mark>the</mark> <mark>Rings</mark>: A Parody <mark>of</mark> J.R.R. Tolkien's <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              }
            ],
            "author_names": [
              {
                "matched_tokens": [
                  "The"
                ],
                "snippet": "<mark>The</mark> Harvard Lampoon"
              },
              {
                "matched_tokens": [],
                "snippet": "Henry N. Beard"
              },
              {
                "matched_tokens": [],
                "snippet": "Douglas C. Kenney"
              }
            ],
            "series_names": [
              {
                "matched_tokens": [],
                "snippet": "Lampoon Parodies"
              },
              {
                "matched_tokens": [
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "Cardboard Box <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              }
            ],
            "title": {
              "matched_tokens": [
                "of",
                "the",
                "Rings",
                "of",
                "Lord",
                "of",
                "the",
                "Rings"
              ],
              "snippet": "Bored <mark>of</mark> <mark>the</mark> <mark>Rings</mark>: A Parody <mark>of</mark> J.R.R. Tolkien's <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
            }
          },
          "highlights": [
            {
              "field": "title",
              "matched_tokens": [
                "of",
                "the",
                "Rings",
                "of",
                "Lord",
                "of",
                "the",
                "Rings"
              ],
              "snippet": "Bored <mark>of</mark> <mark>the</mark> <mark>Rings</mark>: A Parody <mark>of</mark> J.R.R. Tolkien's <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
            },
            {
              "field": "alternative_titles",
              "indices": [
                0
              ],
              "matched_tokens": [
                [
                  "of",
                  "the",
                  "Rings",
                  "of",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ]
              ],
              "snippets": [
                "Bored <mark>of</mark> <mark>the</mark> <mark>Rings</mark>: A Parody <mark>of</mark> J.R.R. Tolkien's <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              ]
            },
            {
              "field": "series_names",
              "indices": [
                1
              ],
              "matched_tokens": [
                [
                  "of",
                  "the",
                  "Rings"
                ]
              ],
              "snippets": [
                "Cardboard Box <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              ]
            },
            {
              "field": "author_names",
              "indices": [
                0
              ],
              "matched_tokens": [
                [
                  "The"
                ]
              ],
              "snippets": [
                "<mark>The</mark> Harvard Lampoon"
              ]
            }
          ],
          "text_match": 2314894167592927000,
          "text_match_info": {
            "best_field_score": "4419510927360",
            "best_field_weight": 5,
            "fields_matched": 4,
            "num_tokens_dropped": 0,
            "score": "2314894167592927276",
            "tokens_matched": 4,
            "typo_prefix_score": 0
          }
        },
        {
          "document": {
            "activities_count": 27,
            "alternative_titles": [
              "Tolkien Box Set",
              "The Hobbit & The Lord of the Rings",
              "The Lord of the Rings and The Hobbit Set",
              "J.R.R. Tolkien 4-Book Boxed Set: The Hobbit and The Lord of the Rings",
              "The Hobbit and The Lord of the Rings",
              "Die Geschichte des Großen Ringkrieges. 7 Bände. Der Hobbit/Der Herr der Ringe",
              "Estuche Tolkien: El Hobbit / El Señor de los Anillos",
              "El Hobbit / El Señor de los Anillos",
              "Hobit",
              "The Hobbit and The Lord of the Rings: Boxed Set",
              "The Hobbit and the Lord of the Rings",
              "The Lord of the Rings / The Hobbit",
              "The Hobbit And The Lord Of The Rings: Deluxe Pocket Boxed Set",
              "The Hobbit & The Lord of the Rings Boxed Set: Illustrated edition",
              "The Hobbit  The Lord Of The Rings Boxed Set",
              "Hobbit; o Senhor dos Anéis",
              "The Hobbit and The Lord of the Rings Boxed Set: The Fellowship / The Two Towers / The Return of the King",
              "Tolkien 4 book boxed set",
              "The Hobbit and The Lord of the Rings Box Set"
            ],
            "author_names": [
              "J.R.R. Tolkien",
              "Alan Lee"
            ],
            "compilation": true,
            "content_warnings": [],
            "contribution_types": [
              "Author",
              "Illustrator"
            ],
            "contributions": [
              {
                "author": {
                  "id": 132049,
                  "image": {
                    "color": "#5a5a5a",
                    "color_name": "Gray",
                    "height": 266,
                    "id": 33205,
                    "url": "https://assets.hardcover.app/authors/132049/6155606-L.jpg",
                    "width": 187
                  },
                  "name": "J.R.R. Tolkien",
                  "slug": "j-r-r-tolkien"
                }
              },
              {
                "author": {
                  "id": 256737,
                  "image": {
                    "color": "#6f584d",
                    "color_name": "Gray",
                    "height": 1200,
                    "id": 4464182,
                    "url": "https://assets.hardcover.app/author/256737/7431086920375234.jpg",
                    "width": 800
                  },
                  "name": "Alan Lee",
                  "slug": "alan-lee"
                },
                "contribution": "Illustrator"
              }
            ],
            "cover_color": "Beige",
            "description": "Contains:\r\n\r\n - [Hobbit](https://openlibrary.org/works/OL262758W)\r\n - [The Fellowship of the Ring][1]\r\n - [The Two Towers][2]\r\n - [The Return of the King][3]\r\n\r\n  [1]: https://openlibrary.org/works/OL15331214W/The_Fellowship_of_the_Ring\r\n  [2]: https://openlibrary.org/works/OL262757W/The_Two_Towers\r\n  [3]: https://openlibrary.org/works/OL27516W/The_Return_of_the_King",
            "featured_series": {
              "details": "0-3",
              "featured": false,
              "id": 2724,
              "position": 0,
              "series": {
                "books_count": 4,
                "id": 1130,
                "name": "The Lord of the Rings",
                "primary_books_count": 3,
                "slug": "the-lord-of-the-rings"
              },
              "unreleased": false
            },
            "featured_series_position": 0,
            "genres": [
              "Fantasy",
              "Fiction",
              "Young Adult",
              "Adventure",
              "Science fiction",
              "Classics",
              "War",
              "General",
              "Fantasy fiction",
              "Baggins"
            ],
            "has_audiobook": true,
            "has_ebook": false,
            "id": "346073",
            "image": {
              "color": "#f4f4f3",
              "color_name": "Beige",
              "height": 475,
              "id": 1868487,
              "url": "https://assets.hardcover.app/external_data/44171367/13004cc8b3506181bf8c35d11e4124ee2c5a80d5.jpeg",
              "width": 398
            },
            "isbns": [
              "0345320565",
              "9780345320568",
              "0007522932",
              "9780007522934",
              "1565117077",
              "9781565117075",
              "0007525524",
              "9780007525522",
              "3608933204",
              "9783608933208",
              "8445013351",
              "9788445013359",
              "8445014021",
              "9788445014028",
              "0395489075",
              "9780395489079",
              "9536166011",
              "9789536166015",
              "0007355149",
              "9780007355143",
              "0008112835",
              "9780008112837",
              "0458923400",
              "9780458923403",
              "0395282632",
              "9780395282632",
              "0007144083",
              "9780007144082",
              "0544445783",
              "9780544445789",
              "0008376107",
              "9780008376109",
              "0618002251",
              "9780618002252",
              "0007105029",
              "9780007105021",
              "0008387753",
              "9780008387754",
              "853361568X",
              "9788533615687",
              "0547928181",
              "9780547928180",
              "0007509847",
              "9780007509843",
              "0261103563",
              "9780261103566",
              "0345195299",
              "9780345195296",
              "0007525516",
              "9780007525515",
              "0345340426",
              "9780345340429",
              "0345538374",
              "9780345538376"
            ],
            "lists_count": 100,
            "moods": [
              "Adventurous",
              "funny",
              "lighthearted"
            ],
            "pages": 1178,
            "prompts_count": 1,
            "rating": 4.495049504950495,
            "ratings_count": 202,
            "release_date": "1937-09-21",
            "release_year": 1937,
            "reviews_count": 4,
            "series_names": [
              "The Lord of the Rings",
              "Middle-earth Universe"
            ],
            "slug": "the-hobbit-the-lord-of-the-rings",
            "subtitle": "Illustrated edition",
            "tags": [
              "Loveable Characters",
              "Strong Character Development",
              "Plot driven"
            ],
            "title": "The Hobbit & The Lord of the Rings",
            "users_count": 397,
            "users_read_count": 279
          },
          "highlight": {
            "alternative_titles": [
              {
                "matched_tokens": [],
                "snippet": "Tolkien Box Set"
              },
              {
                "matched_tokens": [
                  "The",
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> Hobbit & <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings",
                  "The"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> and <mark>The</mark> Hobbit Set"
              },
              {
                "matched_tokens": [
                  "The",
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "J.R.R. Tolkien 4-Book Boxed Set: <mark>The</mark> Hobbit and <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              },
              {
                "matched_tokens": [
                  "The",
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> Hobbit and <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              },
              {
                "matched_tokens": [],
                "snippet": "Die Geschichte des Großen Ringkrieges. 7 Bände. Der Hobbit/Der Herr der Ringe"
              },
              {
                "matched_tokens": [],
                "snippet": "Estuche Tolkien: El Hobbit / El Señor de los Anillos"
              },
              {
                "matched_tokens": [],
                "snippet": "El Hobbit / El Señor de los Anillos"
              },
              {
                "matched_tokens": [],
                "snippet": "Hobit"
              },
              {
                "matched_tokens": [
                  "The",
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> Hobbit and <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>: Boxed Set"
              },
              {
                "matched_tokens": [
                  "The",
                  "the",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> Hobbit and <mark>the</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              },
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings",
                  "The"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> / <mark>The</mark> Hobbit"
              },
              {
                "matched_tokens": [
                  "The",
                  "The",
                  "Lord",
                  "Of",
                  "The",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> Hobbit And <mark>The</mark> <mark>Lord</mark> <mark>Of</mark> <mark>The</mark> <mark>Rings</mark>: Deluxe Pocket Boxed Set"
              },
              {
                "matched_tokens": [
                  "The",
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> Hobbit & <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> Boxed Set: Illustrated edition"
              },
              {
                "matched_tokens": [
                  "The",
                  "The",
                  "Lord",
                  "Of",
                  "The",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> Hobbit  <mark>The</mark> <mark>Lord</mark> <mark>Of</mark> <mark>The</mark> <mark>Rings</mark> Boxed Set"
              },
              {
                "matched_tokens": [],
                "snippet": "Hobbit; o Senhor dos Anéis"
              },
              {
                "matched_tokens": [
                  "The",
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings",
                  "The",
                  "The",
                  "The",
                  "of",
                  "the"
                ],
                "snippet": "<mark>The</mark> Hobbit and <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> Boxed Set: <mark>The</mark> Fellowship / <mark>The</mark> Two Towers / <mark>The</mark> Return <mark>of</mark> <mark>the</mark> King"
              },
              {
                "matched_tokens": [],
                "snippet": "Tolkien 4 book boxed set"
              },
              {
                "matched_tokens": [
                  "The",
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> Hobbit and <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> Box Set"
              }
            ],
            "series_names": [
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              },
              {
                "matched_tokens": [],
                "snippet": "Middle-earth Universe"
              }
            ],
            "title": {
              "matched_tokens": [
                "The",
                "The",
                "Lord",
                "of",
                "the",
                "Rings"
              ],
              "snippet": "<mark>The</mark> Hobbit & <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
            }
          },
          "highlights": [
            {
              "field": "series_names",
              "indices": [
                0
              ],
              "matched_tokens": [
                [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ]
              ],
              "snippets": [
                "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              ]
            },
            {
              "field": "alternative_titles",
              "indices": [
                2,
                11,
                1,
                13,
                14
              ],
              "matched_tokens": [
                [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings",
                  "The"
                ],
                [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings",
                  "The"
                ],
                [
                  "The",
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                [
                  "The",
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                [
                  "The",
                  "The",
                  "Lord",
                  "Of",
                  "The",
                  "Rings"
                ]
              ],
              "snippets": [
                "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> and <mark>The</mark> Hobbit Set",
                "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> / <mark>The</mark> Hobbit",
                "<mark>The</mark> Hobbit & <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>",
                "<mark>The</mark> Hobbit & <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark> Boxed Set: Illustrated edition",
                "<mark>The</mark> Hobbit  <mark>The</mark> <mark>Lord</mark> <mark>Of</mark> <mark>The</mark> <mark>Rings</mark> Boxed Set"
              ]
            },
            {
              "field": "title",
              "matched_tokens": [
                "The",
                "The",
                "Lord",
                "of",
                "the",
                "Rings"
              ],
              "snippet": "<mark>The</mark> Hobbit & <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
            }
          ],
          "text_match": 2314894167592927000,
          "text_match_info": {
            "best_field_score": "4419510927360",
            "best_field_weight": 5,
            "fields_matched": 3,
            "num_tokens_dropped": 0,
            "score": "2314894167592927275",
            "tokens_matched": 4,
            "typo_prefix_score": 0
          }
        },
        {
          "document": {
            "activities_count": 0,
            "alternative_titles": [
              "The Lord of the Rings: The Art of the Fellowship of the Ring"
            ],
            "author_names": [
              "Gary Russell"
            ],
            "compilation": false,
            "content_warnings": [],
            "contribution_types": [
              "Author"
            ],
            "contributions": [
              {
                "author": {
                  "id": 108565,
                  "image": {
                    "color": "#46402a",
                    "color_name": "Brown",
                    "height": 500,
                    "id": 138233,
                    "url": "https://assets.hardcover.app/books/108565/10599802-L.jpg",
                    "width": 312
                  },
                  "name": "Gary Russell",
                  "slug": "gary-russell"
                }
              }
            ],
            "cover_color": "Brown",
            "description": "Presents over six hundred sketches, paintings, and digital artworks created during production of the film \"The Lord of the Rings: The Two Towers.\"",
            "featured_series": {
              "details": "1",
              "featured": true,
              "id": 23043,
              "position": 1,
              "series": {
                "books_count": 5,
                "id": 11926,
                "name": "The Art of The Lord of the Rings",
                "primary_books_count": 5,
                "slug": "the-art-of-the-lord-of-the-rings"
              },
              "unreleased": false
            },
            "featured_series_position": 1,
            "genres": [
              "Fantasy",
              "Adventure",
              "Classics"
            ],
            "has_audiobook": false,
            "has_ebook": false,
            "id": "428609",
            "image": {
              "color": "#5f6653",
              "color_name": "Brown",
              "height": 162,
              "id": 900187,
              "url": "https://assets.hardcover.app/external_data/59865459/bdb9d05fbd98fa7ce994a3936f542d0171e7f206.jpeg",
              "width": 128
            },
            "isbns": [
              "0618212906",
              "9780618212903"
            ],
            "lists_count": 13,
            "moods": [],
            "pages": 0,
            "prompts_count": 0,
            "rating": 4.625,
            "ratings_count": 80,
            "release_date": "2003-01-01",
            "release_year": 2003,
            "reviews_count": 0,
            "series_names": [
              "The Art of The Lord of the Rings"
            ],
            "slug": "the-lord-of-the-rings-the-art-of-the-fellowship-of-the-ring",
            "subtitle": "The Art of the Fellowship of the Ring",
            "tags": [],
            "title": "The Lord of the Rings: The Art of the Fellowship of the Ring",
            "users_count": 124,
            "users_read_count": 86
          },
          "highlight": {
            "alternative_titles": [
              {
                "matched_tokens": [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings",
                  "The",
                  "of",
                  "the",
                  "of",
                  "the"
                ],
                "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>: <mark>The</mark> Art <mark>of</mark> <mark>the</mark> Fellowship <mark>of</mark> <mark>the</mark> Ring"
              }
            ],
            "series_names": [
              {
                "matched_tokens": [
                  "The",
                  "of",
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ],
                "snippet": "<mark>The</mark> Art <mark>of</mark> <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              }
            ],
            "title": {
              "matched_tokens": [
                "The",
                "Lord",
                "of",
                "the",
                "Rings",
                "The",
                "of",
                "the",
                "of",
                "the"
              ],
              "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>: <mark>The</mark> Art <mark>of</mark> <mark>the</mark> Fellowship <mark>of</mark> <mark>the</mark> Ring"
            }
          },
          "highlights": [
            {
              "field": "title",
              "matched_tokens": [
                "The",
                "Lord",
                "of",
                "the",
                "Rings",
                "The",
                "of",
                "the",
                "of",
                "the"
              ],
              "snippet": "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>: <mark>The</mark> Art <mark>of</mark> <mark>the</mark> Fellowship <mark>of</mark> <mark>the</mark> Ring"
            },
            {
              "field": "alternative_titles",
              "indices": [
                0
              ],
              "matched_tokens": [
                [
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings",
                  "The",
                  "of",
                  "the",
                  "of",
                  "the"
                ]
              ],
              "snippets": [
                "<mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>: <mark>The</mark> Art <mark>of</mark> <mark>the</mark> Fellowship <mark>of</mark> <mark>the</mark> Ring"
              ]
            },
            {
              "field": "series_names",
              "indices": [
                0
              ],
              "matched_tokens": [
                [
                  "The",
                  "of",
                  "The",
                  "Lord",
                  "of",
                  "the",
                  "Rings"
                ]
              ],
              "snippets": [
                "<mark>The</mark> Art <mark>of</mark> <mark>The</mark> <mark>Lord</mark> <mark>of</mark> <mark>the</mark> <mark>Rings</mark>"
              ]
            }
          ],
          "text_match": 2314894167592927000,
          "text_match_info": {
            "best_field_score": "4419510927360",
            "best_field_weight": 5,
            "fields_matched": 3,
            "num_tokens_dropped": 0,
            "score": "2314894167592927275",
            "tokens_matched": 4,
            "typo_prefix_score": 0
          }
        }
      ],
      "out_of": 965453,
      "page": 1,
      "request_params": {
        "collection_name": "Book_production_1760914612",
        "first_q": "lord of the rings",
        "per_page": 5,
        "q": "lord of the rings"
      },
      "search_cutoff": false,
      "search_time_ms": 17
    }
  }
}
```
### Series documentation:
The following fields are available in the returned object. You can also sort by any of these, or limit you search to specific field(s) using fields and weights.

author_name - The name of the primary author who wrote the series
author - Author object
books_count - Number of books in this series
books - A list of books in the series
name - The name of the series
primary_books_count - Number of books in this series with an Integer position (1, 2, 3; exlcludes 1.5, empty)
readers_count - Sum of books.users_read_count for all books in this series (not distinct, so readers will be counted once per book)
slug - The URL slug of the series
Default Values
When searching series, we use the following default values.

fields: name,books,author_name
sort: _text_match:desc,readers_count:desc
weights: 2,1,1

### Query
```
  query SeriesNamedHarryPotter {
      search(
          query: "harry potter",
          query_type: "Series",
          per_page: 7,
          page: 1
      ) {
          results
      }
  }
```
Response:
```
{
  "search": {
    "results": {
      "facet_counts": [],
      "found": 63,
      "hits": [
        {
          "document": {
            "author": {
              "id": 80626,
              "image": {
                "color": "#eed8ce",
                "color_name": "Silver",
                "height": 461,
                "id": 31962,
                "url": "https://assets.hardcover.app/authors/80626/5543033-L.jpg",
                "width": 468
              },
              "name": "J.K. Rowling",
              "slug": "jk-rowling-1965"
            },
            "author_name": "J.K. Rowling",
            "books": [
              "Harry Potter and the Sorcerer's Stone",
              "Harry Potter and the Chamber of Secrets",
              "Harry Potter and the Prisoner of Azkaban",
              "Harry Potter and the Goblet of Fire",
              "Harry Potter and the Order of the Phoenix"
            ],
            "books_count": 10,
            "id": "1185",
            "name": "Harry Potter",
            "primary_books_count": 8,
            "readers_count": 47372,
            "slug": "harry-potter"
          },
          "highlight": {
            "books": [
              {
                "matched_tokens": [
                  "Harry",
                  "Potter"
                ],
                "snippet": "<mark>Harry</mark> <mark>Potter</mark> and the Sorcerer's Stone"
              },
              {
                "matched_tokens": [
                  "Harry",
                  "Potter"
                ],
                "snippet": "<mark>Harry</mark> <mark>Potter</mark> and the Chamber of Secrets"
              },
              {
                "matched_tokens": [
                  "Harry",
                  "Potter"
                ],
                "snippet": "<mark>Harry</mark> <mark>Potter</mark> and the Prisoner of Azkaban"
              },
              {
                "matched_tokens": [
                  "Harry",
                  "Potter"
                ],
                "snippet": "<mark>Harry</mark> <mark>Potter</mark> and the Goblet of Fire"
              },
              {
                "matched_tokens": [
                  "Harry",
                  "Potter"
                ],
                "snippet": "<mark>Harry</mark> <mark>Potter</mark> and the Order of the Phoenix"
              }
            ],
            "name": {
              "matched_tokens": [
                "Harry",
                "Potter"
              ],
              "snippet": "<mark>Harry</mark> <mark>Potter</mark>"
            }
          },
          "highlights": [
            {
              "field": "name",
              "matched_tokens": [
                "Harry",
                "Potter"
              ],
              "snippet": "<mark>Harry</mark> <mark>Potter</mark>"
            },
            {
              "field": "books",
              "indices": [
                0,
                1,
                2,
                3,
                4
              ],
              "matched_tokens": [
                [
                  "Harry",
                  "Potter"
                ],
                [
                  "Harry",
                  "Potter"
                ],
                [
                  "Harry",
                  "Potter"
                ],
                [
                  "Harry",
                  "Potter"
                ],
                [
                  "Harry",
                  "Potter"
                ]
              ],
              "snippets": [
                "<mark>Harry</mark> <mark>Potter</mark> and the Sorcerer's Stone",
                "<mark>Harry</mark> <mark>Potter</mark> and the Chamber of Secrets",
                "<mark>Harry</mark> <mark>Potter</mark> and the Prisoner of Azkaban",
                "<mark>Harry</mark> <mark>Potter</mark> and the Goblet of Fire",
                "<mark>Harry</mark> <mark>Potter</mark> and the Order of the Phoenix"
              ]
            }
          ],
          "text_match": 1157451471441625000,
          "text_match_info": {
            "best_field_score": "2211897868544",
            "best_field_weight": 2,
            "fields_matched": 2,
            "num_tokens_dropped": 0,
            "score": "1157451471441625106",
            "tokens_matched": 2,
            "typo_prefix_score": 0
          }
        },
        {
          "document": {
            "books": [
              "Harry Potter And The Philosopher's Stone"
            ],
            "books_count": 1,
            "id": "215419",
            "name": "Harry Potter",
            "primary_books_count": 0,
            "readers_count": 0,
            "slug": "harry-potter-3"
          },
          "highlight": {
            "books": [
              {
                "matched_tokens": [
                  "Harry",
                  "Potter"
                ],
                "snippet": "<mark>Harry</mark> <mark>Potter</mark> And The Philosopher's Stone"
              }
            ],
            "name": {
              "matched_tokens": [
                "Harry",
                "Potter"
              ],
              "snippet": "<mark>Harry</mark> <mark>Potter</mark>"
            }
          },
          "highlights": [
            {
              "field": "name",
              "matched_tokens": [
                "Harry",
                "Potter"
              ],
              "snippet": "<mark>Harry</mark> <mark>Potter</mark>"
            },
            {
              "field": "books",
              "indices": [
                0
              ],
              "matched_tokens": [
                [
                  "Harry",
                  "Potter"
                ]
              ],
              "snippets": [
                "<mark>Harry</mark> <mark>Potter</mark> And The Philosopher's Stone"
              ]
            }
          ],
          "text_match": 1157451471441625000,
          "text_match_info": {
            "best_field_score": "2211897868544",
            "best_field_weight": 2,
            "fields_matched": 2,
            "num_tokens_dropped": 0,
            "score": "1157451471441625106",
            "tokens_matched": 2,
            "typo_prefix_score": 0
          }
        },
        {
          "document": {
            "author": {
              "id": 80626,
              "image": {
                "color": "#eed8ce",
                "color_name": "Silver",
                "height": 461,
                "id": 31962,
                "url": "https://assets.hardcover.app/authors/80626/5543033-L.jpg",
                "width": 468
              },
              "name": "J.K. Rowling",
              "slug": "jk-rowling-1965"
            },
            "author_name": "J.K. Rowling",
            "books": [],
            "books_count": 0,
            "id": "161579",
            "name": "Harry potter",
            "primary_books_count": 0,
            "readers_count": 0,
            "slug": "harry-potter-7d0b2645-ea43-4164-b7ff-b7c071c123f8"
          },
          "highlight": {
            "name": {
              "matched_tokens": [
                "Harry",
                "potter"
              ],
              "snippet": "<mark>Harry</mark> <mark>potter</mark>"
            }
          },
          "highlights": [
            {
              "field": "name",
              "matched_tokens": [
                "Harry",
                "potter"
              ],
              "snippet": "<mark>Harry</mark> <mark>potter</mark>"
            }
          ],
          "text_match": 1157451471441625000,
          "text_match_info": {
            "best_field_score": "2211897868544",
            "best_field_weight": 2,
            "fields_matched": 1,
            "num_tokens_dropped": 0,
            "score": "1157451471441625105",
            "tokens_matched": 2,
            "typo_prefix_score": 0
          }
        },
        {
          "document": {
            "author": {
              "id": 237487,
              "image": {
                "color": "#0f2e2a",
                "color_name": "Purple",
                "height": 475,
                "id": 264696,
                "url": "https://assets.hardcover.app/books/237487/1699624-L.jpg",
                "width": 272
              },
              "name": "John Tiffany",
              "slug": "john-tiffany"
            },
            "author_name": "John Tiffany",
            "books": [],
            "books_count": 0,
            "id": "101156",
            "name": "harry potter",
            "primary_books_count": 0,
            "readers_count": 0,
            "slug": "harry-potter-john-tiffany"
          },
          "highlight": {
            "name": {
              "matched_tokens": [
                "harry",
                "potter"
              ],
              "snippet": "<mark>harry</mark> <mark>potter</mark>"
            }
          },
          "highlights": [
            {
              "field": "name",
              "matched_tokens": [
                "harry",
                "potter"
              ],
              "snippet": "<mark>harry</mark> <mark>potter</mark>"
            }
          ],
          "text_match": 1157451471441625000,
          "text_match_info": {
            "best_field_score": "2211897868544",
            "best_field_weight": 2,
            "fields_matched": 1,
            "num_tokens_dropped": 0,
            "score": "1157451471441625105",
            "tokens_matched": 2,
            "typo_prefix_score": 0
          }
        },
        {
          "document": {
            "books": [],
            "books_count": 0,
            "id": "37857",
            "name": "Harry Potter,",
            "primary_books_count": 0,
            "readers_count": 0,
            "slug": "harry-potter-37857"
          },
          "highlight": {
            "name": {
              "matched_tokens": [
                "Harry",
                "Potter"
              ],
              "snippet": "<mark>Harry</mark> <mark>Potter</mark>,"
            }
          },
          "highlights": [
            {
              "field": "name",
              "matched_tokens": [
                "Harry",
                "Potter"
              ],
              "snippet": "<mark>Harry</mark> <mark>Potter</mark>,"
            }
          ],
          "text_match": 1157451471441625000,
          "text_match_info": {
            "best_field_score": "2211897868544",
            "best_field_weight": 2,
            "fields_matched": 1,
            "num_tokens_dropped": 0,
            "score": "1157451471441625105",
            "tokens_matched": 2,
            "typo_prefix_score": 0
          }
        },
        {
          "document": {
            "author": {
              "id": 227752,
              "image": {
                "color": "#e2e2c5",
                "color_name": "Beige",
                "height": 500,
                "id": 254490,
                "url": "https://assets.hardcover.app/books/227752/7368233-L.jpg",
                "width": 335
              },
              "name": "Eliezer Yudkowsky",
              "slug": "eliezer-yudkowsky"
            },
            "author_name": "Eliezer Yudkowsky",
            "books": [
              "Harry Potter and the Methods of Rationality",
              "Гарри Поттер и Методы рационального мышления",
              "Harry James Potter-Evans-Verres and the Methods of Rationality",
              "Harry James Potter-Evans-Verres and the Professor's Games",
              "Harry James Potter-Evans-Verres and the Shadows of Death"
            ],
            "books_count": 9,
            "id": "11272",
            "name": "Harry Potter and the Methods of Rationality",
            "primary_books_count": 6,
            "readers_count": 176,
            "slug": "harry-potter-and-the-methods-of-rationality"
          },
          "highlight": {
            "books": [
              {
                "matched_tokens": [
                  "Harry",
                  "Potter"
                ],
                "snippet": "<mark>Harry</mark> <mark>Potter</mark> and the Methods of Rationality"
              },
              {
                "matched_tokens": [],
                "snippet": "Гарри Поттер и Методы рационального мышления"
              },
              {
                "matched_tokens": [
                  "Harry",
                  "Potter"
                ],
                "snippet": "<mark>Harry</mark> James <mark>Potter</mark>-Evans-Verres and the Methods of Rationality"
              },
              {
                "matched_tokens": [
                  "Harry",
                  "Potter"
                ],
                "snippet": "<mark>Harry</mark> James <mark>Potter</mark>-Evans-Verres and the Professor's Games"
              },
              {
                "matched_tokens": [
                  "Harry",
                  "Potter"
                ],
                "snippet": "<mark>Harry</mark> James <mark>Potter</mark>-Evans-Verres and the Shadows of Death"
              }
            ],
            "name": {
              "matched_tokens": [
                "Harry",
                "Potter"
              ],
              "snippet": "<mark>Harry</mark> <mark>Potter</mark> and the Methods of Rationality"
            }
          },
          "highlights": [
            {
              "field": "name",
              "matched_tokens": [
                "Harry",
                "Potter"
              ],
              "snippet": "<mark>Harry</mark> <mark>Potter</mark> and the Methods of Rationality"
            },
            {
              "field": "books",
              "indices": [
                0,
                2,
                3,
                4
              ],
              "matched_tokens": [
                [
                  "Harry",
                  "Potter"
                ],
                [
                  "Harry",
                  "Potter"
                ],
                [
                  "Harry",
                  "Potter"
                ],
                [
                  "Harry",
                  "Potter"
                ]
              ],
              "snippets": [
                "<mark>Harry</mark> <mark>Potter</mark> and the Methods of Rationality",
                "<mark>Harry</mark> James <mark>Potter</mark>-Evans-Verres and the Methods of Rationality",
                "<mark>Harry</mark> James <mark>Potter</mark>-Evans-Verres and the Professor's Games",
                "<mark>Harry</mark> James <mark>Potter</mark>-Evans-Verres and the Shadows of Death"
              ]
            }
          ],
          "text_match": 1157451471441100800,
          "text_match_info": {
            "best_field_score": "2211897868288",
            "best_field_weight": 2,
            "fields_matched": 2,
            "num_tokens_dropped": 0,
            "score": "1157451471441100818",
            "tokens_matched": 2,
            "typo_prefix_score": 0
          }
        },
        {
          "document": {
            "author": {
              "id": 245013,
              "image": {
                "color": "#eddcb8",
                "color_name": "Beige",
                "height": 500,
                "id": 272023,
                "url": "https://assets.hardcover.app/books/245013/8123515-L.jpg",
                "width": 295
              },
              "name": "British Library",
              "slug": "british-library"
            },
            "author_name": "British Library",
            "books": [
              "Harry Potter: A History of Magic",
              "Harry Potter: A Journey Through A History of Magic",
              "Harry Potter: A History of Magic: The eBook of the Exhibition",
              "A History of Magic: A Journey Through the Hogwarts Curriculum",
              "Harry Potter: A Journey Through A History of Magic"
            ],
            "books_count": 4,
            "id": "7611",
            "name": "Harry Potter: A History of Magic Exhibition",
            "primary_books_count": 0,
            "readers_count": 43,
            "slug": "harry-potter-a-history-of-magic-exhibition"
          },
          "highlight": {
            "books": [
              {
                "matched_tokens": [
                  "Harry",
                  "Potter"
                ],
                "snippet": "<mark>Harry</mark> <mark>Potter</mark>: A History of Magic"
              },
              {
                "matched_tokens": [
                  "Harry",
                  "Potter"
                ],
                "snippet": "<mark>Harry</mark> <mark>Potter</mark>: A Journey Through A History of Magic"
              },
              {
                "matched_tokens": [
                  "Harry",
                  "Potter"
                ],
                "snippet": "<mark>Harry</mark> <mark>Potter</mark>: A History of Magic: The eBook of the Exhibition"
              },
              {
                "matched_tokens": [],
                "snippet": "A History of Magic: A Journey Through the Hogwarts Curriculum"
              },
              {
                "matched_tokens": [
                  "Harry",
                  "Potter"
                ],
                "snippet": "<mark>Harry</mark> <mark>Potter</mark>: A Journey Through A History of Magic"
              }
            ],
            "name": {
              "matched_tokens": [
                "Harry",
                "Potter"
              ],
              "snippet": "<mark>Harry</mark> <mark>Potter</mark>: A History of Magic Exhibition"
            }
          },
          "highlights": [
            {
              "field": "name",
              "matched_tokens": [
                "Harry",
                "Potter"
              ],
              "snippet": "<mark>Harry</mark> <mark>Potter</mark>: A History of Magic Exhibition"
            },
            {
              "field": "books",
              "indices": [
                0,
                1,
                2,
                4
              ],
              "matched_tokens": [
                [
                  "Harry",
                  "Potter"
                ],
                [
                  "Harry",
                  "Potter"
                ],
                [
                  "Harry",
                  "Potter"
                ],
                [
                  "Harry",
                  "Potter"
                ]
              ],
              "snippets": [
                "<mark>Harry</mark> <mark>Potter</mark>: A History of Magic",
                "<mark>Harry</mark> <mark>Potter</mark>: A Journey Through A History of Magic",
                "<mark>Harry</mark> <mark>Potter</mark>: A History of Magic: The eBook of the Exhibition",
                "<mark>Harry</mark> <mark>Potter</mark>: A Journey Through A History of Magic"
              ]
            }
          ],
          "text_match": 1157451471441100800,
          "text_match_info": {
            "best_field_score": "2211897868288",
            "best_field_weight": 2,
            "fields_matched": 2,
            "num_tokens_dropped": 0,
            "score": "1157451471441100818",
            "tokens_matched": 2,
            "typo_prefix_score": 0
          }
        }
      ],
      "out_of": 205444,
      "page": 1,
      "request_params": {
        "collection_name": "Series_production_1760904561",
        "first_q": "harry potter",
        "per_page": 7,
        "q": "harry potter"
      },
      "search_cutoff": false,
      "search_time_ms": 6
    }
  }
}
```
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
