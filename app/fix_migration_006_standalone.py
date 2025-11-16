#!/usr/bin/env python3
"""
Standalone fix for migration 006 - uses only built-in sqlite3
Run this to fix the migration issue without restarting the container
"""
import sqlite3
import os

# Path to database
db_path = '/data/history.db'

# Check if database exists
if not os.path.exists(db_path):
    print(f"ERROR: Database not found at {db_path}")
    print("Make sure you're running this inside the container or with proper volume mounts")
    exit(1)

print(f"Connecting to {db_path}...")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\n1. Removing migration tracking record...")
cursor.execute("DELETE FROM applied_migrations WHERE filename = '006_add_abs_verification.sql'")
print(f"   ✓ Removed tracking record (rows affected: {cursor.rowcount})")

print("\n2. Adding abs_verify_status column...")
try:
    cursor.execute("ALTER TABLE history ADD COLUMN abs_verify_status TEXT")
    print("   ✓ Added abs_verify_status column")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("   ℹ️  Column already exists")
    else:
        print(f"   ✗ Error: {e}")

print("\n3. Adding abs_verify_note column...")
try:
    cursor.execute("ALTER TABLE history ADD COLUMN abs_verify_note TEXT")
    print("   ✓ Added abs_verify_note column")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("   ℹ️  Column already exists")
    else:
        print(f"   ✗ Error: {e}")

print("\n4. Re-adding migration tracking record...")
cursor.execute(
    "INSERT INTO applied_migrations (filename, applied_at) VALUES (?, datetime('now'))",
    ('006_add_abs_verification.sql',)
)
print("   ✓ Added tracking record")

conn.commit()
conn.close()

print("\n✅ Migration 006 has been fixed!")
print("The history page should now work correctly.")
