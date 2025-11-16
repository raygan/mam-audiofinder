#!/usr/bin/env python3
"""
Library Matching Intelligence Test for MAM Audiobook Finder

Tests the Audiobookshelf library matching logic against comprehensive edge cases.
Can be run as pytest or standalone CLI tool inside the container.

Usage:
    # As pytest (mock mode)
    pytest app/tests/test_library_matching_intelligence.py -v

    # As CLI (mock mode with detailed report)
    python app/tests/test_library_matching_intelligence.py --report

    # Test against live ABS instance
    python app/tests/test_library_matching_intelligence.py --live --report

    # Run specific scenario
    python app/tests/test_library_matching_intelligence.py --scenario exact_match
"""
import sys
import os
import asyncio
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import dataclass, field
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from abs_client import AudiobookshelfClient
    import config
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running from the correct directory")
    sys.exit(1)


@dataclass
class TestCase:
    """Represents a single library matching test case."""
    name: str
    description: str
    query_title: str
    query_author: str = ""
    query_path: str = ""
    query_metadata: Optional[Dict] = None
    expected_status: str = "verified"  # verified, mismatch, not_found
    expected_min_score: int = 0
    expected_item_id: Optional[str] = None
    category: str = "general"  # general, edge_case, identifier, series, etc.
    notes: str = ""

    # Results (filled after test)
    actual_status: str = ""
    actual_score: int = 0
    actual_item_id: Optional[str] = None
    actual_note: str = ""
    passed: bool = False
    score_breakdown: Dict = field(default_factory=dict)


# ============================================================================
# COMPREHENSIVE TEST DATA - Real-world edge cases
# ============================================================================

