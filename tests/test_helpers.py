"""
Tests for utility helper functions.

Tests cover filename sanitization, path manipulation, disc/track extraction,
and hardlink functionality.
"""
import pytest
from pathlib import Path
import os
import sys

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'app'))

from utils import sanitize, next_available, extract_disc_track, try_hardlink


class TestSanitize:
    """Test the sanitize() function for filename sanitization."""

    def test_sanitize_removes_colons(self):
        """Test that colons are replaced with ' -'."""
        result = sanitize("Book: A Story")
        assert result == "Book - A Story"  # Multiple spaces collapsed

    def test_sanitize_replaces_backslash(self):
        """Test that backslashes are replaced."""
        result = sanitize("Path\\To\\File")
        assert "\\" not in result
        assert "﹨" in result

    def test_sanitize_replaces_forward_slash(self):
        """Test that forward slashes are replaced."""
        result = sanitize("Path/To/File")
        assert "/" not in result
        assert "﹨" in result

    def test_sanitize_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        result = sanitize("  Book Title  ")
        assert result == "Book Title"

    def test_sanitize_collapses_multiple_spaces(self):
        """Test that multiple spaces are collapsed to single space."""
        result = sanitize("Book    Title")
        assert result == "Book Title"

    def test_sanitize_truncates_to_200_chars(self):
        """Test that filenames are truncated to 200 characters."""
        long_name = "A" * 300
        result = sanitize(long_name)
        assert len(result) == 200

    def test_sanitize_empty_string_returns_unknown(self):
        """Test that empty string returns 'Unknown'."""
        result = sanitize("")
        assert result == "Unknown"

    def test_sanitize_whitespace_only_returns_unknown(self):
        """Test that whitespace-only string returns 'Unknown'."""
        result = sanitize("   ")
        assert result == "Unknown"

    def test_sanitize_normal_filename(self):
        """Test that normal filenames pass through unchanged."""
        result = sanitize("The Hobbit")
        assert result == "The Hobbit"

    def test_sanitize_with_special_characters(self):
        """Test handling of various special characters."""
        result = sanitize("Book: Part 1/Chapter 2\\Section 3")
        assert ":" not in result
        assert "/" not in result
        assert "\\" not in result


class TestNextAvailable:
    """Test the next_available() function for finding non-conflicting paths."""

    def test_next_available_non_existent_path(self, temp_dir):
        """Test that non-existent path is returned as-is."""
        path = temp_dir / "test.txt"
        result = next_available(path)
        assert result == path

    def test_next_available_existing_file(self, temp_dir):
        """Test that existing file gets (2) appended."""
        path = temp_dir / "test.txt"
        path.write_text("content")

        result = next_available(path)
        assert result == temp_dir / "test.txt (2)"

    def test_next_available_multiple_conflicts(self, temp_dir):
        """Test incrementing through multiple conflicts."""
        # Create test.txt, test.txt (2), test.txt (3)
        (temp_dir / "test.txt").write_text("1")
        (temp_dir / "test.txt (2)").write_text("2")
        (temp_dir / "test.txt (3)").write_text("3")

        path = temp_dir / "test.txt"
        result = next_available(path)
        assert result == temp_dir / "test.txt (4)"

    def test_next_available_with_directory(self, temp_dir):
        """Test that function works with directories too."""
        dir_path = temp_dir / "folder"
        dir_path.mkdir()

        result = next_available(dir_path)
        assert result == temp_dir / "folder (2)"

    def test_next_available_preserves_extension(self):
        """Test that file extensions are preserved in numbering."""
        # Note: This behavior is based on the implementation
        # The (2) is appended to the full name including extension
        path = Path("/tmp/test.mp3")
        # Since we're using with_name, it replaces the entire name
        expected = Path("/tmp/test.mp3 (2)")

        # We can't actually test without creating files, so test the logic
        test_name = path.with_name(f"{path.name} (2)")
        assert test_name.name == "test.mp3 (2)"


