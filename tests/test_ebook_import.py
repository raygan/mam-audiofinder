"""Phase 1 step 3: ebook choices and copy-only import into Grimmory's ingest
folder. Local files only."""
import os
import shutil
from pathlib import Path

import pytest

import config
import importer
from importer import ImportFailed, ebook_choices, import_ebooks


@pytest.fixture
def ingest(tmp_path):
    d = tmp_path / "bookdrop"
    d.mkdir()
    return d


def torrent(tmp_path, files: dict[str, bytes], root="Book Torrent") -> Path:
    base = tmp_path / "downloads" / root
    for rel, data in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return base


def selected(books):
    return [f["path"] for b in books for f in b["files"] if f["selected"]]


# ---------------- choices ----------------
def test_roadmap_example_defaults_to_exactly_the_epub(tmp_path, ingest):
    # ROADMAP acceptance: book.epub, book.pdf, cover.jpg, info.nfo -> exactly book.epub
    src = torrent(tmp_path, {"book.epub": b"E", "book.pdf": b"P", "cover.jpg": b"J", "info.nfo": b"N"})
    books = ebook_choices(src)
    assert len(books) == 1
    assert [f["format"] for f in books[0]["files"]] == ["epub", "pdf"]
    assert selected(books) == ["book.epub"]

    out = import_ebooks(src, selected(books), str(ingest))
    assert [p.name for p in out] == ["book.epub"]
    assert sorted(p.name for p in ingest.iterdir()) == ["book.epub"]
    assert (ingest / "book.epub").read_bytes() == b"E"


def test_several_books_each_get_their_own_default(tmp_path):
    src = torrent(tmp_path, {"a.epub": b"", "a.pdf": b"", "b.pdf": b"", "c.cbz": b"", "c.mobi": b""})
    books = {b["book"]: b for b in ebook_choices(src)}
    assert set(books) == {"a", "b", "c"}
    assert selected(books.values()) == ["a.epub", "b.pdf", "c.mobi"]


def test_preference_order_is_configurable(tmp_path):
    src = torrent(tmp_path, {"x.epub": b"", "x.pdf": b""})
    assert selected(ebook_choices(src, preference=("pdf", "epub"))) == ["x.pdf"]


def test_unlisted_format_ranks_last_but_is_still_offered(tmp_path):
    src = torrent(tmp_path, {"comic.cbr": b"", "comic.pdf": b""})
    (book,) = ebook_choices(src)
    assert [f["format"] for f in book["files"]] == ["pdf", "cbr"]
    assert book["files"][0]["selected"] and not book["files"][1]["selected"]


def test_same_name_in_different_folders_are_different_books(tmp_path):
    src = torrent(tmp_path, {"vol1/book.epub": b"", "vol2/book.epub": b""})
    assert sorted(selected(ebook_choices(src))) == ["vol1/book.epub", "vol2/book.epub"]


def test_non_ebook_and_hidden_files_are_ignored(tmp_path):
    src = torrent(tmp_path, {"cover.jpg": b"", "info.nfo": b"", "notes.txt": b"", ".hidden.epub": b"", "real.EPUB": b""})
    assert selected(ebook_choices(src)) == ["real.EPUB"]


def test_single_file_torrent(tmp_path, ingest):
    d = tmp_path / "downloads"
    d.mkdir()
    (d / "solo.epub").write_bytes(b"S")
    books = ebook_choices(d / "solo.epub")
    assert selected(books) == ["solo.epub"]
    import_ebooks(d / "solo.epub", ["solo.epub"], str(ingest))
    assert (ingest / "solo.epub").read_bytes() == b"S"


def test_sizes_are_reported(tmp_path):
    src = torrent(tmp_path, {"b.epub": b"12345"})
    assert ebook_choices(src)[0]["files"][0]["size"] == 5


# ---------------- import: copy only ----------------
def test_ebook_import_never_hardlinks(tmp_path, ingest, monkeypatch):
    # ROADMAP acceptance: verified with inode counts, even with IMPORT_MODE=link for audiobooks.
    monkeypatch.setattr(config.settings, "IMPORT_MODE", "link")
    src = torrent(tmp_path, {"book.epub": b"E" * 1000})
    (out,) = import_ebooks(src, ["book.epub"], str(ingest))
    s, d = os.stat(src / "book.epub"), os.stat(out)
    assert s.st_ino != d.st_ino
    assert s.st_nlink == 1 and d.st_nlink == 1
    assert (src / "book.epub").exists()  # not moved


def test_import_only_copies_what_was_chosen(tmp_path, ingest):
    src = torrent(tmp_path, {"book.epub": b"E", "book.pdf": b"P"})
    import_ebooks(src, ["book.pdf"], str(ingest))
    assert [p.name for p in ingest.iterdir()] == ["book.pdf"]


def test_import_both_formats_when_chosen(tmp_path, ingest):
    src = torrent(tmp_path, {"book.epub": b"E", "book.pdf": b"P"})
    import_ebooks(src, ["book.epub", "book.pdf"], str(ingest))
    assert sorted(p.name for p in ingest.iterdir()) == ["book.epub", "book.pdf"]


