"""
MAM Audiobook Finder - Main Application Bootstrap
A lightweight web application for searching MAM audiobooks,
adding them to qBittorrent, and importing to Audiobookshelf.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Import configuration first
from config import LOG_MAX_MB, LOG_MAX_FILES, LOG_DIR

# ---------------------------- Logging Setup ----------------------------
# Ensure log directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Create logger
logger = logging.getLogger("mam-audiofinder")
logger.setLevel(logging.INFO)

# Clear any existing handlers
logger.handlers.clear()

# Console handler for Docker (always active)
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# File handler with rotation
log_file = LOG_DIR / "app.log"
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=LOG_MAX_MB * 1024 * 1024,  # Convert MB to bytes
    backupCount=LOG_MAX_FILES
)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

logger.info(f"Logging initialized: {log_file} (max {LOG_MAX_MB}MB, {LOG_MAX_FILES} files)")

# ---------------------------- Database Initialization ----------------------------
from db import initialize_databases

initialize_databases()

# ---------------------------- FastAPI Application ----------------------------
app = FastAPI(title="MAM Audiobook Finder", version="0.4.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include all routes
from routes import main_router
app.include_router(main_router)

# ---------------------------- Startup Event ----------------------------
from abs_client import abs_client

@app.on_event("startup")
async def startup_event():
    """Run startup tests."""
    logger.info("🚀 Starting MAM Audiobook Finder v0.4.0")
    await abs_client.test_connection()
    logger.info("✅ Application startup complete")