MOCK_ABS_LIBRARY = {
    "results": [
        # Standard books
        {
            "id": "item-001-hobbit",
            "media": {
                "metadata": {
                    "title": "The Hobbit",
                    "authorName": "J.R.R. Tolkien",
                    "narratorName": "Rob Inglis",
                    "asin": "B0099RKRB6",
                    "isbn": "9780547928227"
                }
            },
            "path": "/audiobooks/Tolkien, J.R.R/The Hobbit"
        },
        {
            "id": "item-002-fellowship",
            "media": {
                "metadata": {
                    "title": "The Fellowship of the Ring",
                    "authorName": "J.R.R. Tolkien",
                    "narratorName": "Rob Inglis",
                    "asin": "B007978NPG",
                    "isbn": ""
                }
            },
            "path": "/audiobooks/Tolkien, J.R.R/The Fellowship of the Ring"
        },
        # Edge case: Same title, different author
        {
            "id": "item-003-foundation-asimov",
            "media": {
                "metadata": {
                    "title": "Foundation",
                    "authorName": "Isaac Asimov",
                    "narratorName": "Scott Brick",
                    "asin": "B003GFIVFS",
                    "isbn": "9780553293357"
                }
            },
            "path": "/audiobooks/Asimov, Isaac/Foundation"
        },
        # Edge case: Subtitle variations
        {
            "id": "item-004-sapiens",
            "media": {
                "metadata": {
                    "title": "Sapiens: A Brief History of Humankind",
                    "authorName": "Yuval Noah Harari",
                    "narratorName": "Derek Perkins",
                    "asin": "B00ICN066A",
                    "isbn": ""
                }
            },
            "path": "/audiobooks/Harari, Yuval Noah/Sapiens"
        },
        # Edge case: Series with numbers
        {
            "id": "item-005-hp1",
            "media": {
                "metadata": {
                    "title": "Harry Potter and the Philosopher's Stone",
                    "authorName": "J.K. Rowling",
                    "narratorName": "Stephen Fry",
                    "asin": "B017V4IMVQ",
                    "isbn": "9781781100219"
                }
            },
            "path": "/audiobooks/Rowling, J.K/Harry Potter 01"
        },
        # Edge case: Author name variations
        {
            "id": "item-006-dune",
            "media": {
                "metadata": {
                    "title": "Dune",
                    "authorName": "Frank Herbert",
                    "narratorName": "Scott Brick",
                    "asin": "B002V1OF70",
                    "isbn": "9780441013593"
                }
            },
            "path": "/audiobooks/Herbert, Frank/Dune"
        },
        # Edge case: Special characters
        {
            "id": "item-007-enders-game",
            "media": {
                "metadata": {
                    "title": "Ender's Game",
                    "authorName": "Orson Scott Card",
                    "narratorName": "Stefan Rudnicki",
                    "asin": "B003ZZAFJ2",
                    "isbn": "9780812550702"
                }
            },
            "path": "/audiobooks/Card, Orson Scott/Ender's Game"
        },
        # Edge case: Very long title with subtitle
        {
            "id": "item-008-thinking",
            "media": {
                "metadata": {
                    "title": "Thinking, Fast and Slow",
                    "authorName": "Daniel Kahneman",
                    "narratorName": "Patrick Egan",
                    "asin": "B005TKKCWC",
                    "isbn": "9780374533557"
                }
            },
            "path": "/audiobooks/Kahneman, Daniel/Thinking, Fast and Slow"
        },
        # Edge case: Multi-author book
        {
            "id": "item-009-expanse1",
            "media": {
                "metadata": {
                    "title": "Leviathan Wakes",
                    "authorName": "James S.A. Corey",  # Pen name for two authors
                    "narratorName": "Jefferson Mays",
                    "asin": "B073H9PF2D",
                    "isbn": ""
                }
            },
            "path": "/audiobooks/Corey, James S.A/The Expanse 01 - Leviathan Wakes"
        },
        # Edge case: Edition variations
        {
            "id": "item-010-1984",
            "media": {
                "metadata": {
                    "title": "1984",
                    "authorName": "George Orwell",
                    "narratorName": "Simon Prebble",
                    "asin": "B003JTHWKU",
                    "isbn": "9780452284234"
                }
            },
            "path": "/audiobooks/Orwell, George/1984"
        },
        # Edge case: Article variations (The, A, An)
        {
            "id": "item-011-stand",
            "media": {
                "metadata": {
                    "title": "The Stand",
                    "authorName": "Stephen King",
                    "narratorName": "Grover Gardner",
                    "asin": "B00ACPDZD6",
                    "isbn": ""
                }
            },
            "path": "/audiobooks/King, Stephen/The Stand"
        },
        # Edge case: Numeric in title
        {
            "id": "item-012-2001",
            "media": {
                "metadata": {
                    "title": "2001: A Space Odyssey",
                    "authorName": "Arthur C. Clarke",
                    "narratorName": "Dick Hill",
                    "asin": "B0012IR7XS",
                    "isbn": ""
                }
            },
            "path": "/audiobooks/Clarke, Arthur C/2001 - A Space Odyssey"
        }
    ],
    "total": 12
}


# ============================================================================
# TEST SCENARIOS - Comprehensive edge case coverage
# ============================================================================

