#!/usr/bin/env python3
"""
Test Hardcover API integration.
Run this inside the container to verify Hardcover API configuration and connectivity.

Usage:
    python test_hardcover_api.py                    # Run all tests
    python test_hardcover_api.py --search "Mistborn" # Test series search only
    python test_hardcover_api.py --series 12345     # Test series books only
    python test_hardcover_api.py --author "Brandon Sanderson" # Test author search
    python test_hardcover_api.py --framework basic  # Run specific framework tests
    python test_hardcover_api.py --limits           # Test limit variations
"""
import sys
import asyncio
import argparse
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import HARDCOVER_API_TOKEN, HARDCOVER_BASE_URL, HARDCOVER_CACHE_TTL
from hardcover_client import hardcover_client


def print_header(title):
    """Print formatted section header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def print_result(label, value, indent=0):
    """Print formatted result."""
    prefix = "  " * indent
    print(f"{prefix}{label:<30} {value}")


def print_request_stats(start_count: int, start_cache: int, label: str = "Test"):
    """Print request statistics."""
    end_count = hardcover_client.get_request_count()
    end_cache = hardcover_client.get_cache_hit_count()
    requests_made = end_count - start_count
    cache_hits = end_cache - start_cache
    print(f"\n📊 {label} Statistics:")
    print_result("API Requests Made:", requests_made, indent=1)
    print_result("Cache Hits:", cache_hits, indent=1)
    print_result("Total Requests (session):", end_count, indent=1)
    print_result("Total Cache Hits (session):", end_cache, indent=1)


async def wait_between_tests(seconds: float = 1.0):
    """Wait between tests to avoid rate limiting."""
    print(f"\n⏱️  Waiting {seconds}s between tests...")
    await asyncio.sleep(seconds)


async def test_configuration():
    """Test Hardcover API configuration."""
    print_header("Configuration Check")

    config_ok = True

    # Check API token
    if HARDCOVER_API_TOKEN:
        token_display = HARDCOVER_API_TOKEN[:8] + "..." + HARDCOVER_API_TOKEN[-4:] if len(HARDCOVER_API_TOKEN) > 12 else "***"
        print_result("✓ API Token:", f"Configured ({token_display})")
    else:
        print_result("✗ API Token:", "NOT CONFIGURED")
        config_ok = False

    # Check base URL
    if HARDCOVER_BASE_URL:
        print_result("✓ Base URL:", HARDCOVER_BASE_URL)
    else:
        print_result("✗ Base URL:", "NOT CONFIGURED")
        config_ok = False

    # Check cache TTL
    print_result("✓ Cache TTL:", f"{HARDCOVER_CACHE_TTL}s")

    # Check client status
    if hardcover_client.is_configured:
        print_result("✓ Client Status:", "Ready")
    else:
        print_result("✗ Client Status:", "Not configured")
        config_ok = False

    return config_ok


async def test_series_search(query="Mistborn", author="", limit=5):
    """Test series search functionality."""
    print_header(f"Series Search Test: '{query}'")

    if not hardcover_client.is_configured:
        print("⚠️  Skipping test - Hardcover API not configured")
        return False

    try:
        print(f"\n🔍 Searching for series: '{query}'")
        if author:
            print(f"   Author filter: '{author}'")
        print(f"   Limit: {limit}")

        results = await hardcover_client.search_series(
            title=query,
            author=author,
            limit=limit
        )

        # Check if API call failed (returns None)
        if results is None:
            print("\n❌ API call failed - check logs above for details")
            return False

        print(f"\n✅ Search returned {len(results)} results\n")

        if not results:
            print("ℹ️  No series found matching query (this is OK)")
            return True

        for i, series in enumerate(results, 1):
            print(f"Result #{i}:")
            print_result("Series ID:", series.get('series_id'), indent=1)
            print_result("Name:", series.get('series_name'), indent=1)
            print_result("Author:", series.get('author_name'), indent=1)
            print_result("Book Count:", series.get('book_count'), indent=1)
            print_result("Readers:", series.get('readers_count'), indent=1)
            books = series.get('books', [])
            if books:
                print_result("Book Titles:", f"({len(books)} titles)", indent=1)
                for j, title in enumerate(books[:3], 1):  # Show first 3
                    print_result(f"  {j}.", title, indent=1)
                if len(books) > 3:
                    print_result("  ...", f"(+{len(books)-3} more)", indent=1)
            print()

        return True

    except Exception as e:
        print(f"\n❌ Search failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_series_books(series_id=None):
    """Test fetching books for a series."""
    if series_id is None:
        # First search for a series to test with
        print_header("Finding a test series...")
        try:
            results = await hardcover_client.search_series("Stormlight", limit=1)
            if results is None:
                print("❌ API call failed when searching for test series")
                return False
            if not results:
                print("⚠️  Could not find test series, skipping books test")
                return True
            series_id = results[0]['series_id']
            print(f"✓ Using series: {results[0]['series_name']} (ID: {series_id})")
        except Exception as e:
            print(f"❌ Failed to find test series: {e}")
            return False

    print_header(f"Series Books Test: ID {series_id}")

    if not hardcover_client.is_configured:
        print("⚠️  Skipping test - Hardcover API not configured")
        return False

    try:
        print(f"\n📚 Fetching books for series ID {series_id}...")

        result = await hardcover_client.list_series_books(series_id)

        if not result:
            print(f"❌ Series {series_id} not found")
            return False

        print(f"\n✅ Series found: {result['series_name']}")
        print(f"   Author: {result['author_name']}")
        print(f"   Books: {len(result['books'])}\n")

        # Note: Books are now simple title strings (limited to 5) from search endpoint
        print("   📚 Book titles (from search results, limited to top 5):")
        for i, book_title in enumerate(result['books'], 1):
            print(f"      {i}. {book_title}")

        return True

    except Exception as e:
        print(f"\n❌ Books fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_rate_limiting():
    """Test rate limiting mechanism."""
    print_header("Rate Limiting Test")

    if not hardcover_client.is_configured:
        print("⚠️  Skipping test - Hardcover API not configured")
        return False

    print("\n🔄 Testing rate limiter (sending 3 rapid requests)...")

    try:
        import time
        start = time.time()

        # Send 3 rapid search requests
        for i in range(3):
            print(f"\n  Request {i+1}...")
            result = await hardcover_client.search_series("Test", limit=1)
            if result is None:
                print(f"    ❌ Request {i+1} failed")
                return False

        elapsed = time.time() - start
        print(f"\n✓ Completed 3 requests in {elapsed:.2f}s")

        if elapsed < 0.5:
            print("  ✓ Rate limiter allows rapid sequential requests")
        else:
            print("  ℹ️  Some delay observed (expected if approaching limit)")

        return True

    except Exception as e:
        print(f"\n❌ Rate limiting test failed: {e}")
        return False


async def test_caching():
    """Test caching mechanism."""
    print_header("Caching Test")

    if not hardcover_client.is_configured:
        print("⚠️  Skipping test - Hardcover API not configured")
        return False

    print("\n💾 Testing cache (same query twice)...")

    try:
        import time

        # First request (should hit API)
        print("\n  Request 1 (should query API)...")
        start1 = time.time()
        result1 = await hardcover_client.search_series("Mistborn", limit=3)
        time1 = time.time() - start1
        if result1 is None:
            print("  ❌ First request failed")
            return False
        print(f"  ✓ Completed in {time1:.3f}s")

        # Second request (should hit cache)
        print("\n  Request 2 (should hit cache)...")
        start2 = time.time()
        result2 = await hardcover_client.search_series("Mistborn", limit=3)
        time2 = time.time() - start2
        if result2 is None:
            print("  ❌ Second request failed")
            return False
        print(f"  ✓ Completed in {time2:.3f}s")

        # Compare results
        if result1 == result2:
            print("\n  ✓ Results match")
        else:
            print("\n  ⚠ Results differ (unexpected)")

        # Check if second request was faster (cache hit)
        if time2 < time1 * 0.5:  # At least 50% faster
            print(f"  ✓ Cache speedup detected ({time1/time2:.1f}x faster)")
        else:
            print(f"  ℹ️  No significant speedup (may still be cached)")

        return True

    except Exception as e:
        print(f"\n❌ Caching test failed: {e}")
        return False


async def test_author_series_search(author="Brandon Sanderson", limit=10):
    """Test series search by author name."""
    print_header(f"Author Series Search Test: '{author}'")

    if not hardcover_client.is_configured:
        print("⚠️  Skipping test - Hardcover API not configured")
        return False

    try:
        # Track requests
        start_req = hardcover_client.get_request_count()
        start_cache = hardcover_client.get_cache_hit_count()

        print(f"\n🔍 Searching for series by author: '{author}'")
        print(f"   Limit: {limit}")

        results = await hardcover_client.get_series_by_author(
            author_name=author,
            limit=limit
        )

        if results is None:
            print("\n❌ API call failed - check logs above for details")
            print_request_stats(start_req, start_cache, "Author Series Search")
            return False

        print(f"\n✅ Search returned {len(results)} series\n")

        if not results:
            print("ℹ️  No series found for this author (this may be OK)")
            print_request_stats(start_req, start_cache, "Author Series Search")
            return True

        for i, series in enumerate(results[:5], 1):  # Show first 5
            print(f"Series #{i}:")
            print_result("Series ID:", series.get('series_id'), indent=1)
            print_result("Name:", series.get('series_name'), indent=1)
            print_result("Author:", series.get('author_name'), indent=1)
            print_result("Book Count:", series.get('book_count'), indent=1)
            books = series.get('books', [])
            if books:
                print_result("Books:", f"{len(books)} titles", indent=1)
                for j, title in enumerate(books[:3], 1):
                    print_result(f"  {j}.", title, indent=1)
            print()

        if len(results) > 5:
            print(f"   ... and {len(results) - 5} more series\n")

        print_request_stats(start_req, start_cache, "Author Series Search")
        return True

    except Exception as e:
        print(f"\n❌ Author series search failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_limit_variations():
    """Test different limit values."""
    print_header("Limit Variation Tests")

    if not hardcover_client.is_configured:
        print("⚠️  Skipping test - Hardcover API not configured")
        return False

    limits_to_test = [1, 5, 10, 20]
    test_query = "Stormlight"

    try:
        start_req = hardcover_client.get_request_count()
        start_cache = hardcover_client.get_cache_hit_count()

        for limit in limits_to_test:
            print(f"\n🔍 Testing limit={limit} for query '{test_query}'")

            results = await hardcover_client.search_series(test_query, limit=limit)

            if results is None:
                print(f"  ❌ API call failed for limit={limit}")
                continue

            actual_count = len(results)
            print(f"  ✅ Requested: {limit}, Received: {actual_count}")

            if actual_count <= limit:
                print(f"  ✓ Result count respects limit")
            else:
                print(f"  ⚠️  Result count exceeds limit!")

            # Wait between requests to avoid rate limiting
            if limit != limits_to_test[-1]:
                await asyncio.sleep(0.5)

        print_request_stats(start_req, start_cache, "Limit Variations")
        return True

    except Exception as e:
        print(f"\n❌ Limit variation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_field_extraction():
    """Test extraction of specific fields from series data."""
    print_header("Field Extraction Test")

    if not hardcover_client.is_configured:
        print("⚠️  Skipping test - Hardcover API not configured")
        return False

    try:
        start_req = hardcover_client.get_request_count()
        start_cache = hardcover_client.get_cache_hit_count()

        print(f"\n🔍 Searching for series to test field extraction")

        results = await hardcover_client.search_series("Mistborn", limit=3)

        if results is None:
            print("\n❌ API call failed")
            print_request_stats(start_req, start_cache, "Field Extraction")
            return False

        if not results:
            print("\n⚠️  No results found")
            print_request_stats(start_req, start_cache, "Field Extraction")
            return True

        print(f"\n✅ Testing field extraction on {len(results)} series\n")

        # Fields to check
        expected_fields = ['series_id', 'series_name', 'author_name', 'book_count', 'readers_count', 'books']

        all_passed = True
        for i, series in enumerate(results, 1):
            print(f"Series #{i}: {series.get('series_name', 'Unknown')}")

            for field in expected_fields:
                if field in series:
                    value = series[field]
                    value_type = type(value).__name__
                    if field == 'books' and isinstance(value, list):
                        print_result(f"✓ {field}:", f"list[{len(value)}] - {value_type}", indent=1)
                    else:
                        print_result(f"✓ {field}:", f"{value} ({value_type})", indent=1)
                else:
                    print_result(f"✗ {field}:", "MISSING", indent=1)
                    all_passed = False

            print()

        print_request_stats(start_req, start_cache, "Field Extraction")
        return all_passed

    except Exception as e:
        print(f"\n❌ Field extraction test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_books_by_author(author="Brandon Sanderson", limit=10):
    """Test fetching books by author with field selection."""
    print_header(f"Books By Author Test: '{author}'")

    if not hardcover_client.is_configured:
        print("⚠️  Skipping test - Hardcover API not configured")
        return False

    try:
        start_req = hardcover_client.get_request_count()
        start_cache = hardcover_client.get_cache_hit_count()

        # Test with different field combinations
        field_sets = [
            ["title", "description"],
            ["title", "series_names"],
            ["title", "description", "series_names", "book_series"],
        ]

        for i, fields in enumerate(field_sets, 1):
            print(f"\n🔍 Test {i}: Fetching books with fields: {', '.join(fields)}")

            results = await hardcover_client.search_books_by_author(
                author_name=author,
                limit=limit,
                fields=fields
            )

            if results is None:
                print(f"  ❌ API call failed for field set {i}")
                continue

            print(f"  ✅ Retrieved {len(results)} books")

            if results:
                # Show first book as example
                first_book = results[0]
                print(f"\n  Example (first book):")
                for field in fields:
                    value = first_book.get(field)
                    if isinstance(value, list):
                        print_result(field + ":", f"[{len(value)} items]", indent=2)
                    elif isinstance(value, str) and len(value) > 60:
                        print_result(field + ":", value[:60] + "...", indent=2)
                    else:
                        print_result(field + ":", value, indent=2)

            # Wait between requests
            if i < len(field_sets):
                await asyncio.sleep(0.5)

        print_request_stats(start_req, start_cache, "Books By Author")
        return True

    except Exception as e:
        print(f"\n❌ Books by author test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_series_names_field():
    """Test extraction of series_names field specifically."""
    print_header("Series Names Field Test")

    if not hardcover_client.is_configured:
        print("⚠️  Skipping test - Hardcover API not configured")
        return False

    try:
        start_req = hardcover_client.get_request_count()
        start_cache = hardcover_client.get_cache_hit_count()

        print(f"\n🔍 Searching for books with series_names field")

        # Search for a known series author
        results = await hardcover_client.search_books_by_author(
            author_name="Brandon Sanderson",
            limit=10,
            fields=["title", "series_names"]
        )

        if results is None:
            print("\n❌ API call failed")
            print_request_stats(start_req, start_cache, "Series Names Field")
            return False

        print(f"\n✅ Retrieved {len(results)} books\n")

        books_with_series = 0
        for i, book in enumerate(results[:5], 1):
            title = book.get('title', 'Unknown')
            series_names = book.get('series_names', [])

            print(f"Book #{i}: {title}")
            if series_names:
                books_with_series += 1
                print_result("Series Names:", series_names, indent=1)
            else:
                print_result("Series Names:", "(none)", indent=1)
            print()

        print(f"📊 {books_with_series}/{len(results[:5])} books have series information")
        print_request_stats(start_req, start_cache, "Series Names Field")
        return True

    except Exception as e:
        print(f"\n❌ Series names field test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_framework_basic():
    """Basic testing framework - simple searches with request counting."""
    print_header("Framework: Basic Tests")

    if not hardcover_client.is_configured:
        print("⚠️  Skipping framework - Hardcover API not configured")
        return False

    # Reset counters for this framework
    hardcover_client.reset_counters()
    start_time = time.time()

    tests = [
        ("Mistborn", ""),
        ("Stormlight", ""),
        ("Kingkiller", ""),
    ]

    try:
        for query, author in tests:
            print(f"\n🔍 Searching: '{query}'")
            results = await hardcover_client.search_series(query, author=author, limit=5)

            if results is None:
                print(f"  ❌ Failed")
                continue

            print(f"  ✅ Found {len(results)} results")
            await asyncio.sleep(0.5)  # Wait between requests

        elapsed = time.time() - start_time
        print(f"\n✅ Basic framework completed in {elapsed:.2f}s")
        print_request_stats(0, 0, "Basic Framework")
        return True

    except Exception as e:
        print(f"\n❌ Basic framework failed: {e}")
        return False


async def test_framework_author_focused():
    """Author-focused testing framework - tests series discovery by author."""
    print_header("Framework: Author-Focused Tests")

    if not hardcover_client.is_configured:
        print("⚠️  Skipping framework - Hardcover API not configured")
        return False

    # Reset counters for this framework
    hardcover_client.reset_counters()
    start_time = time.time()

    authors = [
        "Brandon Sanderson",
        "Patrick Rothfuss",
        "Joe Abercrombie",
    ]

    try:
        for author in authors:
            print(f"\n🔍 Author: '{author}'")

            # Get series
            series_results = await hardcover_client.get_series_by_author(author, limit=5)
            if series_results:
                print(f"  ✅ Series: {len(series_results)}")

            await asyncio.sleep(0.5)

            # Get books
            book_results = await hardcover_client.search_books_by_author(
                author, limit=5, fields=["title", "series_names"]
            )
            if book_results:
                print(f"  ✅ Books: {len(book_results)}")

            await asyncio.sleep(0.5)

        elapsed = time.time() - start_time
        print(f"\n✅ Author-focused framework completed in {elapsed:.2f}s")
        print_request_stats(0, 0, "Author-Focused Framework")
        return True

    except Exception as e:
        print(f"\n❌ Author-focused framework failed: {e}")
        return False


async def test_framework_field_validation():
    """Field validation framework - comprehensive field testing."""
    print_header("Framework: Field Validation Tests")

    if not hardcover_client.is_configured:
        print("⚠️  Skipping framework - Hardcover API not configured")
        return False

    # Reset counters for this framework
    hardcover_client.reset_counters()
    start_time = time.time()

    field_combinations = [
        ["title"],
        ["title", "description"],
        ["title", "series_names"],
        ["title", "description", "series_names"],
        ["title", "book_series"],
        ["title", "list_books"],
    ]

    try:
        for i, fields in enumerate(field_combinations, 1):
            print(f"\n🔍 Test {i}/{len(field_combinations)}: {', '.join(fields)}")

            results = await hardcover_client.search_books_by_author(
                "Brandon Sanderson",
                limit=3,
                fields=fields
            )

            if results:
                print(f"  ✅ Retrieved {len(results)} books")

                # Validate fields exist
                if results:
                    first_book = results[0]
                    for field in fields:
                        if field in first_book:
                            print(f"     ✓ {field}")
                        else:
                            print(f"     ✗ {field} (missing)")

            await asyncio.sleep(0.5)

        elapsed = time.time() - start_time
        print(f"\n✅ Field validation framework completed in {elapsed:.2f}s")
        print_request_stats(0, 0, "Field Validation Framework")
        return True

    except Exception as e:
        print(f"\n❌ Field validation framework failed: {e}")
        return False


async def run_all_tests():
    """Run all tests."""
    print("\n" + "🧪 "*25)
    print("  HARDCOVER API INTEGRATION TEST SUITE")
    print("🧪 "*25)

    results = []

    # Reset counters at start
    hardcover_client.reset_counters()

    # Test 1: Configuration
    results.append(("Configuration", await test_configuration()))
    await wait_between_tests(0.5)

    # Test 2: Series Search
    results.append(("Series Search", await test_series_search("Mistborn")))
    await wait_between_tests(1.0)

    # Test 3: Series Books
    results.append(("Series Books", await test_series_books()))
    await wait_between_tests(1.0)

    # Test 4: Rate Limiting
    results.append(("Rate Limiting", await test_rate_limiting()))
    await wait_between_tests(1.0)

    # Test 5: Caching
    results.append(("Caching", await test_caching()))
    await wait_between_tests(1.0)

    # Test 6: Author Series Search
    results.append(("Author Series Search", await test_author_series_search()))
    await wait_between_tests(1.0)

    # Test 7: Limit Variations
    results.append(("Limit Variations", await test_limit_variations()))
    await wait_between_tests(1.0)

    # Test 8: Field Extraction
    results.append(("Field Extraction", await test_field_extraction()))
    await wait_between_tests(1.0)

    # Test 9: Books By Author
    results.append(("Books By Author", await test_books_by_author()))
    await wait_between_tests(1.0)

    # Test 10: Series Names Field
    results.append(("Series Names Field", await test_series_names_field()))
    await wait_between_tests(1.0)

    # Test 11: Framework - Basic
    results.append(("Framework: Basic", await test_framework_basic()))
    await wait_between_tests(1.0)

    # Test 12: Framework - Author Focused
    results.append(("Framework: Author Focused", await test_framework_author_focused()))
    await wait_between_tests(1.0)

    # Test 13: Framework - Field Validation
    results.append(("Framework: Field Validation", await test_framework_field_validation()))

    # Summary
    print_header("Test Summary")
    print()

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name:<25} {status}")

    print()
    print("="*70)
    print(f"  Results: {passed}/{total} tests passed")
    print("="*70)

    return passed == total


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test Hardcover API integration")
    parser.add_argument("--search", metavar="QUERY", help="Test series search with query")
    parser.add_argument("--author", metavar="AUTHOR", help="Test author search or filter")
    parser.add_argument("--series", metavar="ID", type=int, help="Test series books with ID")
    parser.add_argument("--limits", action="store_true", help="Test limit variations")
    parser.add_argument("--fields", action="store_true", help="Test field extraction")
    parser.add_argument("--framework", metavar="NAME", choices=["basic", "author", "fields", "all"],
                        help="Run specific framework: basic, author, fields, or all")
    parser.add_argument("--all", action="store_true", help="Run all tests (default)")

    args = parser.parse_args()

    # Determine which tests to run
    success = True

    if args.search:
        success = await test_configuration()
        if success:
            author_filter = args.author if args.author else ""
            success = await test_series_search(args.search, author_filter)

    elif args.author:
        success = await test_configuration()
        if success:
            success = await test_author_series_search(args.author)

    elif args.series:
        success = await test_configuration()
        if success:
            success = await test_series_books(args.series)

    elif args.limits:
        success = await test_configuration()
        if success:
            success = await test_limit_variations()

    elif args.fields:
        success = await test_configuration()
        if success:
            success = await test_field_extraction()

    elif args.framework:
        success = await test_configuration()
        if success:
            if args.framework == "basic":
                success = await test_framework_basic()
            elif args.framework == "author":
                success = await test_framework_author_focused()
            elif args.framework == "fields":
                success = await test_framework_field_validation()
            elif args.framework == "all":
                await test_framework_basic()
                await wait_between_tests(2.0)
                await test_framework_author_focused()
                await wait_between_tests(2.0)
                success = await test_framework_field_validation()

    else:
        # Run all tests by default
        success = await run_all_tests()

    return 0 if success else 1


if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
