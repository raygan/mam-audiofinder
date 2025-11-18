"""Routes package for MAM Audiobook Finder."""
from fastapi import APIRouter

from .search import router as search_router
from .history import router as history_router
from .qbittorrent import router as qbittorrent_router
from .import_route import router as import_router
from .covers_route import router as covers_router
from .basic import router as basic_router
from .logs_route import router as logs_router
from .showcase import router as showcase_router
from .series import router as series_router
from .description_route import router as description_router

# Create main router that includes all sub-routers
main_router = APIRouter()
main_router.include_router(basic_router)
main_router.include_router(search_router)
main_router.include_router(history_router)
main_router.include_router(qbittorrent_router)
main_router.include_router(import_router)
main_router.include_router(covers_router)
main_router.include_router(logs_router)
main_router.include_router(showcase_router)
main_router.include_router(series_router)
main_router.include_router(description_router)

__all__ = ["main_router"]
