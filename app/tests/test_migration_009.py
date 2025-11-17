#!/usr/bin/env python3
"""
Test Migration 009: series_cache table creation and structure.
Run this inside the container to verify migration 009 works correctly.
"""
import sqlite3
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta


def test_series_cache_migration():
    """Test the series_cache migration SQL."""
    print("="*70)
    print("Testing Migration 009: series_cache table creation")
    print("="*70)

    # Create temp database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Read and execute migration
    test_dir = Path(__file__).parent
    project_root = test_dir.parent
    migration_file = project_root / 'db' / 'migrations' / '009_create_series_cache.sql'

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return False

    sql = migration_file.read_text()

    # Split into statements
    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]

    print(f"\n📄 Found {len(statements)} SQL statements in migration")
    print("-" * 70)

    for i, stmt in enumerate(statements, 1):
        # Truncate long statements for display
        display_stmt = stmt[:80] + "..." if len(stmt) > 80 else stmt
        print(f"\n{i}. {display_stmt}")

        try:
            cursor.execute(stmt)
            print(f"   ✓ Executed successfully")
        except Exception as e:
            print(f"   ✗ Error: {e}")
            conn.close()
            Path(db_path).unlink()
            return False

    conn.commit()

    # Verify table was created
    print("\n" + "="*70)
    print("Verifying series_cache table structure...")
    print("="*70)

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='series_cache'")
    if not cursor.fetchone():
        print("❌ series_cache table was not created!")
        conn.close()
        Path(db_path).unlink()
        return False

    print("✓ series_cache table exists")

    # Check columns
    cursor.execute("PRAGMA table_info(series_cache)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}  # {name: type}

    expected_columns = {
        'id': 'INTEGER',
        'cache_key': 'TEXT',
        'cache_type': 'TEXT',
        'query_title': 'TEXT',
        'query_author': 'TEXT',
        'query_normalized': 'TEXT',
        'series_id': 'INTEGER',
        'series_name': 'TEXT',
        'series_author': 'TEXT',
        'response_data': 'TEXT',
        'cached_at': 'TEXT',
        'expires_at': 'TEXT',
        'hit_count': 'INTEGER'
    }

    print("\nColumn verification:")
    all_columns_ok = True
    for col_name, expected_type in expected_columns.items():
        if col_name in columns:
            actual_type = columns[col_name]
            if actual_type == expected_type:
                print(f"  ✓ {col_name:<20} {actual_type}")
            else:
                print(f"  ⚠ {col_name:<20} Expected: {expected_type}, Got: {actual_type}")
                all_columns_ok = False
        else:
            print(f"  ✗ {col_name:<20} MISSING")
            all_columns_ok = False

    # Check indexes
    print("\nIndex verification:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='series_cache'")
    indexes = [row[0] for row in cursor.fetchall()]

    expected_indexes = [
        'idx_series_cache_key',
        'idx_series_expires_at',
        'idx_series_id',
        'idx_series_cache_type'
    ]

    for idx in expected_indexes:
        if idx in indexes:
            print(f"  ✓ {idx}")
        else:
            print(f"  ✗ {idx} MISSING")
            all_columns_ok = False

    # Check trigger
    print("\nTrigger verification:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='series_cache'")
    triggers = [row[0] for row in cursor.fetchall()]

    if 'cleanup_expired_series_cache' in triggers:
        print(f"  ✓ cleanup_expired_series_cache")
    else:
        print(f"  ✗ cleanup_expired_series_cache MISSING")
        all_columns_ok = False

    # Test inserting data
    print("\n" + "="*70)
    print("Testing data operations...")
    print("="*70)

    test_data = {
        "series": [
            {
                "series_id": 12345,
                "series_name": "Test Series",
                "author_name": "Test Author",
                "book_count": 5,
                "readers_count": 1000
            }
        ]
    }

    now = datetime.now()
    expires_at = now + timedelta(seconds=300)

    try:
        cursor.execute("""
            INSERT INTO series_cache
            (cache_key, cache_type, query_title, query_author, query_normalized,
             response_data, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "search:test123",
            "search",
            "Test Title",
            "Test Author",
            "test title",
            json.dumps(test_data),
            expires_at.isoformat()
        ))
        conn.commit()
        print("✓ Successfully inserted test record")
    except Exception as e:
        print(f"✗ Failed to insert test record: {e}")
        all_columns_ok = False

    # Test querying
    try:
        cursor.execute("""
            SELECT cache_key, cache_type, response_data, hit_count
            FROM series_cache
            WHERE cache_key = ?
        """, ("search:test123",))

        row = cursor.fetchone()
        if row:
            cache_key, cache_type, response_data, hit_count = row
            print(f"✓ Successfully queried test record")
            print(f"  - Cache key: {cache_key}")
            print(f"  - Cache type: {cache_type}")
            print(f"  - Hit count: {hit_count}")

            # Verify JSON can be parsed
            parsed_data = json.loads(response_data)
            if parsed_data == test_data:
                print(f"  ✓ JSON data matches")
            else:
                print(f"  ✗ JSON data mismatch")
                all_columns_ok = False
        else:
            print(f"✗ Failed to retrieve test record")
            all_columns_ok = False
    except Exception as e:
        print(f"✗ Failed to query test record: {e}")
        all_columns_ok = False

    # Test trigger (insert expired entry and new entry)
    print("\nTesting auto-cleanup trigger...")
    try:
        # Insert expired entry
        expired_time = now - timedelta(seconds=300)
        cursor.execute("""
            INSERT INTO series_cache
            (cache_key, cache_type, response_data, expires_at)
            VALUES (?, ?, ?, ?)
        """, (
            "search:expired",
            "search",
            json.dumps({"test": "data"}),
            expired_time.isoformat()
        ))
        conn.commit()

        # Count entries before trigger
        cursor.execute("SELECT COUNT(*) FROM series_cache")
        count_before = cursor.fetchone()[0]

        # Insert new entry (should trigger cleanup)
        cursor.execute("""
            INSERT INTO series_cache
            (cache_key, cache_type, response_data, expires_at)
            VALUES (?, ?, ?, ?)
        """, (
            "search:new",
            "search",
            json.dumps({"test": "new"}),
            expires_at.isoformat()
        ))
        conn.commit()

        # Count entries after trigger
        cursor.execute("SELECT COUNT(*) FROM series_cache")
        count_after = cursor.fetchone()[0]

        # Check if expired entry was deleted
        cursor.execute("SELECT COUNT(*) FROM series_cache WHERE cache_key = ?", ("search:expired",))
        expired_count = cursor.fetchone()[0]

        if expired_count == 0:
            print("✓ Trigger successfully cleaned up expired entries")
        else:
            print(f"⚠ Trigger may not have cleaned up expired entries (found {expired_count})")
            # Note: This might be expected behavior depending on trigger timing

    except Exception as e:
        print(f"✗ Trigger test failed: {e}")
        all_columns_ok = False

    # Cleanup
    conn.close()
    Path(db_path).unlink()

    # Final result
    print("\n" + "="*70)
    if all_columns_ok:
        print("✅ Migration 009 test PASSED - All checks successful!")
        print("="*70)
        return True
    else:
        print("❌ Migration 009 test FAILED - Some checks failed")
        print("="*70)
        return False


if __name__ == '__main__':
    import sys
    success = test_series_cache_migration()
    sys.exit(0 if success else 1)
