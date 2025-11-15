#!/usr/bin/env python3
"""
Startup validation script to check for common configuration errors.
This helps catch issues before the application starts.
"""
import os
import sys

def validate_env():
    """Validate environment variables and provide helpful error messages."""
    errors = []
    warnings = []

    # Check if user mistakenly set GUID instead of PGID
    if os.getenv("GUID"):
        errors.append(
            "ERROR: Found environment variable 'GUID' but the correct variable name is 'PGID'.\n"
            "       Please change GUID to PGID in your configuration."
        )

    # Check if PGID is set (when running in Docker with user specification)
    if os.getenv("PUID") and not os.getenv("PGID"):
        errors.append(
            "ERROR: PUID is set but PGID is missing.\n"
            "       Both PUID and PGID must be set together for proper file permissions."
        )

    # Validate UMASK format
    umask_val = os.getenv("UMASK")
    if umask_val:
        try:
            # Try to parse as octal
            int(umask_val, 8)
        except ValueError:
            errors.append(
                f"ERROR: Invalid UMASK value '{umask_val}'.\n"
                f"       UMASK must be a valid octal number (e.g., 0002, 0022)."
            )

    # Check for required MAM cookie
    if not os.getenv("MAM_COOKIE"):
        warnings.append(
            "WARNING: MAM_COOKIE is not set. Search functionality will not work."
        )

    # Check Audiobookshelf configuration
    abs_url = os.getenv("ABS_BASE_URL")
    abs_key = os.getenv("ABS_API_KEY")

    if abs_url and not abs_key:
        warnings.append(
            "WARNING: ABS_BASE_URL is set but ABS_API_KEY is missing.\n"
            "         Cover image fetching from Audiobookshelf will not work.\n"
            "         Set ABS_API_KEY to enable cover integration."
        )
    elif abs_key and not abs_url:
        warnings.append(
            "WARNING: ABS_API_KEY is set but ABS_BASE_URL is missing.\n"
            "         Cover image fetching from Audiobookshelf will not work.\n"
            "         Set ABS_BASE_URL to enable cover integration."
        )
    elif not abs_url and not abs_key:
        warnings.append(
            "INFO: Audiobookshelf integration not configured (ABS_BASE_URL/ABS_API_KEY).\n"
            "      Cover images will not be fetched. This is optional."
        )

    # Check logging configuration
    log_max_mb = os.getenv("LOG_MAX_MB")
    log_max_files = os.getenv("LOG_MAX_FILES")

    if log_max_mb:
        try:
            max_mb = int(log_max_mb)
            if max_mb <= 0:
                warnings.append(
                    f"WARNING: LOG_MAX_MB is set to {max_mb} which will disable log rotation.\n"
                    "         Logs may grow indefinitely. Recommended value: 5 or higher."
                )
            elif max_mb > 100:
                warnings.append(
                    f"WARNING: LOG_MAX_MB is set to {max_mb}MB which is very large.\n"
                    "         Each log file can grow up to this size. Recommended value: 5-20."
                )
        except ValueError:
            errors.append(
                f"ERROR: Invalid LOG_MAX_MB value '{log_max_mb}'.\n"
                f"       LOG_MAX_MB must be a positive integer (megabytes)."
            )

    if log_max_files:
        try:
            max_files = int(log_max_files)
            if max_files < 0:
                errors.append(
                    f"ERROR: Invalid LOG_MAX_FILES value '{max_files}'.\n"
                    f"       LOG_MAX_FILES must be a non-negative integer."
                )
            elif max_files == 0:
                warnings.append(
                    "WARNING: LOG_MAX_FILES is set to 0 which will disable log rotation.\n"
                    "         Only the current log file will be kept. Recommended value: 5 or higher."
                )
            elif max_files > 50:
                warnings.append(
                    f"WARNING: LOG_MAX_FILES is set to {max_files} which will keep many log files.\n"
                    "         This may use significant disk space. Recommended value: 5-10."
                )
        except ValueError:
            errors.append(
                f"ERROR: Invalid LOG_MAX_FILES value '{log_max_files}'.\n"
                f"       LOG_MAX_FILES must be a non-negative integer."
            )

    # Print results
    if warnings:
        print("\n".join(warnings), file=sys.stderr)
        print("", file=sys.stderr)

    if errors:
        print("\n".join(errors), file=sys.stderr)
        print("\nConfiguration validation failed. Please fix the errors above.", file=sys.stderr)
        sys.exit(1)

    print("✓ Environment configuration validated successfully")

if __name__ == "__main__":
    validate_env()
