"""Phase 1 step 4: ingest folder setting/checks, ebook choices endpoint, and
ebook import through /import."""
import json
import os

import pytest
from sqlalchemy import text

import config
import db
import main
from test_import import make_torrent, qb_for, set_category_calls

# Own hash: rows here are ebooks, and /import falls back to a lookup by hash.
HASH = "e0" * 20


@pytest.fixture
def ingest(tmp_path, monkeypatch):
    d = tmp_path / "ebook-import"
    d.mkdir()
    monkeypatch.setattr(main.settings, "EBOOK_INGEST_DIR", str(d))
    monkeypatch.setattr(main.settings, "QB_POSTIMPORT_CATEGORY_EBOOK", "ebooks-imported")
    return d


def ebook_row(qb_hash=HASH):
    with db.engine.begin() as cx:
        return cx.execute(text("INSERT INTO history (mam_id, title, qb_hash, qb_status, media_type) "
                               "VALUES ('77','Ebook',:h,'added','ebook')"), {"h": qb_hash}).lastrowid


# ---------------- /health ----------------
def test_health_reports_ingest_state(client, tmp_path, monkeypatch):
    monkeypatch.setattr(main.settings, "EBOOK_INGEST_DIR", "")
    assert client.get("/health").json()["ebook_ingest"] == "not configured"
    monkeypatch.setattr(main.settings, "EBOOK_INGEST_DIR", str(tmp_path))
    assert client.get("/health").json()["ebook_ingest"] == "ok"
    monkeypatch.setattr(main.settings, "EBOOK_INGEST_DIR", str(tmp_path / "missing"))
    j = client.get("/health").json()
    assert j["ok"] is True and "does not exist" in j["ebook_ingest"]


def test_health_does_not_write_into_the_ingest_folder(client, tmp_path, monkeypatch):
    monkeypatch.setattr(main.settings, "EBOOK_INGEST_DIR", str(tmp_path))
    client.get("/health")
    assert list(tmp_path.iterdir()) == []


# ---------------- setup ----------------
def saved_config():
    try:
        return json.load(open(config.CONFIG_PATH))
    except FileNotFoundError:
        return {}


def test_setup_saves_a_writable_ingest_folder(client, tmp_path, monkeypatch):
    monkeypatch.delenv("EBOOK_INGEST_DIR", raising=False)
    d = tmp_path / "drop"
    d.mkdir()
    r = client.post("/api/setup", json={"ebook_ingest_dir": f"{d}/"})
    assert r.status_code == 200, r.text
    assert saved_config()["EBOOK_INGEST_DIR"] == str(d)
    assert main.settings.EBOOK_INGEST_DIR == str(d)
    assert list(d.iterdir()) == []  # the write test cleaned up after itself


@pytest.mark.parametrize("make", ["missing", "file", "readonly"])
def test_setup_rejects_unusable_ingest_folder(client, tmp_path, make):
    target = tmp_path / "drop"
    if make == "file":
        target.write_text("x")
    elif make == "readonly":
        target.mkdir()
        target.chmod(0o500)
    before = saved_config().get("EBOOK_INGEST_DIR")
    try:
        r = client.post("/api/setup", json={"ebook_ingest_dir": str(target)})
    finally:
        if make == "readonly":
            target.chmod(0o700)
    if make == "readonly" and os.geteuid() == 0:
        pytest.skip("root can write anywhere")
    assert r.status_code == 400
    assert saved_config().get("EBOOK_INGEST_DIR") == before


def test_setup_page_shows_ingest_field(client, monkeypatch):
    monkeypatch.setattr(main.settings, "EBOOK_INGEST_DIR", "/media/books/import")
    page = client.get("/setup").text
    assert 'id="ebook_ingest_dir"' in page and 'value="/media/books/import"' in page


# ---------------- choices ----------------
def test_ebook_choices_endpoint(net, client, dirs):
    dl, _ = dirs
    files = {"book.epub": b"E", "book.pdf": b"PP", "cover.jpg": b"J"}
    qb_for(net, make_torrent(dl, files), files)
    books = client.get(f"/import/ebook-choices?hash={HASH}").json()["books"]
    assert [(f["path"], f["format"], f["selected"]) for f in books[0]["files"]] == [
        ("book.epub", "epub", True), ("book.pdf", "pdf", False)]
    assert net.mam_requests == []


# ---------------- import ----------------
def test_ebook_import_end_to_end(net, client, dirs, ingest):
    dl, lib = dirs
    hid = ebook_row()
    files = {"book.epub": b"E", "book.pdf": b"P", "cover.jpg": b"J", "info.nfo": b"N"}
    qb_for(net, make_torrent(dl, files), files)

    r = client.post("/import", json={"hash": HASH, "history_id": hid, "files": ["book.epub"]})
    assert r.status_code == 200, r.text
    assert r.json()["files"] == ["book.epub"] and r.json()["dest"] == str(ingest)
    assert [p.name for p in ingest.iterdir()] == ["book.epub"]
    assert os.stat(ingest / "book.epub").st_ino != os.stat(dl / "Some Book" / "book.epub").st_ino
    assert list(lib.iterdir()) == []  # nothing in the audiobook library
    assert set_category_calls(net) == [{"hashes": HASH, "category": "ebooks-imported"}]
    with db.engine.begin() as cx:
        assert cx.execute(text("SELECT qb_status FROM history WHERE id=:i"), {"i": hid}).scalar() == "imported"
    assert net.mam_requests == []


def test_ebook_import_needs_a_choice(net, client, dirs, ingest):
    hid = ebook_row()
    r = client.post("/import", json={"hash": HASH, "history_id": hid, "files": []})
    assert r.status_code == 400
    assert net.requests == []


def test_ebook_import_rejects_escaping_paths_and_copies_nothing(net, client, dirs, ingest):
    dl, _ = dirs
    hid = ebook_row()
    files = {"book.epub": b"E"}
    qb_for(net, make_torrent(dl, files), files)
    r = client.post("/import", json={"hash": HASH, "history_id": hid, "files": ["book.epub", "../../etc/passwd"]})
    assert r.status_code == 400
    assert list(ingest.iterdir()) == []
    assert set_category_calls(net) == []
    with db.engine.begin() as cx:
        assert cx.execute(text("SELECT qb_status FROM history WHERE id=:i"), {"i": hid}).scalar() == "added"


def test_audiobook_import_still_requires_author_and_title(net, client, dirs):
    r = client.post("/import", json={"hash": HASH, "author": "", "title": "T"})
    assert r.status_code == 400
    assert net.requests == []
