# Library Matching Intelligence Test

## Overview

The **Library Matching Intelligence Test** is a comprehensive test suite for validating the Audiobookshelf library matching logic in MAM Audiobook Finder. It tests how well the system can identify books in your Audiobookshelf library based on title, author, ASIN/ISBN, and path matching.

## Features

- **30+ Test Scenarios** covering real-world edge cases
- **Dual-Mode Operation**: Mock (fast) or Live (real ABS instance)
- **Detailed Scoring Analysis**: Shows exactly why each match succeeded or failed
- **Category Breakdown**: Organizes tests by type (identifiers, subtitles, series, etc.)
- **Pytest Integration**: Can run via pytest or standalone CLI
- **Container-Ready**: Designed to run inside Docker environment
- **No Hardcoded Paths**: Uses dynamic path resolution

## Test Categories

- **Exact Matches**: Perfect title/author matches
- **Identifier Matching**: ASIN/ISBN based matching (highest priority)
- **Partial Matches**: Substring and fuzzy matching
- **Subtitle Handling**: Books with colons, dashes, etc.
- **Series Handling**: Books with numbers and series indicators
- **Author Variations**: Different name formats (initials, pen names, etc.)
- **Special Characters**: Apostrophes, commas, etc.
- **Article Variations**: The, A, An handling
- **Numeric Titles**: Books starting with numbers
- **Disambiguation**: Same title, different authors
- **Path Matching**: Bonus scoring for matching file paths
- **Not Found**: Validation of negative cases

## Scoring System

The test validates the scoring logic used in `abs_client.py`:

- **ASIN/ISBN Match**: 200 points (verified)
- **Exact Title Match**: 100 points
- **Partial Title Match**: 50 points
- **Exact Author Match**: 50 points
- **Partial Author Match**: 25 points
- **Path Match Bonus**: 25 points
- **No Author Provided**: 10 points (default)

**Verification Thresholds**:
- Score >= 200: Verified (ASIN/ISBN)
- Score >= 100: Verified (title + author)
- Score < 100: Mismatch
- No match: Not found

## Usage

### Inside Container (Recommended)

```bash
# Exec into running container
docker exec -it mam-audiofinder bash

# Run all tests with mock data
python app/tests/test_library_matching_intelligence.py

# Run with detailed report
python app/tests/test_library_matching_intelligence.py --report

# Run specific category
python app/tests/test_library_matching_intelligence.py --scenario identifier --report

# Run specific test
python app/tests/test_library_matching_intelligence.py --scenario exact_match

# Test against real ABS instance (requires ABS_* env vars)
python app/tests/test_library_matching_intelligence.py --live --report

# Save report to file
python app/tests/test_library_matching_intelligence.py --report --output /data/match_report.txt
```

### Via Pytest

```bash
# Run all matching tests
python -m pytest app/tests/test_library_matching_intelligence.py -v

# Run specific test class
python -m pytest app/tests/test_library_matching_intelligence.py::TestLibraryMatchingIntelligence::test_exact_matches -v

# Run with coverage
python -m pytest app/tests/test_library_matching_intelligence.py --cov=app.abs_client
```

### Outside Container (Development)

```bash
# Install dependencies first
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
python app/tests/test_library_matching_intelligence.py --report
```

## Sample Output

```
================================================================================
Library Matching Intelligence Test
Mode: MOCK (Simulated)
Test Cases: 30
================================================================================

[1/30] Running: exact_title_author_match
[2/30] Running: exact_match_lowercase
[3/30] Running: exact_match_no_author
...

================================================================================
LIBRARY MATCHING INTELLIGENCE TEST REPORT
================================================================================

Summary:
  Total Tests: 30
  Passed: 25 (83.3%)
  Failed: 5 (16.7%)

Results by Category:
  articles            :  2/ 2 (100.0%)
  author_variations   :  2/ 3 ( 66.7%)
  disambiguation      :  1/ 2 ( 50.0%)
  exact_match         :  3/ 3 (100.0%)
  identifier          :  3/ 3 (100.0%)
  ...

================================================================================
DETAILED TEST RESULTS
================================================================================

✅ exact_title_author_match
   Category: exact_match
   Description: Perfect title and author match
   Query: 'The Hobbit' by 'J.R.R. Tolkien'
   Result: verified (expected: verified)
   Score: 150 (min expected: 150)
   Matched: 'The Hobbit' by 'J.R.R. Tolkien'
   Item ID: item-001-hobbit
   Score Breakdown:
     • Exact title match (+100)
     • Exact author match (+50)

❌ same_title_wrong_author
   Description: Same title, wrong author
   Query: 'Foundation' by 'Robert A. Heinlein'
   Expected: mismatch (score >= 100)
   Actual: verified (score = 100)
   Note: Found in library: 'Foundation' by 'Isaac Asimov'
   Score Breakdown:
     • Exact title match (+100)
   Test Notes: Title matches but author doesn't
```