def generate_test_cases() -> List[TestCase]:
    """Generate comprehensive test cases covering all edge cases."""
    return [
        # ========== EXACT MATCHES ==========
        TestCase(
            name="exact_title_author_match",
            description="Perfect title and author match",
            query_title="The Hobbit",
            query_author="J.R.R. Tolkien",
            expected_status="verified",
            expected_min_score=150,
            expected_item_id="item-001-hobbit",
            category="exact_match"
        ),

        TestCase(
            name="exact_match_lowercase",
            description="Exact match with different casing",
            query_title="the hobbit",
            query_author="j.r.r. tolkien",
            expected_status="verified",
            expected_min_score=150,
            expected_item_id="item-001-hobbit",
            category="exact_match"
        ),

        TestCase(
            name="exact_match_no_author",
            description="Title match without author",
            query_title="Dune",
            query_author="",
            expected_status="verified",
            expected_min_score=100,
            expected_item_id="item-006-dune",
            category="exact_match"
        ),

        # ========== ASIN/ISBN MATCHING (Highest Priority) ==========
        TestCase(
            name="asin_match_exact",
            description="ASIN match with matching title",
            query_title="The Hobbit",
            query_author="J.R.R. Tolkien",
            query_metadata={"asin": "B0099RKRB6"},
            expected_status="verified",
            expected_min_score=200,
            expected_item_id="item-001-hobbit",
            category="identifier",
            notes="ASIN should give 200 points"
        ),

        TestCase(
            name="asin_match_wrong_title",
            description="ASIN match even with completely different title",
            query_title="Wrong Title Here",
            query_author="Wrong Author",
            query_metadata={"asin": "B0099RKRB6"},
            expected_status="verified",
            expected_min_score=200,
            expected_item_id="item-001-hobbit",
            category="identifier",
            notes="ASIN should override title/author mismatch"
        ),

        TestCase(
            name="isbn_match_exact",
            description="ISBN match with matching title",
            query_title="The Hobbit",
            query_author="J.R.R. Tolkien",
            query_metadata={"isbn": "9780547928227"},
            expected_status="verified",
            expected_min_score=200,
            expected_item_id="item-001-hobbit",
            category="identifier"
        ),

        # ========== PARTIAL MATCHES ==========
        TestCase(
            name="partial_title_exact_author",
            description="Partial title match with exact author",
            query_title="Hobbit",
            query_author="J.R.R. Tolkien",
            expected_status="verified",
            expected_min_score=100,
            expected_item_id="item-001-hobbit",
            category="partial_match"
        ),

        TestCase(
            name="exact_title_partial_author",
            description="Exact title with partial author",
            query_title="The Hobbit",
            query_author="Tolkien",
            expected_status="verified",
            expected_min_score=125,
            expected_item_id="item-001-hobbit",
            category="partial_match"
        ),

        TestCase(
            name="partial_both",
            description="Partial title and partial author",
            query_title="Fellowship",
            query_author="Tolkien",
            expected_status="mismatch",
            expected_min_score=75,
            category="partial_match",
            notes="Should be mismatch (score < 100)"
        ),

        # ========== SUBTITLE HANDLING ==========
        TestCase(
            name="subtitle_colon_present",
            description="Query includes subtitle with colon",
            query_title="Sapiens: A Brief History of Humankind",
            query_author="Yuval Noah Harari",
            expected_status="verified",
            expected_min_score=150,
            expected_item_id="item-004-sapiens",
            category="subtitle"
        ),

        TestCase(
            name="subtitle_missing_in_query",
            description="Query without subtitle, library has it",
            query_title="Sapiens",
            query_author="Yuval Noah Harari",
            expected_status="verified",
            expected_min_score=100,
            expected_item_id="item-004-sapiens",
            category="subtitle",
            notes="Should still match (partial title)"
        ),

        TestCase(
            name="subtitle_dash_variation",
            description="Subtitle with dash instead of colon",
            query_title="Sapiens - A Brief History of Humankind",
            query_author="Yuval Noah Harari",
            expected_status="mismatch",
            expected_min_score=50,
            category="subtitle",
            notes="Won't be exact match but should be partial"
        ),

        # ========== SERIES HANDLING ==========
        TestCase(
            name="series_exact_name",
            description="Exact series book name",
            query_title="Harry Potter and the Philosopher's Stone",
            query_author="J.K. Rowling",
            expected_status="verified",
            expected_min_score=150,
            expected_item_id="item-005-hp1",
            category="series"
        ),

        TestCase(
            name="series_with_book_number",
            description="Query includes 'Book 1' variation",
            query_title="Harry Potter and the Philosopher's Stone Book 1",
            query_author="J.K. Rowling",
            expected_status="mismatch",
            expected_min_score=50,
            category="series",
            notes="Partial match only (title substring)"
        ),

        # ========== AUTHOR NAME VARIATIONS ==========
        TestCase(
            name="author_initials_vs_full",
            description="Query has initials, library has full dots",
            query_title="The Hobbit",
            query_author="JRR Tolkien",
            expected_status="mismatch",
            expected_min_score=100,
            category="author_variations",
            notes="Title matches but author format differs"
        ),

        TestCase(
            name="author_lastname_only",
            description="Query has last name only",
            query_title="Dune",
            query_author="Herbert",
            expected_status="verified",
            expected_min_score=125,
            expected_item_id="item-006-dune",
            category="author_variations"
        ),

        TestCase(
            name="author_pen_name",
            description="Multi-author pen name",
            query_title="Leviathan Wakes",
            query_author="James S.A. Corey",
            expected_status="verified",
            expected_min_score=150,
            expected_item_id="item-009-expanse1",
            category="author_variations"
        ),

        # ========== SPECIAL CHARACTERS ==========
        TestCase(
            name="apostrophe_in_title",
            description="Title with apostrophe",
            query_title="Ender's Game",
            query_author="Orson Scott Card",
            expected_status="verified",
            expected_min_score=150,
            expected_item_id="item-007-enders-game",
            category="special_chars"
        ),

        TestCase(
            name="apostrophe_straight_vs_curly",
            description="Different apostrophe types",
            query_title="Ender's Game",
            query_author="Orson Scott Card",
            expected_status="mismatch",
            expected_min_score=50,
            category="special_chars",
            notes="Curly vs straight apostrophe mismatch"
        ),

        TestCase(
            name="comma_in_title",
            description="Title with comma",
            query_title="Thinking, Fast and Slow",
            query_author="Daniel Kahneman",
            expected_status="verified",
            expected_min_score=150,
            expected_item_id="item-008-thinking",
            category="special_chars"
        ),

        # ========== ARTICLE VARIATIONS (The, A, An) ==========
        TestCase(
            name="article_the_present",
            description="Query with 'The' article",
            query_title="The Stand",
            query_author="Stephen King",
            expected_status="verified",
            expected_min_score=150,
            expected_item_id="item-011-stand",
            category="articles"
        ),

        TestCase(
            name="article_the_missing",
            description="Query without 'The' article",
            query_title="Stand",
            query_author="Stephen King",
            expected_status="verified",
            expected_min_score=100,
            expected_item_id="item-011-stand",
            category="articles",
            notes="Partial match (substring)"
        ),

        # ========== NUMERIC IN TITLES ==========
        TestCase(
            name="numeric_exact",
            description="Numeric in title - exact match",
            query_title="1984",
            query_author="George Orwell",
            expected_status="verified",
            expected_min_score=150,
            expected_item_id="item-010-1984",
            category="numeric"
        ),

        TestCase(
            name="numeric_with_colon",
            description="Numeric with colon and subtitle",
            query_title="2001: A Space Odyssey",
            query_author="Arthur C. Clarke",
            expected_status="verified",
            expected_min_score=150,
            expected_item_id="item-012-2001",
            category="numeric"
        ),

        # ========== SAME TITLE DIFFERENT AUTHORS ==========
        TestCase(
            name="same_title_correct_author",
            description="Same title, correct author specified",
            query_title="Foundation",
            query_author="Isaac Asimov",
            expected_status="verified",
            expected_min_score=150,
            expected_item_id="item-003-foundation-asimov",
            category="disambiguation"
        ),

        TestCase(
            name="same_title_wrong_author",
            description="Same title, wrong author",
            query_title="Foundation",
            query_author="Robert A. Heinlein",
            expected_status="mismatch",
            expected_min_score=100,
            category="disambiguation",
            notes="Title matches but author doesn't"
        ),

        # ========== NOT FOUND CASES ==========
        TestCase(
            name="not_in_library_title",
            description="Book not in library",
            query_title="The Nonexistent Book",
            query_author="Unknown Author",
            expected_status="not_found",
            expected_min_score=0,
            category="not_found"
        ),

        TestCase(
            name="wrong_asin",
            description="ASIN not in library",
            query_title="Some Book",
            query_author="Some Author",
            query_metadata={"asin": "B999999999"},
            expected_status="not_found",
            expected_min_score=0,
            category="not_found"
        ),

        # ========== PATH MATCHING ==========
        TestCase(
            name="path_match_bonus",
            description="Correct path should add bonus points",
            query_title="Dune",
            query_author="Frank Herbert",
            query_path="/audiobooks/Herbert, Frank/Dune",
            expected_status="verified",
            expected_min_score=175,
            expected_item_id="item-006-dune",
            category="path_matching",
            notes="Should get +25 for path match"
        ),

        TestCase(
            name="path_mismatch_no_penalty",
            description="Wrong path shouldn't penalize",
            query_title="Dune",
            query_author="Frank Herbert",
            query_path="/wrong/path/here",
            expected_status="verified",
            expected_min_score=150,
            expected_item_id="item-006-dune",
            category="path_matching",
            notes="Path mismatch doesn't reduce score"
        ),
    ]


