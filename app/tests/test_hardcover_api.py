#!/usr/bin/env python3
"""
Test Hardcover API integration.
Run this inside the container to verify Hardcover API configuration and connectivity.

Usage:
    python test_hardcover_api.py                    # Run all tests
    python test_hardcover_api.py --search "Mistborn" # Test series search only
    python test_hardcover_api.py --series 12345     # Test series books only
"""
import sys
import asyncio
import argparse
from pathlib import Path

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


async def run_all_tests():
    """Run all tests."""
    print("\n" + "🧪 "*25)
    print("  HARDCOVER API INTEGRATION TEST SUITE")
    print("🧪 "*25)

    results = []

    # Test 1: Configuration
    results.append(("Configuration", await test_configuration()))

    # Test 2: Series Search
    results.append(("Series Search", await test_series_search("Mistborn")))

    # Test 3: Series Books
    results.append(("Series Books", await test_series_books()))

    # Test 4: Rate Limiting
    results.append(("Rate Limiting", await test_rate_limiting()))

    # Test 5: Caching
    results.append(("Caching", await test_caching()))

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
    parser.add_argument("--author", metavar="AUTHOR", default="", help="Author filter for search")
    parser.add_argument("--series", metavar="ID", type=int, help="Test series books with ID")
    parser.add_argument("--all", action="store_true", help="Run all tests (default)")

    args = parser.parse_args()

    # Determine which tests to run
    if args.search:
        success = await test_configuration()
        if success:
            success = await test_series_search(args.search, args.author)
    elif args.series:
        success = await test_configuration()
        if success:
            success = await test_series_books(args.series)
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
