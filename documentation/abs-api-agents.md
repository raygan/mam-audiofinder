# ABS API Agent Guide

This repository publishes the Audiobookshelf API documentation via Slate. Every endpoint family lives in its own include file beneath `source/includes`. This guide is for AI assistants that need to answer “where are the docs for X?” or supply example requests without rereading the repo.

## 1. Know the Terrain

- **Endpoint definitions** live in `source/includes/_*.md`. Headings start with `##`. Each section includes an “HTTP Request” block that contains the verb + URL pattern and examples.
- **Schemas** and shared data shapes** are documented in `source/includes/_schemas.md` (library, item, media progress, session objects, etc.), providing canonical field names and types.
- **Navigation Tip:** Use your editor’s “go to line” on the references listed below—each section here includes its starting line so you can jump straight to the relevant block.

## 2. High-Level Category Map

Each row points to the key include file, the line where the section begins, and the highlights/endpoints available there.

| Category | File / Line | Highlights |
| --- | --- | --- |
| Authors | `source/includes/_authors.md:3` | Get (`GET /api/authors/:id`), update/merge (`PATCH /api/authors/:id`), match (`POST /api/authors/:id/match`), and download author images (`GET /api/authors/:id/image`). |
| Libraries | `source/includes/_libraries.md:3` | Create/list/get/update/delete libraries; fetch library collections, playlists, personalized view, filter data, stats, authors; scan/match; reorder list; recent episodes. |
| Library Items | `source/includes/_items.md:3` | Delete all items, get/delete/update items, cover CRUD, matching, playback (`POST /api/items/:id/play[/episodeId]`), track edits, scans, tone scans, chapter management, and batch delete/update/get/quickmatch. |
| Collections | `source/includes/_collections.md:3` | Collection CRUD plus add/remove single book, batch add/remove, include RSS feed option. |
| Playlists | `source/includes/_playlists.md:3` | Playlist CRUD, add/remove playlist items, batch operations, create playlist from collection. |
| Podcasts | `source/includes/_podcasts.md:3` | Podcast creation, feed import (RSS or OPML), episode download queue, search feed, match episodes, per-episode CRUD. |
| RSS Feeds | `source/includes/_rss_feeds.md:3` | Open feeds for library items, collections, and series; close feed endpoint. |
| Users (admin) | `source/includes/_users.md:3` | Admin user CRUD, list/online view, user listening sessions/stats, purge media progress. |
| Me (self) | `source/includes/_me.md:5` | Get authed user, listening sessions/stats, manage continue listening, media progress CRUD/batch, bookmarks, password change, sync local progress, items in progress, remove series from continue listening. |
| Sessions | `source/includes/_sessions.md:3` | List listening sessions, delete session, sync local session(s), inspect/sync/close open stream sessions. |
| Server Auth | `source/includes/_server.md:3` | Login/logout, OAuth2 PKCE endpoints (auth request, callback, mobile redirect), initial server setup, status/ping/healthcheck probes. |
| Notifications | `source/includes/_notifications.md:3` | Get/update notification settings, fetch event data, fire test events, create/update/delete notifications, send test via ID. |
| Tools | `source/includes/_tools.md:3` | Encode book to M4B, cancel encode, embed metadata in audio files. |
| Backups | `source/includes/_backups.md:3` | List/create/delete/apply/upload backups. |
| Cache | `source/includes/_cache.md:3` | Purge all cache or just the items cache. |
| Filesystem | `source/includes/_filesystem.md:3` | Browse server directories for library configuration. |
| Misc Utilities | `source/includes/_misc.md:3` | Upload files, update server settings, `/api/authorize`, tag & genre CRUD, cron validation. |
| Search | `source/includes/_search.md:3` | Search covers, books (multi-provider), podcasts, authors, book chapters. |
| Filtering Guide | `source/includes/_filtering.md` | Explains filter syntax (groups, values, encoding). |
| Metadata Providers | `source/includes/_metadata_providers.md:3` | Valid provider strings for books/podcasts. |
| Socket Events | `source/includes/_socket.md:11` | Client-emitted events plus server events for users, streams, libraries, scans, collections, playlists, RSS feeds, backups, podcast download queue, metadata, notifications, misc. |
| Schemas | `source/includes/_schemas.md:3` | Canonical JSON for libraries, items, podcasts, tracks, audio files, bookmarks, stats, etc. |

## 3. How to Find Examples Fast

1. **Use the table above as an index.** Jump directly to the include file + line for the endpoint family you need.
2. **Scan the `##` headings.** Within each include you’ll see `## {Endpoint}` followed by the cURL sample, request description, and response schema.
3. **Validate payloads using `_schemas.md`.** When copying fields, reference the schema definitions so you stay consistent with required attributes and types.
4. **Check supporting guides.** Use `_filtering.md` for advanced query parameters, `_metadata_providers.md` for valid provider values, and `_filesystem.md` for selecting folders when creating libraries.

## 4. Typical Questions & Where to Look

- **“How do I create or manage playback sessions?”** See `source/includes/_items.md:1197` for starting a session and `source/includes/_sessions.md:3` for inspecting/deleting/syncing sessions.
- **“Where are the admin endpoints for user management?”** All in `source/includes/_users.md` (lines listed above), while self-service actions live in `_me.md`.
- **“Need examples for podcast episode downloads.”** Check `_podcasts.md` sections starting at `source/includes/_podcasts.md:373` (downloads, clear queue, search feed).
- **“How do I trigger notifications?”** `_notifications.md` covers settings (`line 3`), events (`line 145`), and testing (`line 228` and `line 445`).
- **“Which provider strings are valid for metadata searches?”** Consult the table in `source/includes/_metadata_providers.md`.

## 5. Best Practices for Agents

- **Quote paths and lines** when pointing maintainers to documentation (`source/includes/_items.md:700` instead of “look in the items file”).
- **Distinguish between admin vs. self endpoints.** Many routes require admin privileges (e.g., backups, user CRUD) while the `/api/me/*` group is for the authenticated user only.
- **Leverage existing cURL examples.** Every section includes a ready-to-run snippet—reuse them to ensure consistent headers and parameters.
- **Keep responses aligned with schemas.** When summarizing or producing example payloads, cite the relevant schema section so consumers can verify each field.

Armed with this guide, AI assistants can quickly map user requests to the right documentation sections, cite exact endpoints, and surface example payloads without re-parsing the entire Slate project each time.