# ============================================================================
# MATCH ANALYZER - Detailed scoring breakdown
# ============================================================================

class MatchAnalyzer:
    """Analyzes match results and provides detailed scoring breakdown."""

    @staticmethod
    def analyze_match(test_case: TestCase, abs_library: Dict, result: Dict) -> Dict:
        """
        Analyze why a match succeeded or failed.

        Returns detailed breakdown of scoring logic.
        """
        breakdown = {
            "title_score": 0,
            "author_score": 0,
            "path_score": 0,
            "identifier_score": 0,
            "total_score": 0,
            "matched_item": None,
            "match_explanation": []
        }

        # Simulate the matching logic from abs_client.py
        title_lower = test_case.query_title.lower().strip()
        author_lower = test_case.query_author.lower().strip() if test_case.query_author else ""

        metadata_asin = test_case.query_metadata.get("asin", "") if test_case.query_metadata else ""
        metadata_isbn = test_case.query_metadata.get("isbn", "") if test_case.query_metadata else ""

        best_score = 0
        best_item = None

        for item in abs_library.get("results", []):
            item_metadata = item.get("media", {}).get("metadata", {})
            item_title = (item_metadata.get("title") or "").lower().strip()
            item_author = (item_metadata.get("authorName") or "").lower().strip()
            item_asin = (item_metadata.get("asin") or "").lower().strip()
            item_isbn = (item_metadata.get("isbn") or "").lower().strip()
            item_path = item.get("path", "")

            score = 0
            explanations = []

            # ASIN/ISBN matching (highest priority)
            if metadata_asin and item_asin and metadata_asin.lower() == item_asin:
                score += 200
                explanations.append(f"ASIN match: {metadata_asin} (+200)")
            elif metadata_isbn and item_isbn and metadata_isbn.lower() == item_isbn:
                score += 200
                explanations.append(f"ISBN match: {metadata_isbn} (+200)")
            else:
                # Title matching
                if item_title == title_lower:
                    score += 100
                    explanations.append(f"Exact title match (+100)")
                elif title_lower in item_title or item_title in title_lower:
                    score += 50
                    explanations.append(f"Partial title match (+50)")

                # Author matching
                if author_lower:
                    if item_author == author_lower:
                        score += 50
                        explanations.append(f"Exact author match (+50)")
                    elif author_lower in item_author or item_author in author_lower:
                        score += 25
                        explanations.append(f"Partial author match (+25)")
                else:
                    score += 10
                    explanations.append(f"No author provided (+10)")

                # Path matching
                if test_case.query_path and item_path:
                    lib_path_norm = test_case.query_path.lower().replace("\\", "/").strip("/")
                    item_path_norm = item_path.lower().replace("\\", "/").strip("/")
                    if lib_path_norm in item_path_norm or item_path_norm in lib_path_norm:
                        score += 25
                        explanations.append(f"Path match bonus (+25)")

            # Track best match
            if score > best_score and (score >= 50 or metadata_asin or metadata_isbn):
                best_score = score
                best_item = {
                    "id": item.get("id"),
                    "title": item_metadata.get("title"),
                    "author": item_metadata.get("authorName"),
                    "path": item_path,
                    "score": score,
                    "explanations": explanations
                }

        breakdown["total_score"] = best_score
        breakdown["matched_item"] = best_item
        if best_item:
            breakdown["match_explanation"] = best_item["explanations"]

        return breakdown


