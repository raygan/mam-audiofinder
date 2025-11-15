"""
Basic routes for health checks and configuration.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import IMPORT_MODE, FLATTEN_DISCS

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main UI."""
    return templates.TemplateResponse("index.html", {"request": request})


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
    }