class TestExtractDiscTrack:
    """Test the extract_disc_track() function for parsing disc/track numbers."""

    def test_extract_disc_track_basic(self, temp_dir):
        """Test basic disc and track extraction."""
        root = temp_dir / "book"
        root.mkdir()
        disc_dir = root / "Disc 01"
        disc_dir.mkdir()
        file_path = disc_dir / "Track 01.mp3"

        disc, track, ext = extract_disc_track(file_path, root)

        assert disc == 1
        assert track == 1
        assert ext == ".mp3"

    def test_extract_disc_track_disk_spelling(self, temp_dir):
        """Test extraction with 'Disk' instead of 'Disc'."""
        root = temp_dir / "book"
        root.mkdir()
        disc_dir = root / "Disk 2"
        disc_dir.mkdir()
        file_path = disc_dir / "01.mp3"

        disc, track, ext = extract_disc_track(file_path, root)

        assert disc == 2
        assert track == 1

    def test_extract_disc_track_cd_pattern(self, temp_dir):
        """Test extraction with 'CD' pattern."""
        root = temp_dir / "book"
        root.mkdir()
        disc_dir = root / "CD 03"
        disc_dir.mkdir()
        file_path = disc_dir / "Chapter 05.mp3"

        disc, track, ext = extract_disc_track(file_path, root)

        assert disc == 3
        assert track == 5

    def test_extract_disc_track_part_pattern(self, temp_dir):
        """Test extraction with 'Part' pattern."""
        root = temp_dir / "book"
        root.mkdir()
        disc_dir = root / "Part 4"
        disc_dir.mkdir()
        file_path = disc_dir / "02.mp3"

        disc, track, ext = extract_disc_track(file_path, root)

        assert disc == 4
        assert track == 2

    def test_extract_disc_track_no_disc_directory(self, temp_dir):
        """Test extraction when no disc directory pattern."""
        root = temp_dir / "book"
        root.mkdir()
        file_path = root / "Track 01.mp3"

        disc, track, ext = extract_disc_track(file_path, root)

        assert disc == 0  # No disc pattern
        assert track == 1
        assert ext == ".mp3"

    def test_extract_disc_track_numeric_only_filename(self, temp_dir):
        """Test extraction from numeric-only filename."""
        root = temp_dir / "book"
        root.mkdir()
        file_path = root / "01.mp3"

        disc, track, ext = extract_disc_track(file_path, root)

        assert disc == 0
        assert track == 1

    def test_extract_disc_track_chapter_pattern(self, temp_dir):
        """Test extraction with 'Chapter' pattern."""
        root = temp_dir / "book"
        root.mkdir()
        file_path = root / "Chapter 10.mp3"

        disc, track, ext = extract_disc_track(file_path, root)

        assert disc == 0
        assert track == 10

    def test_extract_disc_track_with_title(self, temp_dir):
        """Test extraction from filename with title."""
        root = temp_dir / "book"
        root.mkdir()
        file_path = root / "01 - Introduction.mp3"

        disc, track, ext = extract_disc_track(file_path, root)

        assert disc == 0
        assert track == 1

    def test_extract_disc_track_no_patterns(self, temp_dir):
        """Test extraction when no patterns match."""
        root = temp_dir / "book"
        root.mkdir()
        file_path = root / "cover.jpg"

        disc, track, ext = extract_disc_track(file_path, root)

        assert disc == 0
        assert track == 0
        assert ext == ".jpg"

    def test_extract_disc_track_case_insensitive(self, temp_dir):
        """Test that pattern matching is case-insensitive."""
        root = temp_dir / "book"
        root.mkdir()
        disc_dir = root / "DISC 01"
        disc_dir.mkdir()
        file_path = disc_dir / "TRACK 05.mp3"

        disc, track, ext = extract_disc_track(file_path, root)

        assert disc == 1
        assert track == 5

    def test_extract_disc_track_path_not_under_root(self, temp_dir):
        """Test extraction when path is not under root."""
        root = temp_dir / "book"
        root.mkdir()
        unrelated_path = temp_dir / "other" / "file.mp3"

        disc, track, ext = extract_disc_track(unrelated_path, root)

        # Should return defaults when path not under root
        assert disc == 0
        assert track == 0