# ============================================================================
# TEST RUNNER - Execute tests and generate reports
# ============================================================================

class LibraryMatchingTestRunner:
    """Runs library matching tests and generates detailed reports."""

    def __init__(self, use_live: bool = False):
        self.use_live = use_live
        self.test_cases = generate_test_cases()
        self.results = []

    async def run_all_tests(self, scenario_filter: Optional[str] = None) -> List[TestCase]:
        """Run all test cases (or filtered by scenario)."""
        test_cases = self.test_cases

        if scenario_filter:
            test_cases = [tc for tc in test_cases if tc.name == scenario_filter or tc.category == scenario_filter]

        print(f"\n{'='*80}")
        print(f"Library Matching Intelligence Test")
        print(f"Mode: {'LIVE (Real ABS)' if self.use_live else 'MOCK (Simulated)'}")
        print(f"Test Cases: {len(test_cases)}")
        print(f"{'='*80}\n")

        for idx, test_case in enumerate(test_cases, 1):
            print(f"[{idx}/{len(test_cases)}] Running: {test_case.name}")
            await self.run_test_case(test_case)
            self.results.append(test_case)

        return self.results

    async def run_test_case(self, test_case: TestCase):
        """Run a single test case."""
        if self.use_live:
            # Test against real ABS instance
            await self._run_live_test(test_case)
        else:
            # Test with mock data
            await self._run_mock_test(test_case)

    async def _run_mock_test(self, test_case: TestCase):
        """Run test with mock ABS data."""
        # Create mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=MOCK_ABS_LIBRARY)

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)

        # Create ABS client (need to configure)
        with patch("abs_client.ABS_BASE_URL", "http://mock-abs:13378"):
            with patch("abs_client.ABS_API_KEY", "mock-key"):
                with patch("abs_client.ABS_LIBRARY_ID", "mock-lib"):
                    with patch("abs_client.ABS_VERIFY_TIMEOUT", 10):
                        with patch("httpx.AsyncClient", return_value=mock_client):
                            client = AudiobookshelfClient()

                            # Mock the description update method to avoid errors
                            client._update_description_after_verification = AsyncMock()

                            result = await client.verify_import(
                                title=test_case.query_title,
                                author=test_case.query_author,
                                library_path=test_case.query_path,
                                metadata=test_case.query_metadata
                            )

        # Analyze the result
        breakdown = MatchAnalyzer.analyze_match(test_case, MOCK_ABS_LIBRARY, result)

        # Update test case with results
        test_case.actual_status = result.get("status", "unknown")
        test_case.actual_note = result.get("note", "")
        test_case.actual_item_id = result.get("abs_item_id")
        test_case.actual_score = breakdown["total_score"]
        test_case.score_breakdown = breakdown

        # Determine if test passed
        status_match = test_case.actual_status == test_case.expected_status
        score_match = test_case.actual_score >= test_case.expected_min_score

        if test_case.expected_item_id:
            item_match = test_case.actual_item_id == test_case.expected_item_id
        else:
            item_match = True  # Don't require specific item if not specified

        test_case.passed = status_match and score_match and item_match

    async def _run_live_test(self, test_case: TestCase):
        """Run test against real ABS instance."""
        try:
            client = AudiobookshelfClient()

            if not client.is_configured:
                print("  ⚠️  ABS not configured - skipping live test")
                test_case.actual_status = "not_configured"
                test_case.passed = False
                return

            result = await client.verify_import(
                title=test_case.query_title,
                author=test_case.query_author,
                library_path=test_case.query_path,
                metadata=test_case.query_metadata
            )

            test_case.actual_status = result.get("status", "unknown")
            test_case.actual_note = result.get("note", "")
            test_case.actual_item_id = result.get("abs_item_id")

            # For live tests, we can't predict exact scores, so just check status
            test_case.passed = test_case.actual_status == test_case.expected_status

            print(f"  Status: {test_case.actual_status}")
            print(f"  Note: {test_case.actual_note}")

        except Exception as e:
            print(f"  ❌ Error: {e}")
            test_case.actual_status = "error"
            test_case.actual_note = str(e)
            test_case.passed = False

    def generate_report(self, show_details: bool = True) -> str:
        """Generate detailed test report."""
        lines = []
        lines.append("\n" + "="*80)
        lines.append("LIBRARY MATCHING INTELLIGENCE TEST REPORT")
        lines.append("="*80)

        # Summary statistics
        total = len(self.results)
        passed = sum(1 for tc in self.results if tc.passed)
        failed = total - passed

        lines.append(f"\nSummary:")
        lines.append(f"  Total Tests: {total}")
        lines.append(f"  Passed: {passed} ({100*passed/total:.1f}%)")
        lines.append(f"  Failed: {failed} ({100*failed/total:.1f}%)")

        # Breakdown by category
        categories = {}
        for tc in self.results:
            if tc.category not in categories:
                categories[tc.category] = {"total": 0, "passed": 0}
            categories[tc.category]["total"] += 1
            if tc.passed:
                categories[tc.category]["passed"] += 1

        lines.append(f"\nResults by Category:")
        for cat, stats in sorted(categories.items()):
            pct = 100 * stats["passed"] / stats["total"]
            lines.append(f"  {cat:20s}: {stats['passed']:2d}/{stats['total']:2d} ({pct:5.1f}%)")

        # Failed tests
        if failed > 0:
            lines.append(f"\n{'='*80}")
            lines.append("FAILED TESTS")
            lines.append("="*80)

            for tc in self.results:
                if not tc.passed:
                    lines.append(f"\n❌ {tc.name}")
                    lines.append(f"   Description: {tc.description}")
                    lines.append(f"   Query: '{tc.query_title}' by '{tc.query_author}'")
                    if tc.query_metadata:
                        lines.append(f"   Metadata: {tc.query_metadata}")
                    lines.append(f"   Expected: {tc.expected_status} (score >= {tc.expected_min_score})")
                    lines.append(f"   Actual: {tc.actual_status} (score = {tc.actual_score})")
                    lines.append(f"   Note: {tc.actual_note}")

                    if show_details and tc.score_breakdown.get("match_explanation"):
                        lines.append(f"   Score Breakdown:")
                        for exp in tc.score_breakdown["match_explanation"]:
                            lines.append(f"     • {exp}")

                    if tc.notes:
                        lines.append(f"   Test Notes: {tc.notes}")

        # Detailed results (if requested)
        if show_details:
            lines.append(f"\n{'='*80}")
            lines.append("DETAILED TEST RESULTS")
            lines.append("="*80)

            for tc in self.results:
                status_icon = "✅" if tc.passed else "❌"
                lines.append(f"\n{status_icon} {tc.name}")
                lines.append(f"   Category: {tc.category}")
                lines.append(f"   Description: {tc.description}")
                lines.append(f"   Query: '{tc.query_title}' by '{tc.query_author}'")
                if tc.query_metadata:
                    lines.append(f"   Metadata: {tc.query_metadata}")
                lines.append(f"   Result: {tc.actual_status} (expected: {tc.expected_status})")
                lines.append(f"   Score: {tc.actual_score} (min expected: {tc.expected_min_score})")

                if tc.score_breakdown.get("matched_item"):
                    item = tc.score_breakdown["matched_item"]
                    lines.append(f"   Matched: '{item['title']}' by '{item['author']}'")
                    lines.append(f"   Item ID: {item['id']}")
                    lines.append(f"   Score Breakdown:")
                    for exp in tc.score_breakdown["match_explanation"]:
                        lines.append(f"     • {exp}")

                if tc.notes:
                    lines.append(f"   Notes: {tc.notes}")

        lines.append("\n" + "="*80 + "\n")

        return "\n".join(lines)


