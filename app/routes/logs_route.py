"""
Logs viewing endpoint
"""
from fastapi import APIRouter, Query
from pathlib import Path
import logging

logger = logging.getLogger("mam-audiofinder")
router = APIRouter()

@router.get("/api/logs")
async def get_logs(
    lines: int = Query(default=100, ge=1, le=10000, description="Number of lines to return"),
    level: str = Query(default="", description="Filter by log level (INFO, WARNING, ERROR)")
):
    """
    Read application logs from /data/logs/app.log and rotated logs
    Returns most recent log entries, optionally filtered by level
    """
    try:
        log_dir = Path("/data/logs")
        log_file = log_dir / "app.log"

        if not log_file.exists():
            return {
                "ok": False,
                "error": "Log file not found",
                "logs": []
            }

        # Collect lines from current log and rotated logs
        all_lines = []

        # Read rotated logs first (oldest to newest)
        for i in range(10, 0, -1):  # Check app.log.10 down to app.log.1
            rotated = log_dir / f"app.log.{i}"
            if rotated.exists():
                try:
                    with open(rotated, "r", encoding="utf-8", errors="ignore") as f:
                        all_lines.extend(f.readlines())
                except Exception as e:
                    logger.warning(f"Failed to read {rotated}: {e}")

        # Read current log file
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                all_lines.extend(f.readlines())
        except Exception as e:
            logger.error(f"Failed to read current log file: {e}")
            return {
                "ok": False,
                "error": f"Failed to read log file: {e}",
                "logs": []
            }

        # Filter by log level if specified
        if level:
            level_upper = level.upper()
            filtered_lines = [
                line for line in all_lines
                if level_upper in line
            ]
        else:
            filtered_lines = all_lines

        # Return the last N lines
        recent_lines = filtered_lines[-lines:] if len(filtered_lines) > lines else filtered_lines

        return {
            "ok": True,
            "total_lines": len(all_lines),
            "filtered_lines": len(filtered_lines),
            "returned_lines": len(recent_lines),
            "logs": recent_lines
        }

    except Exception as e:
        logger.exception("Error reading logs")
        return {
            "ok": False,
            "error": str(e),
            "logs": []
        }
