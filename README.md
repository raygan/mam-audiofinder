# MAM Audiobook Finder

A lightweight web app + API to quickly search [MyAnonamouse](https://www.myanonamouse.net/) for audiobooks, add them to qBittorrent, and import completed downloads into your [Audiobookshelf](https://www.audiobookshelf.org/) library.

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


1. Clone this repository.
2. Copy `.env.example` → `.env` and fill in the required values:
   - Your **MAM session cookie** (`MAM_COOKIE`)
   - Your **qBittorrent WebUI** address and credentials (`QB_URL`, `QB_USER`, `QB_PASS`)
   - Update host paths (`MEDIA_ROOT`, `DATA_DIR`) to match your system
3. Start the container (will pull the image if needed):
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
| `MEDIA_ROOT`           | Host path that contains both torrent downloads and Audiobookshelf library   |
| `DATA_DIR`             | Host path where this app stores its state (e.g. SQLite DB)                  |
| `DL_DIR`               | In-container path for qBittorrent downloads (default `/media/torrents`)     |
| `LIB_DIR`              | In-container path for Audiobookshelf library (default `/media/Books/Audiobooks`) |
| `IMPORT_MODE`          | `link`, `copy`, or `move` (default `link`)                                  |
| `QB_CATEGORY`          | Category assigned to new torrents (default `mam-audiofinder`)               |
| `QB_POSTIMPORT_CATEGORY` | Category to set after import (empty = unset)                              |
| `PUID`                 | Container user ID (for file permissions, default `99`)                      |
| `PGID`                 | Container group ID (for file permissions, default `100`)                    |
| `UMASK`                | File creation mask (default `0002`)                                         |


This project was created to scratch a personal itch, and was almost entirely vibe-coded with ChatGPT. I will probably not be developing it further, looking at issues, or accepting pull requests.
Do not run this on the open internet! 
Are you a *real* developer? Do you want to fork or rewrite this project and make it not suck? Go for it!

## License

MIT — provided as-is, no warranty.