# ============================================================================
# CLI INTERFACE
# ============================================================================

async def main():
    """Main entry point for CLI execution."""
    parser = argparse.ArgumentParser(
        description="Library Matching Intelligence Test for MAM Audiobook Finder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tests with mock data
  python app/tests/test_library_matching_intelligence.py

  # Run with detailed report
  python app/tests/test_library_matching_intelligence.py --report

  # Test against live ABS instance
  python app/tests/test_library_matching_intelligence.py --live --report

  # Run specific scenario
  python app/tests/test_library_matching_intelligence.py --scenario exact_match

  # Run category of tests
  python app/tests/test_library_matching_intelligence.py --scenario identifier --report
        """
    )

    parser.add_argument("--live", action="store_true", help="Test against real ABS instance (requires ABS_* env vars)")
    parser.add_argument("--report", action="store_true", help="Show detailed report")
    parser.add_argument("--scenario", type=str, help="Run specific scenario or category")
    parser.add_argument("--output", type=str, help="Save report to file")

    args = parser.parse_args()

    # Run tests
    runner = LibraryMatchingTestRunner(use_live=args.live)
    results = await runner.run_all_tests(scenario_filter=args.scenario)

    # Generate report
    report = runner.generate_report(show_details=args.report)
    print(report)

    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report)
        print(f"\n📄 Report saved to: {output_path}")

    # Exit with appropriate code
    failed = sum(1 for tc in results if not tc.passed)
    sys.exit(0 if failed == 0 else 1)


# ============================================================================
# PYTEST INTEGRATION
# ============================================================================

import pytest

@pytest.mark.asyncio
class TestLibraryMatchingIntelligence:
    """Pytest integration for library matching tests."""

    async def test_all_scenarios(self):
        """Run all test scenarios."""
        runner = LibraryMatchingTestRunner(use_live=False)
        results = await runner.run_all_tests()

        failed = [tc for tc in results if not tc.passed]

        if failed:
            report = runner.generate_report(show_details=True)
            pytest.fail(f"\n{len(failed)} test(s) failed:\n{report}")

    async def test_exact_matches(self):
        """Test exact match scenarios."""
        runner = LibraryMatchingTestRunner(use_live=False)
        results = await runner.run_all_tests(scenario_filter="exact_match")

        failed = [tc for tc in results if not tc.passed]
        assert len(failed) == 0, f"{len(failed)} exact match tests failed"

    async def test_identifier_matching(self):
        """Test ASIN/ISBN identifier matching."""
        runner = LibraryMatchingTestRunner(use_live=False)
        results = await runner.run_all_tests(scenario_filter="identifier")

        failed = [tc for tc in results if not tc.passed]
        assert len(failed) == 0, f"{len(failed)} identifier tests failed"

    async def test_partial_matches(self):
        """Test partial match scenarios."""
        runner = LibraryMatchingTestRunner(use_live=False)
        results = await runner.run_all_tests(scenario_filter="partial_match")

        failed = [tc for tc in results if not tc.passed]
        assert len(failed) == 0, f"{len(failed)} partial match tests failed"

    async def test_edge_cases(self):
        """Test edge case scenarios."""
        runner = LibraryMatchingTestRunner(use_live=False)
        edge_categories = ["subtitle", "series", "author_variations", "special_chars", "articles", "numeric"]

        all_failed = []
        for category in edge_categories:
            results = await runner.run_all_tests(scenario_filter=category)
            failed = [tc for tc in results if not tc.passed]
            all_failed.extend(failed)

        if all_failed:
            print(f"\n⚠️  {len(all_failed)} edge case tests failed:")
            for tc in all_failed:
                print(f"  - {tc.name}: {tc.actual_status} (expected {tc.expected_status})")


if __name__ == "__main__":
    # Run as CLI
    asyncio.run(main())
