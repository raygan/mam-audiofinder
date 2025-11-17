"""
Basic routes for health checks and configuration.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import IMPORT_MODE, FLATTEN_DISCS, HARDCOVER_SERIES_LIMIT

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the search page (main UI)."""
    return templates.TemplateResponse("search.html", {"request": request})


@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """Serve the history page."""
    return templates.TemplateResponse("history.html", {"request": request})


@router.get("/showcase", response_class=HTMLResponse)
async def showcase_page(request: Request):
    """Serve the showcase page."""
    return templates.TemplateResponse("showcase.html", {"request": request})


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Serve the logs page."""
    return templates.TemplateResponse("logs.html", {"request": request})


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"ok": True}


@router.get("/config")
async def config():
    """Return app configuration."""
    return {
        "import_mode": IMPORT_MODE,
        "flatten_discs": FLATTEN_DISCS,
        "hardcover_series_limit": HARDCOVER_SERIES_LIMIT,
    }