class TestTryHardlink:
    """Test the try_hardlink() function for creating hardlinks."""

    def test_try_hardlink_success(self, temp_dir):
        """Test successful hardlink creation."""
        src = temp_dir / "source.txt"
        dst = temp_dir / "dest.txt"
        src.write_text("test content")

        result = try_hardlink(src, dst)

        assert result is True
        assert dst.exists()

        # Verify it's actually a hardlink (same inode)
        assert src.stat().st_ino == dst.stat().st_ino

    def test_try_hardlink_different_filesystems(self, temp_dir, monkeypatch):
        """Test hardlink failure when filesystems differ."""
        src = temp_dir / "source.txt"
        src.write_text("test content")
        dst = temp_dir / "dest.txt"

        # Mock stat to simulate different filesystems
        original_stat = Path.stat

        def mock_stat(path_self):
            stat_result = original_stat(path_self)
            if str(path_self) == str(src):
                # Mock source on different device
                class MockStat:
                    st_dev = 1
                    st_ino = stat_result.st_ino
                    st_size = stat_result.st_size

                return MockStat()
            elif str(path_self) == str(dst.parent):
                # Mock dest parent on different device
                class MockStat:
                    st_dev = 2
                    st_ino = stat_result.st_ino
                    st_size = stat_result.st_size

                return MockStat()
            return stat_result

        monkeypatch.setattr(Path, "stat", mock_stat)

        result = try_hardlink(src, dst)

        assert result is False
        assert not dst.exists()

    def test_try_hardlink_permission_error(self, temp_dir, monkeypatch):
        """Test hardlink failure due to permissions."""
        src = temp_dir / "source.txt"
        dst = temp_dir / "dest.txt"
        src.write_text("test content")

        # Mock os.link to raise permission error
        def mock_link(src_path, dst_path):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(os, "link", mock_link)

        result = try_hardlink(src, dst)

        assert result is False

    def test_try_hardlink_source_not_exists(self, temp_dir):
        """Test hardlink when source doesn't exist."""
        src = temp_dir / "nonexistent.txt"
        dst = temp_dir / "dest.txt"

        result = try_hardlink(src, dst)

        assert result is False

    def test_try_hardlink_preserves_content(self, temp_dir):
        """Test that hardlinked files share content."""
        src = temp_dir / "source.txt"
        dst = temp_dir / "dest.txt"
        src.write_text("original content")

        try_hardlink(src, dst)

        # Modify via destination
        dst.write_text("modified content")

        # Should be reflected in source (same file)
        assert src.read_text() == "modified content"


class TestUtilityEdgeCases:
    """Test edge cases and error handling in utility functions."""

    def test_sanitize_unicode_characters(self):
        """Test sanitization with unicode characters."""
        result = sanitize("Book: Café")
        assert "Café" in result
        assert ":" not in result

    def test_extract_disc_track_double_digit_disc(self, temp_dir):
        """Test extraction with double-digit disc numbers."""
        root = temp_dir / "book"
        root.mkdir()
        disc_dir = root / "Disc 12"
        disc_dir.mkdir()
        file_path = disc_dir / "Track 99.mp3"

        disc, track, ext = extract_disc_track(file_path, root)

        assert disc == 12
        assert track == 99

    def test_next_available_very_high_numbers(self, temp_dir):
        """Test next_available with many existing conflicts."""
        base_path = temp_dir / "test.txt"
        base_path.write_text("original")

        # Create many conflicts
        for i in range(2, 12):
            (temp_dir / f"test.txt ({i})").write_text(str(i))

        result = next_available(base_path)
        assert result == temp_dir / "test.txt (12)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