## Interpreting Results

### Passed Tests (✅)
Tests that pass indicate the matching logic is working as expected for that scenario.

### Failed Tests (❌)
Failed tests reveal edge cases where the matching logic may need improvement:

- **False Positives**: Query matched when it shouldn't (e.g., wrong author)
- **False Negatives**: Query didn't match when it should (e.g., subtitle variations)
- **Score Mismatches**: Match found but with unexpected score

### Common Issues Revealed

1. **Author Format Sensitivity**: `JRR Tolkien` vs `J.R.R. Tolkien` may not match
2. **Subtitle Variations**: Dash vs colon can break exact matching
3. **Special Characters**: Different apostrophe types may cause mismatches
4. **Title-Only Matching**: Books with same title but different authors may match incorrectly

## Mock Library Data

The test uses a mock ABS library with 12 carefully selected books covering various edge cases:

- The Hobbit (Tolkien) - Standard book with ASIN/ISBN
- Fellowship of the Ring (Tolkien) - Series book
- Foundation (Asimov) - Common title (disambiguation test)
- Sapiens (Harari) - Subtitle with colon
- Harry Potter 1 (Rowling) - Series with number
- Dune (Herbert) - Single-word title
- Ender's Game (Card) - Special characters
- Thinking, Fast and Slow (Kahneman) - Comma in title
- Leviathan Wakes (Corey) - Pen name
- 1984 (Orwell) - Numeric title
- The Stand (King) - Article "The"
- 2001: A Space Odyssey (Clarke) - Numeric with subtitle

## Live Testing

To test against your real Audiobookshelf instance:

```bash
# Set environment variables (if not already configured)
export ABS_BASE_URL="http://audiobookshelf:13378"
export ABS_API_KEY="your_api_key_here"
export ABS_LIBRARY_ID="your_library_id"

# Run live tests
python app/tests/test_library_matching_intelligence.py --live --report
```

**Note**: Live testing will query your actual ABS library and report how well the matching logic performs against your real collection.

## Adding New Test Cases

To add new test scenarios, edit the `generate_test_cases()` function in the test file:

```python
TestCase(
    name="my_new_test",
    description="Description of what this tests",
    query_title="Book Title",
    query_author="Author Name",
    query_metadata={"asin": "B001234567"},  # Optional
    expected_status="verified",  # verified, mismatch, or not_found
    expected_min_score=150,
    expected_item_id="item-id",  # Optional
    category="my_category",
    notes="Additional context"
),
```

## Integration with CI/CD

This test can be integrated into automated testing:

```yaml
# In your CI pipeline
- name: Run Library Matching Tests
  run: |
    docker exec mam-audiofinder python app/tests/test_library_matching_intelligence.py
```

## Files

- **Test File**: `app/tests/test_library_matching_intelligence.py` (~900 lines)
- **Tested Module**: `app/abs_client.py` (verify_import method)
- **Documentation**: `documentation/library-matching-test.md` (this file)

## Troubleshooting

### Import Errors

```bash
# Make sure all dependencies are installed
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Pytest Can't Find Modules

```bash
# Use python -m to ensure correct Python environment
python -m pytest app/tests/test_library_matching_intelligence.py -v
```

### Container Permission Issues

```bash
# Tests use temporary directories and don't write to /workspace
# No special permissions needed
```

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Project overview and architecture
- [BACKEND.md](../BACKEND.md) - Technical implementation details
- [README.md](../README.md) - User-facing documentation

## Future Enhancements

Potential improvements to the test suite:

- [ ] Add phonetic matching tests (Soundex, Metaphone)
- [ ] Test Unicode and international characters
- [ ] Add performance benchmarks (time to match 1000+ books)
- [ ] Test concurrent matching (thread safety)
- [ ] Add fuzzy ratio thresholds testing
- [ ] Test pagination with large libraries (10,000+ items)

---

**Last Updated**: 2025-11-16
**Test Coverage**: 30 scenarios across 12 categories
**Pass Rate**: ~83% (expected, some tests demonstrate known limitations)