def test_import_is_flat(tmp_path, ingest):
    src = torrent(tmp_path, {"deep/nested/book.epub": b"E"})
    import_ebooks(src, ["deep/nested/book.epub"], str(ingest))
    assert [p.name for p in ingest.iterdir()] == ["book.epub"]


def test_collisions_are_numbered_before_the_extension(tmp_path, ingest):
    (ingest / "book.epub").write_bytes(b"old")
    (ingest / "book (2).epub").write_bytes(b"old2")
    src = torrent(tmp_path, {"book.epub": b"new"})
    (out,) = import_ebooks(src, ["book.epub"], str(ingest))
    assert out.name == "book (3).epub" and out.read_bytes() == b"new"
    assert (ingest / "book.epub").read_bytes() == b"old"  # never overwritten


def test_no_partial_files_left_after_success(tmp_path, ingest):
    src = torrent(tmp_path, {"a.epub": b"A", "b.pdf": b"B"})
    import_ebooks(src, ["a.epub", "b.pdf"], str(ingest))
    assert not [p for p in ingest.iterdir() if p.name.endswith(importer.PARTIAL_SUFFIX) or p.name.startswith(".")]


def test_failed_copy_leaves_no_partial_and_no_final(tmp_path, ingest, monkeypatch):
    src = torrent(tmp_path, {"book.epub": b"E"})
    real = shutil.copyfile

    def half_copy(a, b, *args, **kw):
        Path(b).write_bytes(b"half")
        raise OSError("disk full")
    monkeypatch.setattr(importer.shutil, "copyfile", half_copy)
    with pytest.raises(OSError):
        import_ebooks(src, ["book.epub"], str(ingest))
    assert list(ingest.iterdir()) == []
    monkeypatch.setattr(importer.shutil, "copyfile", real)


def test_partial_uses_a_hidden_non_ebook_name(tmp_path, ingest, monkeypatch):
    seen = []
    real_replace = os.replace

    def spy(a, b):
        seen.append((Path(a).name, Path(b).name))
        return real_replace(a, b)
    monkeypatch.setattr(importer.os, "replace", spy)
    src = torrent(tmp_path, {"book.epub": b"E"})
    import_ebooks(src, ["book.epub"], str(ingest))
    assert seen == [(".book.epub.partial", "book.epub")]


# ---------------- import: choices are validated ----------------
@pytest.mark.parametrize("rel", [
    "../outside.epub", "/etc/passwd", "", "missing.epub", "cover.jpg", "sub/../../outside.epub",
])
def test_bad_choices_are_rejected_and_nothing_is_copied(tmp_path, ingest, rel):
    src = torrent(tmp_path, {"book.epub": b"E", "cover.jpg": b"J"})
    (tmp_path / "downloads" / "outside.epub").write_bytes(b"X")
    with pytest.raises(ImportFailed):
        import_ebooks(src, ["book.epub", rel], str(ingest))
    assert list(ingest.iterdir()) == []  # validated before any copy


def test_symlink_escaping_the_torrent_is_rejected(tmp_path, ingest):
    src = torrent(tmp_path, {"book.epub": b"E"})
    secret = tmp_path / "secret.epub"
    secret.write_bytes(b"S")
    (src / "link.epub").symlink_to(secret)
    with pytest.raises(ImportFailed):
        import_ebooks(src, ["link.epub"], str(ingest))


def test_single_file_torrent_cannot_reach_siblings(tmp_path, ingest):
    d = tmp_path / "downloads"
    d.mkdir()
    (d / "solo.epub").write_bytes(b"S")
    (d / "other.epub").write_bytes(b"O")
    with pytest.raises(ImportFailed):
        import_ebooks(d / "solo.epub", ["other.epub"], str(ingest))


def test_nothing_chosen_is_an_error(tmp_path, ingest):
    src = torrent(tmp_path, {"book.epub": b"E"})
    with pytest.raises(ImportFailed):
        import_ebooks(src, [], str(ingest))


def test_missing_ingest_folder_is_an_error(tmp_path):
    src = torrent(tmp_path, {"book.epub": b"E"})
    with pytest.raises(ImportFailed):
        import_ebooks(src, ["book.epub"], str(tmp_path / "nope"))


# ---------------- settings ----------------
def test_ext_list_parsing():
    assert importer.parse_ext_list(" epub, .PDF ,mobi,epub", ()) == ("epub", "pdf", "mobi")
    assert importer.parse_ext_list("", ("epub",)) == ("epub",)
    assert importer.parse_ext_list(None, ("epub",)) == ("epub",)


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("EBOOK_EXTENSIONS", raising=False)
    monkeypatch.setenv("EBOOK_FORMAT_PREFERENCE", "pdf,epub")
    s = config.Settings()
    assert "epub" in s.EBOOK_EXTENSIONS and "cbz" in s.EBOOK_EXTENSIONS
    assert s.EBOOK_FORMAT_PREFERENCE == ("pdf", "epub")
