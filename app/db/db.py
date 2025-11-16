"""
Database module for MAM Audiobook Finder.
Handles database engine setup and migration execution.
"""
import logging
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text

logger = logging.getLogger("mam-audiofinder")

# ---------------------------- Database Engines ----------------------------
# Main history database
engine = create_engine("sqlite:////data/history.db", future=True)

# Covers database - separate from history to cache covers before adding to qBittorrent
# Configure connection pool to handle concurrent cover fetches better
covers_engine = create_engine(
    "sqlite:////data/covers.db",
    future=True,
    pool_size=20,  # Increased from default 5
    max_overflow=30,  # Increased from default 10
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600  # Recycle connections after 1 hour
)

# ---------------------------- Migration System ----------------------------
MIGRATIONS_DIR = Path(__file__).parent / "migrations"

def _ensure_migrations_table(target_engine):
    """Ensure the applied_migrations tracking table exists."""
    with target_engine.begin() as cx:
        cx.execute(text("""
            CREATE TABLE IF NOT EXISTS applied_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT DEFAULT (datetime('now'))
            )
        """))


def run_migrations():
    """
    Execute all SQL migration files in order.
    Migration files are named numerically (001_xxx.sql, 002_xxx.sql, etc.)
    and are executed in order. Each statement is executed independently
    to allow idempotent migrations (e.g., ALTER TABLE ADD COLUMN IF NOT EXISTS).
    """
    if not MIGRATIONS_DIR.exists():
        logger.warning(f"⚠️  Migrations directory not found: {MIGRATIONS_DIR}")
        return

    # Get all .sql files sorted numerically
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    if not migration_files:
        logger.info("ℹ️  No migration files found")
        return

    logger.info(f"🔧 Running {len(migration_files)} migration(s)...")

    # Track which database each migration applies to
    # Migrations 001-004 are for history.db, 005+ are for covers.db
    # Ensure tracking tables exist
    _ensure_migrations_table(engine)
    _ensure_migrations_table(covers_engine)

    pending = 0
    for migration_file in migration_files:
        # Determine target database by examining SQL content
        migration_num = int(migration_file.stem.split("_")[0])
        sql_content = migration_file.read_text().lower()

        # Smart routing: check which table the migration targets
        targets_history = any(pattern in sql_content for pattern in [
            "alter table history",
            "create table history",
            "create table if not exists history",
            "insert into history",
            "create index if not exists idx_history"
        ])

        targets_covers = any(pattern in sql_content for pattern in [
            "alter table covers",
            "create table covers",
            "create table if not exists covers",
            "insert into covers",
            "create index if not exists idx_covers"
        ])

        # Determine target engine
        if targets_history and not targets_covers:
            target_engine = engine
            db_name = "history.db"
        elif targets_covers and not targets_history:
            target_engine = covers_engine
            db_name = "covers.db"
        else:
            # Fallback to legacy logic for migrations that don't clearly target one table
            target_engine = covers_engine if migration_num >= 5 else engine
            db_name = "covers.db" if migration_num >= 5 else "history.db"

        with target_engine.begin() as cx:
            exists = cx.execute(
                text("SELECT 1 FROM applied_migrations WHERE filename = :filename"),
                {"filename": migration_file.name}
            ).fetchone()

        if exists:
            logger.debug(f"  ↺ Skipping already applied migration {migration_file.name}")
            continue

        pending += 1
        logger.info(f"  → {migration_file.name} (target: {db_name})")

        try:
            # Use already-read SQL content (avoid reading file twice)
            sql = migration_file.read_text()

            # Split into individual statements (handles multi-statement files)
            statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]

            # Execute each statement independently (idempotent migrations)
            with target_engine.begin() as cx:
                for statement in statements:
                    try:
                        cx.execute(text(statement))
                    except Exception as e:
                        # Log but don't fail - allows idempotent migrations
                        # (e.g., "ALTER TABLE ADD COLUMN" on already existing column)
                        if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                            logger.debug(f"    ⊘ Skipped (already exists): {statement[:50]}...")
                        else:
                            logger.warning(f"    ⚠️  Error executing statement: {e}")
                            logger.debug(f"    Statement: {statement}")

            with target_engine.begin() as cx:
                cx.execute(
                    text("INSERT INTO applied_migrations (filename, applied_at) VALUES (:filename, :applied_at)"),
                    {"filename": migration_file.name, "applied_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}
                )

            logger.info(f"    ✓ {migration_file.name} completed")

        except Exception as e:
            logger.error(f"    ✗ Migration failed: {migration_file.name}: {e}")
            # Continue with other migrations instead of failing

    if pending == 0:
        logger.info("✓ Database migrations already up to date")
    else:
        logger.info("✓ Database migrations completed")

def initialize_databases():
    """Initialize database schemas by running migrations."""
    run_migrations()
    logger.info("✓ Database schemas initialized")
