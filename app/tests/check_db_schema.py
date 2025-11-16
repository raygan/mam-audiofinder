#!/usr/bin/env python3
"""
Database Schema Checker for MAM Audiobook Finder
Displays current schema and applied migrations for both databases.
"""
import sqlite3
from pathlib import Path

def check_database(db_path, db_name, table_name):
    """Check and display database schema and migration status."""
    if not Path(db_path).exists():
        print(f"\n❌ {db_name} not found at {db_path}")
        return

    print(f"\n{'='*70}")
    print(f"{db_name.upper()}")
    print(f"{'='*70}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get table schema
    cursor.execute(f'PRAGMA table_info({table_name})')
    cols = cursor.fetchall()

    print(f"\n{table_name.upper()} Table Columns ({len(cols)}):")
    for col in cols:
        nullable = "NULL" if col[3] == 0 else "NOT NULL"
        default = f" DEFAULT {col[4]}" if col[4] else ""
        pk = " PRIMARY KEY" if col[5] == 1 else ""
        print(f"  {col[1]:30} {col[2]:10} {nullable:8}{default}{pk}")

    # Get applied migrations
    cursor.execute('SELECT filename, applied_at FROM applied_migrations ORDER BY applied_at')
    migrations = cursor.fetchall()

    print(f"\nApplied Migrations ({len(migrations)}):")
    if migrations:
        for mig in migrations:
            print(f"  ✓ {mig[0]:50} {mig[1]}")
    else:
        print("  (none)")

    conn.close()

def main():
    """Main function to check both databases."""
    print("\n🔍 MAM Audiobook Finder - Database Schema Checker")

    # Check history.db
    check_database(
        '/workspace/data/history.db',
        'history.db',
        'history'
    )

    # Check covers.db
    check_database(
        '/workspace/data/covers.db',
        'covers.db',
        'covers'
    )

    print(f"\n{'='*70}")
    print("✅ Schema check complete!")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
