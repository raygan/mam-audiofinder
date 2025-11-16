#!/usr/bin/env python3
"""
Standalone script to manually apply migration 007/008 columns.
Run this inside the Docker container if automated migrations fail.
"""
import sqlite3
from pathlib import Path

def fix_history_db():
    """Add missing columns to history.db"""
    print("🔧 Fixing history.db...")
    conn = sqlite3.connect('/data/history.db')
    cursor = conn.cursor()

    columns_to_add = [
        ('abs_description', 'TEXT'),
        ('abs_description_source', 'TEXT'),
        ('abs_metadata', 'TEXT'),
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f'ALTER TABLE history ADD COLUMN {col_name} {col_type}')
            print(f"  ✓ Added column: {col_name}")
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                print(f"  ↺ Column already exists: {col_name}")
            else:
                print(f"  ✗ Error adding {col_name}: {e}")

    conn.commit()
    conn.close()
    print("✓ history.db fixed")

def fix_covers_db():
    """Add missing columns to covers.db"""
    print("🔧 Fixing covers.db...")
    conn = sqlite3.connect('/data/covers.db')
    cursor = conn.cursor()

    columns_to_add = [
        ('abs_description', 'TEXT'),
        ('abs_metadata', 'TEXT'),
        ('abs_metadata_fetched_at', 'TEXT'),
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f'ALTER TABLE covers ADD COLUMN {col_name} {col_type}')
            print(f"  ✓ Added column: {col_name}")
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                print(f"  ↺ Column already exists: {col_name}")
            else:
                print(f"  ✗ Error adding {col_name}: {e}")

    conn.commit()
    conn.close()
    print("✓ covers.db fixed")

def verify_columns():
    """Verify the columns exist"""
    print("\n🔍 Verifying columns...")

    # Check history.db
    conn = sqlite3.connect('/data/history.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(history)")
    history_cols = [row[1] for row in cursor.fetchall()]
    conn.close()

    # Check covers.db
    conn = sqlite3.connect('/data/covers.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(covers)")
    covers_cols = [row[1] for row in cursor.fetchall()]
    conn.close()

    # Verify history columns
    required_history = ['abs_description', 'abs_description_source', 'abs_metadata']
    print("\nhistory.db columns:")
    for col in required_history:
        status = "✓" if col in history_cols else "✗"
        print(f"  {status} {col}")

    # Verify covers columns
    required_covers = ['abs_description', 'abs_metadata', 'abs_metadata_fetched_at']
    print("\ncovers.db columns:")
    for col in required_covers:
        status = "✓" if col in covers_cols else "✗"
        print(f"  {status} {col}")

if __name__ == '__main__':
    print("=" * 60)
    print("Manual Migration Fix for 007/008")
    print("=" * 60)
    fix_history_db()
    fix_covers_db()
    verify_columns()
    print("\n✓ Done! Restart the container for changes to take effect.")
