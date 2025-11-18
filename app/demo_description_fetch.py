#!/usr/bin/env python3
"""
Demo script for unified description service.
Demonstrates real API calls to ABS and Hardcover with actual book titles.

Usage:
    python demo_description_fetch.py
"""
import asyncio
import sys
from description_service import description_service
from config import ABS_BASE_URL, ABS_API_KEY, HARDCOVER_API_TOKEN


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_result(result, book_title):
    """Print a formatted result."""
    print(f"\n📖 Book: {book_title}")
    print(f"   Source: {result['source']}")
    print(f"   Cached: {result['cached']}")
    print(f"   Fetched: {result['fetched_at']}")

    description = result.get('description', '')
    if description:
        # Truncate long descriptions
        if len(description) > 300:
            print(f"   Description: {description[:300]}...")
            print(f"   (Total length: {len(description)} characters)")
        else:
            print(f"   Description: {description}")
    else:
        print(f"   Description: (none found)")

    # Show metadata if available
    metadata = result.get('metadata', {})
    if metadata:
        if 'book_id' in metadata:
            print(f"   Hardcover ID: {metadata.get('book_id')}")

        # Handle authors (can be list of strings or list of dicts with 'name' field)
        if 'authors' in metadata:
            authors_raw = metadata.get('authors', [])
            if authors_raw:
                # Convert to list of strings if needed
                author_names = []
                for author in authors_raw:
                    if isinstance(author, str):
                        author_names.append(author)
                    elif isinstance(author, dict):
                        # ABS format: {"id": "...", "name": "Author Name"}
                        author_names.append(author.get('name', 'Unknown'))
                    else:
                        author_names.append(str(author))

                if author_names:
                    print(f"   Authors: {', '.join(author_names)}")

        if 'series_names' in metadata:
            series = metadata.get('series_names', [])
            if series:
                print(f"   Series: {', '.join(series)}")


async def demo_abs_fetch():
    """Demonstrate fetching from ABS (if configured)."""
    print_section("TEST 1: Audiobookshelf API (if configured)")

    if not ABS_BASE_URL or not ABS_API_KEY:
        print("⚠️  Audiobookshelf not configured (ABS_BASE_URL or ABS_API_KEY missing)")
        print("   Set these env vars to test ABS integration")
        return

    print(f"✅ ABS configured: {ABS_BASE_URL}")

    # Test with a popular audiobook (adjust based on your library)
    test_books = [
        ("Project Hail Mary", "Andy Weir"),
        ("The Way of Kings", "Brandon Sanderson"),
        ("Dune", "Frank Herbert"),
    ]

    for title, author in test_books:
        try:
            result = await description_service.get_description(
                title=title,
                author=author,
                force_refresh=True  # Skip cache to test real API
            )
            print_result(result, f"{title} by {author}")
        except Exception as e:
            print(f"❌ Error fetching '{title}': {e}")


async def demo_hardcover_fetch():
    """Demonstrate fetching from Hardcover API (if configured)."""
    print_section("TEST 2: Hardcover API (if configured)")

    if not HARDCOVER_API_TOKEN:
        print("⚠️  Hardcover not configured (HARDCOVER_API_TOKEN missing)")
        print("   Set this env var to test Hardcover integration")
        print("   Get token from: https://hardcover.app/settings/api")
        return

    print(f"✅ Hardcover configured")

    # Test with popular books that should be in Hardcover
    test_books = [
        ("Project Hail Mary", "Andy Weir"),
        ("The Midnight Library", "Matt Haig"),
        ("Atomic Habits", "James Clear"),
        ("Circe", "Madeline Miller"),
    ]

    for title, author in test_books:
        try:
            result = await description_service.get_description(
                title=title,
                author=author,
                force_refresh=True  # Skip cache to test real API
            )
            print_result(result, f"{title} by {author}")
        except Exception as e:
            print(f"❌ Error fetching '{title}': {e}")


