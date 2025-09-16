# MAM Audiobook Finder

A lightweight web app + API to quickly search [MyAnonamouse](https://www.myanonamouse.net/) for audiobooks, add them to qBittorrent, and import completed downloads into your [Audiobookshelf](https://www.audiobookshelf.org/) library.

## Features

- **Search MAM** by title, author, or narrator  
- **One-click add to qBittorrent** (with its own category)  
- **History view** of all books you've added  
- **Inline import tool** to copy or hard-link completed downloads into your library  
- **Cue-file skip** and duplicate-title handling (`Title (2)` if needed)  
- Minimal, fast UI that works on desktop and mobile

## Requirements

- qBittorrent with WebUI enabled  
- A valid MAM session cookie  
- Docker & Docker Compose

## Quick Start

1. Clone this repository.
2. Copy `.env.example` → `.env` and fill in:
   - `MAM_COOKIE` (your session cookie)
   - `QB_URL`, `QB_USER`, `QB_PASS` (qBittorrent WebUI creds)
   - `DL_DIR` and `LIB_DIR` (downloads & Audiobookshelf library)
3. Build and run:

   ```bash
   docker compose up -d --build
   ```
   
4. Visit [http://localhost:8008](http://localhost:8008) (or your mapped port).

## Environment Variables

| Variable | Description |
|---------|-------------|
| `MAM_COOKIE` | Your MAM session cookie |
| `QB_URL`, `QB_USER`, `QB_PASS` | qBittorrent WebUI connection |
| `QB_CATEGORY` | Category used for torrents (default `mam-audiofinder`) |
| `DL_DIR` | Path inside container to qB downloads (default `/media/torrents`) |
| `LIB_DIR` | Path inside container to Audiobookshelf library |
| `IMPORT_MODE` | `link`, `copy`, or `move` (default `link`) |
| `PUID`, `PGID`, `UMASK` | Container user/group and umask |


This project was created to scratch a personal itch, and was almost entirely vibe-coded with ChatGPT. I will probably not be developing it further, looking at issues, or accepting pull requests.

## License

MIT — provided as-is, no warranty.