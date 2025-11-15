# MAM Audiobook Finder

A lightweight web app + API to quickly search MyAnonamouse for audiobooks, add them to qBittorrent, and import completed downloads into your [Audiobookshelf](https://www.audiobookshelf.org/) library.

![Search](/app/static/screenshots/search.png)
![Import](/app/static/screenshots/import.png)


## Features

- **Search MAM** by title, author, or narrator  
- **One-click add to qBittorrent** (with its own category)  
- **History view** of all books you've added  
- **Inline import tool** to copy or hard-link completed downloads into your Audiobookshelf library  
- Minimal, fast UI that works on desktop and mobile
- ZERO AUTHENTICATION (*Please* don't put this on the open internet. Tailscale or a Cloudflare Tunnel with Cloudflare Access might be good options.)
- Spouse tested and approved

## Requirements

- qBittorrent with WebUI enabled  
- A valid MAM session cookie  
- Docker & Docker Compose

## Quick Start

1. Clone this repository.
2. Copy `.env.example` → `.env` and fill in the required values:
   - Your **MAM session cookie** (`MAM_COOKIE`)
   - Your **qBittorrent WebUI** address and credentials (`QB_URL`, `QB_USER`, `QB_PASS`)
   - Update host paths (`MEDIA_ROOT`, `DATA_DIR`) to match your system
3. Start the container:
   ```bash
   docker compose up -d
   ```
   
4. Visit [http://localhost:8008](http://localhost:8008) (or your mapped port).

## Environment Variables

| Variable               | Description                                                                 |
|------------------------|-----------------------------------------------------------------------------|
| `MAM_COOKIE`           | Your MAM session cookie (use ASN-locked cookie)                             |
| `QB_URL`               | qBittorrent WebUI URL (e.g. `http://qbittorrent:8080`)                      |
| `QB_USER`              | qBittorrent WebUI username                                                  |
| `QB_PASS`              | qBittorrent WebUI password                                                  |
| `ABS_BASE_URL`         | *(Optional)* Audiobookshelf URL for fetching cover images (e.g. `http://audiobookshelf:13378`) |
| `ABS_API_KEY`          | *(Optional)* Audiobookshelf API key/token for authentication                |
| `ABS_LIBRARY_ID`       | *(Optional)* Specific Audiobookshelf library ID to search within            |
| `MEDIA_ROOT`           | Host path that contains both torrent downloads and Audiobookshelf library   |
| `DATA_DIR`             | Host path where this app stores its state (e.g. SQLite DB)                  |
| `DL_DIR`               | In-container path for qBittorrent downloads (default `/media/torrents`)     |
| `LIB_DIR`              | In-container path for Audiobookshelf library (default `/media/Books/Audiobooks`) |
| `IMPORT_MODE`          | `link`, `copy`, or `move` (default `link`)                                  |
| `FLATTEN_DISCS`        | Flatten multi-disc audiobooks to sequential files (default `true`)          |
| `QB_CATEGORY`          | Category assigned to new torrents (default `mam-audiofinder`)               |
| `QB_POSTIMPORT_CATEGORY` | Category to set after import (empty = unset)                              |
| `PUID`                 | Container user ID (for file permissions, default `1000`)                    |
| `PGID`                 | Container group ID (for file permissions, default `1000`)                   |
| `UMASK`                | File creation mask (default `0002`)                                         |

### FLATTEN_DISCS Explained

When enabled (default), multi-disc audiobooks are automatically reorganized for Audiobookshelf:

**Input structure:**
```
Speaker for the Dead/
├── Speaker for the Dead (Disc 01)/
│   ├── Track 01.mp3
│   ├── Track 02.mp3
│   └── ...
├── Speaker for the Dead (Disc 02)/
│   ├── Track 01.mp3
│   └── ...
```

**Output structure:**
```
Speaker for the Dead/
├── Part 001.mp3
├── Part 002.mp3
├── Part 003.mp3
└── ... (all tracks sequentially numbered)
```

The import detects disc/track patterns (Disc, Disk, CD, Part + Track, Chapter numbers), sorts files correctly across all discs, and renames them sequentially. This creates a clean, flat structure that Audiobookshelf can process into a single audiobook.

Set `FLATTEN_DISCS=false` to preserve the original directory structure.

> **Note:** The variable is `PGID` (not `GUID`). Both `PUID` and `PGID` must be set together. The container will validate your configuration on startup and show helpful error messages if there are issues.
>
> **Important:** If you change `PUID` or `PGID` values after the initial build, you must rebuild the container:
> ```bash
> docker compose up -d --build
> ```


This project was created to scratch a personal itch, and was almost entirely vibe-coded with ChatGPT. I will probably not be developing it further, looking at issues, or accepting pull requests.
Do not run this on the open internet! 
Are you a *real* developer? Do you want to fork or rewrite this project and make it not suck? Go for it!

## License

MIT — provided as-is, no warranty.