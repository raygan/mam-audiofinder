#!/usr/bin/env python3
"""
Test script to verify description fetching after import verification.
This simulates the verification process and checks if descriptions are saved.
"""
import asyncio
import sqlite3
from pathlib import Path

# Add app directory to path for imports
import sys
sys.path.insert(0, '/workspace/app')

async def test_description_update():
    """Test the description update functionality."""
    print("=" * 70)
    print("TESTING DESCRIPTION FETCH AFTER VERIFICATION")
    print("=" * 70)

    # Import after path setup
    from abs_client import abs_client
    from config import ABS_BASE_URL, ABS_API_KEY, ABS_LIBRARY_ID

    # Check configuration
    print(f"\n1. Configuration Check:")
    print(f"   ABS_BASE_URL: {ABS_BASE_URL or '(not set)'}")
    print(f"   ABS_API_KEY: {'***' + ABS_API_KEY[-8:] if ABS_API_KEY else '(not set)'}")
    print(f"   ABS_LIBRARY_ID: {ABS_LIBRARY_ID or '(not set)'}")

    if not abs_client.is_configured:
        print("\n❌ ABS is not configured. Cannot test.")
        print("   Please set ABS_BASE_URL, ABS_API_KEY, and ABS_LIBRARY_ID in .env")
        return

    # Check if there are any books in history
    print(f"\n2. Checking history.db for test candidates:")
    conn = sqlite3.connect('/workspace/data/history.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, mam_id, title, author, abs_item_id, abs_description
        FROM history
        WHERE imported_at IS NOT NULL
        ORDER BY imported_at DESC
        LIMIT 5
    """)

    history_rows = cursor.fetchall()
    conn.close()

    if not history_rows:
        print("   No imported books found in history.")
        print("   Please import a book first, then run this test.")
        return

    print(f"   Found {len(history_rows)} imported book(s):")
    for row in history_rows:
        desc_status = "✓" if row[5] else "✗"
        print(f"   [{desc_status}] {row[2][:50]} by {row[3][:30] if row[3] else '(no author)'}")

    # Test with first imported book without description
    test_book = None
    for row in history_rows:
        if not row[5]:  # No description yet
            test_book = row
            break

    if not test_book:
        print("\n   All imported books already have descriptions!")
        print("   Showing sample description from first book:")
        first = history_rows[0]
        print(f"\n   Title: {first[2]}")
        print(f"   Description: {first[5][:200]}..." if first[5] else "   (none)")
        return

    book_id, mam_id, title, author, abs_item_id, current_desc = test_book

    print(f"\n3. Testing description fetch for:")
    print(f"   Title: {title}")
    print(f"   Author: {author or '(unknown)'}")
    print(f"   ABS Item ID: {abs_item_id or '(not set)'}")
    print(f"   Current description: {current_desc or '(none)'}")

    # If no abs_item_id, try verification first
    if not abs_item_id:
        print(f"\n4. No ABS item ID found, running verification...")
        result = await abs_client.verify_import(title, author or "")
        print(f"   Verification result: {result['status']}")
        print(f"   Note: {result['note']}")
        abs_item_id = result.get('abs_item_id')

        if not abs_item_id:
            print(f"\n❌ Could not verify book in ABS library.")
            print(f"   Make sure the book is imported and scanned in Audiobookshelf.")
            return
    else:
        print(f"\n4. Book already has ABS item ID, testing description update...")
        # Manually call the update function
        await abs_client._update_description_after_verification(abs_item_id, title, author or "")

    # Check if description was saved
    print(f"\n5. Checking if description was saved...")

    conn = sqlite3.connect('/workspace/data/history.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT abs_description, abs_metadata, abs_description_source
        FROM history
        WHERE id = ?
    """, (book_id,))

    updated_row = cursor.fetchone()
    conn.close()

    if updated_row and updated_row[0]:
        print(f"\n✅ SUCCESS! Description was saved to history.db")
        print(f"\n   Description preview:")
        desc = updated_row[0]
        print(f"   {desc[:300]}{'...' if len(desc) > 300 else ''}")
        print(f"\n   Metadata source: {updated_row[2] or '(not set)'}")
        print(f"   Metadata size: {len(updated_row[1]) if updated_row[1] else 0} bytes")
    else:
        print(f"\n⚠️  Description not found in database after update.")
        print(f"   Check logs for errors during fetch/save.")

    # Check covers.db too
    if mam_id:
        print(f"\n6. Checking covers.db for MAM ID {mam_id}...")
        conn = sqlite3.connect('/workspace/data/covers.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT abs_description, abs_metadata
            FROM covers
            WHERE mam_id = ?
        """, (mam_id,))

        cover_row = cursor.fetchone()
        conn.close()

        if cover_row and cover_row[0]:
            print(f"   ✅ Description also saved to covers.db")
            print(f"   Description length: {len(cover_row[0])} characters")
        else:
            print(f"   ⚠️  No description in covers.db (may not have cover cached)")

    print(f"\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_description_update())