async def demo_fallback_logic():
    """Demonstrate the ABS → Hardcover fallback logic."""
    print_section("TEST 3: Fallback Logic (ABS → Hardcover)")

    if not HARDCOVER_API_TOKEN:
        print("⚠️  Hardcover not configured, cannot test fallback")
        print("   Fallback only works if Hardcover is configured")
        return

    print("Testing with a book likely NOT in your ABS library...")
    print("(Should fallback to Hardcover)")

    # Use obscure/new books unlikely to be in local ABS library
    test_books = [
        ("Tomorrow, and Tomorrow, and Tomorrow", "Gabrielle Zevin"),
        ("Lessons in Chemistry", "Bonnie Garmus"),
        ("The Seven Husbands of Evelyn Hugo", "Taylor Jenkins Reid"),
    ]

    for title, author in test_books:
        try:
            result = await description_service.get_description(
                title=title,
                author=author,
                force_refresh=True
            )
            print_result(result, f"{title} by {author}")

            # Highlight fallback
            if result['source'] == 'hardcover':
                print("   ✨ Successfully fell back to Hardcover!")
            elif result['source'] == 'abs':
                print("   ℹ️  Found in your ABS library (no fallback needed)")

        except Exception as e:
            print(f"❌ Error fetching '{title}': {e}")


async def demo_caching():
    """Demonstrate caching behavior."""
    print_section("TEST 4: Caching Behavior")

    title = "Project Hail Mary"
    author = "Andy Weir"

    print(f"Fetching description for '{title}' twice...")
    print("\nFirst call (should hit API):")

    # First call - should hit API
    result1 = await description_service.get_description(
        title=title,
        author=author,
        force_refresh=True
    )
    print_result(result1, f"{title} by {author}")

    print("\n\nSecond call (should hit cache):")

    # Second call - should hit cache
    result2 = await description_service.get_description(
        title=title,
        author=author
    )
    print_result(result2, f"{title} by {author}")

    if result2['cached']:
        print("\n   ✨ Cache hit! No API call made on second request")
    else:
        print("\n   ⚠️  Cache miss (unexpected)")

    # Show cache stats
    stats = description_service.get_cache_stats()
    print("\n📊 Cache Statistics:")
    print(f"   Total entries: {stats['total_entries']}")
    print(f"   Valid entries: {stats['valid_entries']}")
    print(f"   Cache TTL: {stats['cache_ttl']} seconds ({stats['cache_ttl']/3600:.1f} hours)")
    print(f"   Fallback enabled: {stats['fallback_enabled']}")


async def demo_identifier_matching():
    """Demonstrate ASIN/ISBN identifier matching."""
    print_section("TEST 5: Identifier Matching (ASIN/ISBN)")

    if not ABS_BASE_URL or not ABS_API_KEY:
        print("⚠️  Requires ABS configuration to test identifier matching")
        return

    print("Testing ASIN/ISBN matching (if available in your library)...")
    print("Note: These are examples - adjust based on your library")

    # Example with ASIN (you'll need to check your library for real ASINs)
    test_cases = [
        {
            "title": "Dune",
            "author": "Frank Herbert",
            "asin": "B00JDQTL08",  # Example ASIN
            "note": "ASIN match test"
        },
        {
            "title": "The Martian",
            "author": "Andy Weir",
            "isbn": "9780553418026",  # Example ISBN
            "note": "ISBN match test"
        },
    ]

    for test in test_cases:
        print(f"\n{test['note']}: {test['title']}")
        try:
            result = await description_service.get_description(
                title=test['title'],
                author=test['author'],
                asin=test.get('asin', ''),
                isbn=test.get('isbn', ''),
                force_refresh=True
            )
            print_result(result, test['title'])
        except Exception as e:
            print(f"❌ Error: {e}")


async def main():
    """Run all demo tests."""
    print("\n" + "🚀" * 40)
    print("  UNIFIED DESCRIPTION SERVICE - LIVE API DEMO")
    print("🚀" * 40)

    print("\nThis demo will make REAL API calls to:")
    print("  • Audiobookshelf (if ABS_BASE_URL and ABS_API_KEY are set)")
    print("  • Hardcover (if HARDCOVER_API_TOKEN is set)")
    print("\nResults will show actual descriptions from these services.")

    # Run demos
    await demo_abs_fetch()
    await demo_hardcover_fetch()
    await demo_fallback_logic()
    await demo_caching()
    await demo_identifier_matching()

    print("\n" + "=" * 80)
    print("  DEMO COMPLETE")
    print("=" * 80)
    print("\nℹ️  To customize this demo:")
    print("   1. Edit the test_books lists with titles from your library")
    print("   2. Add your actual ASINs/ISBNs for identifier matching tests")
    print("   3. Set ABS_BASE_URL, ABS_API_KEY, and HARDCOVER_API_TOKEN env vars")
    print("\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
