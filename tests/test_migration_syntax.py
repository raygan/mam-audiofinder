#!/usr/bin/env python3
"""Test migration SQL syntax by executing against a temp database"""
import sqlite3
import tempfile
from pathlib import Path

def test_history_migration():
    """Test the history migration SQL"""
    print("Testing history.db migration...")

    # Create temp database with history table
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create minimal history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mam_id TEXT UNIQUE,
            title TEXT,
            author TEXT
        )
    """)
    conn.commit()

    # Read and execute migration - compute path relative to this file
    test_dir = Path(__file__).parent
    project_root = test_dir.parent
    migration_file = project_root / 'app' / 'db' / 'migrations' / '007_add_abs_description_history.sql'
    sql = migration_file.read_text()

    # Split into statements like the migration system does
    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]

    print(f"Found {len(statements)} statements:")
    for i, stmt in enumerate(statements, 1):
        print(f"  {i}. {stmt[:60]}...")
        try:
            cursor.execute(stmt)
            print(f"     ✓ Executed successfully")
        except Exception as e:
            print(f"     ✗ Error: {e}")

    conn.commit()

    # Verify columns were added
    cursor.execute("PRAGMA table_info(history)")
    columns = [row[1] for row in cursor.fetchall()]

    print(f"\nColumns in history table: {columns}")
    print("\nChecking for new columns:")
    for col in ['abs_description', 'abs_description_source', 'abs_metadata']:
        status = "✓" if col in columns else "✗"
        print(f"  {status} {col}")

    conn.close()
    Path(db_path).unlink()

def test_covers_migration():
    """Test the covers migration SQL"""
    print("\n" + "="*60)
    print("Testing covers.db migration...")

    # Create temp database with covers table
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create minimal covers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS covers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mam_id TEXT UNIQUE NOT NULL,
            title TEXT,
            author TEXT,
            cover_url TEXT NOT NULL
        )
    """)
    conn.commit()

    # Read and execute migration - compute path relative to this file
    test_dir = Path(__file__).parent
    project_root = test_dir.parent
    migration_file = project_root / 'app' / 'db' / 'migrations' / '008_add_abs_description_covers.sql'
    sql = migration_file.read_text()

    # Split into statements like the migration system does
    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]

    print(f"Found {len(statements)} statements:")
    for i, stmt in enumerate(statements, 1):
        print(f"  {i}. {stmt[:60]}...")
        try:
            cursor.execute(stmt)
            print(f"     ✓ Executed successfully")
        except Exception as e:
            print(f"     ✗ Error: {e}")

    conn.commit()

    # Verify columns were added
    cursor.execute("PRAGMA table_info(covers)")
    columns = [row[1] for row in cursor.fetchall()]

    print(f"\nColumns in covers table: {columns}")
    print("\nChecking for new columns:")
    for col in ['abs_description', 'abs_metadata', 'abs_metadata_fetched_at']:
        status = "✓" if col in columns else "✗"
        print(f"  {status} {col}")

    conn.close()
    Path(db_path).unlink()

if __name__ == '__main__':
    print("="*60)
    print("Migration Syntax Test")
    print("="*60)
    test_history_migration()
    test_covers_migration()
    print("\n✓ Syntax test complete")
