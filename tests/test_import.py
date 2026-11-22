"""/qb/torrents and /import: qB is mocked, files live in a temp dir. No MAM
traffic is involved (the autouse net fixture fails on any MAM request)."""
import os

import httpx
import pytest
from sqlalchemy import text

import db
import main

HASH = "deadbeef" * 5


def make_torrent(dl, files: dict[str, bytes], root="Some Book"):
    for rel, data in files.items():
        p = dl / root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return f"/downloads/{root}"


def qb_for(net, content_path, files):
    def qb(request):
        path = request.url.path
        if path == "/api/v2/torrents/files":
            return httpx.Response(200, json=[{"name": n} for n in files])
        if path == "/api/v2/torrents/properties":
            return httpx.Response(200, json={"save_path": "/downloads"})
        if path == "/api/v2/torrents/info":
            return httpx.Response(200, json=[{"hash": HASH, "content_path": content_path}])
        if path == "/api/v2/torrents/setCategory":
            return httpx.Response(200)
        return net.default_qb(request)
    net.qb_handler = qb


def set_category_calls(net):
    from urllib.parse import parse_qs
    return [{k: v[0] for k, v in parse_qs(r.read().decode(), keep_blank_values=True).items()}
            for r in net.qb_requests if r.url.path == "/api/v2/torrents/setCategory"]


# ---------------- /qb/torrents ----------------
def test_qb_torrents_lists_completed_in_category(net, client):
    def qb(request):
        path = request.url.path
        if path == "/api/v2/torrents/info":
            assert request.url.params["category"] == main.settings.QB_CATEGORY
            assert request.url.params["filter"] == "completed"
            return httpx.Response(200, json=[
                {"hash": "h1", "name": "Multi", "save_path": "/downloads", "total_size": 10, "added_on": 1},
                {"hash": "h2", "name": "single.m4b", "save_path": "/downloads", "total_size": 5, "added_on": 2},
                {"name": "no hash, skipped"},
            ])
        if path == "/api/v2/torrents/files":
            if request.url.params["hash"] == "h1":
                return httpx.Response(200, json=[{"name": "Multi/01.mp3"}, {"name": "Multi/02.mp3"}])
            return httpx.Response(200, json=[{"name": "single.m4b"}])
        return net.default_qb(request)
    net.qb_handler = qb
    items = client.get("/qb/torrents").json()["items"]
    assert [(i["hash"], i["root"], i["single_file"]) for i in items] == [("h1", "Multi", False), ("h2", "single.m4b", True)]
    assert items[0]["size"] == 10


# ---------------- /import ----------------
def test_import_links_all_but_cue(net, client, dirs, monkeypatch):
    dl, lib = dirs
    monkeypatch.setattr(main.settings, "IMPORT_MODE", "link")
    files = {"01.mp3": b"a", "sub/02.mp3": b"b", "book.cue": b"c"}
    qb_for(net, make_torrent(dl, files), files)

    r = client.post("/import", json={"author": "Ann: Author", "title": "A/Book", "hash": HASH})
    assert r.status_code == 200, r.text
    dest = lib / "Ann - Author" / "A﹨Book"
    assert r.json()["dest"] == str(dest)
    assert (dest / "01.mp3").read_bytes() == b"a"
    assert (dest / "sub" / "02.mp3").exists()
    assert not (dest / "book.cue").exists()
    # link mode really hardlinks (same filesystem in tmp)
    assert os.stat(dest / "01.mp3").st_ino == os.stat(dl / "Some Book" / "01.mp3").st_ino
    assert set_category_calls(net) == [{"hashes": HASH, "category": "imported"}]


def test_import_copy_mode_does_not_link(net, client, dirs, monkeypatch):
    dl, lib = dirs
    monkeypatch.setattr(main.settings, "IMPORT_MODE", "copy")
    files = {"01.mp3": b"a"}
    qb_for(net, make_torrent(dl, files), files)
    client.post("/import", json={"author": "A", "title": "B", "hash": HASH})
    src, dst = dl / "Some Book" / "01.mp3", lib / "A" / "B" / "01.mp3"
    assert dst.read_bytes() == b"a"
    assert os.stat(src).st_ino != os.stat(dst).st_ino
    assert os.stat(src).st_nlink == 1


def test_import_move_mode_moves(net, client, dirs, monkeypatch):
    dl, lib = dirs
    monkeypatch.setattr(main.settings, "IMPORT_MODE", "move")
    files = {"01.mp3": b"a"}
    qb_for(net, make_torrent(dl, files), files)
    client.post("/import", json={"author": "A", "title": "B", "hash": HASH})
    assert (lib / "A" / "B" / "01.mp3").exists()
    assert not (dl / "Some Book" / "01.mp3").exists()


def test_import_single_file_torrent(net, client, dirs, monkeypatch):
    dl, lib = dirs
    monkeypatch.setattr(main.settings, "IMPORT_MODE", "copy")
    (dl / "single.m4b").write_bytes(b"x")
    qb_for(net, "/downloads/single.m4b", {"single.m4b": b"x"})
    r = client.post("/import", json={"author": "A", "title": "B", "hash": HASH})
    assert r.status_code == 200, r.text
    assert (lib / "A" / "B" / "single.m4b").read_bytes() == b"x"


def test_import_only_cue_is_rejected(net, client, dirs):
    dl, _ = dirs
    (dl / "x.cue").write_bytes(b"c")
    qb_for(net, "/downloads/x.cue", {"x.cue": b"c"})
    r = client.post("/import", json={"author": "A", "title": "B", "hash": HASH})
    assert r.status_code == 400


def test_import_avoids_collisions(net, client, dirs, monkeypatch):
    dl, lib = dirs
    monkeypatch.setattr(main.settings, "IMPORT_MODE", "copy")
    (lib / "A" / "B").mkdir(parents=True)
    files = {"01.mp3": b"a"}
    qb_for(net, make_torrent(dl, files), files)
    r = client.post("/import", json={"author": "A", "title": "B", "hash": HASH})
    assert r.json()["dest"] == str(lib / "A" / "B (2)")


def test_import_marks_history_imported(net, client, dirs, monkeypatch):
    dl, _ = dirs
    monkeypatch.setattr(main.settings, "IMPORT_MODE", "copy")
    with db.engine.begin() as cx:
        hid = cx.execute(text("INSERT INTO history (mam_id, title, qb_hash, qb_status) VALUES ('9','T',:h,'added')"),
                         {"h": HASH}).lastrowid
    files = {"01.mp3": b"a"}
    qb_for(net, make_torrent(dl, files), files)
    client.post("/import", json={"author": "A", "title": "T", "hash": HASH, "history_id": hid})
    with db.engine.begin() as cx:
        row = cx.execute(text("SELECT qb_status, imported_at FROM history WHERE id=:id"), {"id": hid}).mappings().one()
    assert row["qb_status"] == "imported" and row["imported_at"]


def test_import_missing_content_path_is_404(net, client, dirs):
    qb_for(net, "", {"01.mp3": b"a"})
    r = client.post("/import", json={"author": "A", "title": "B", "hash": HASH})
    assert r.status_code == 404


def test_import_qb_login_failure(net, client, dirs):
    def qb(request):
        if request.url.path == "/api/v2/auth/login":
            return httpx.Response(200, text="Fails.")
        return net.default_qb(request)
    net.qb_handler = qb
    r = client.post("/import", json={"author": "A", "title": "B", "hash": HASH})
    assert r.status_code == 424


def test_history_list_and_delete(client):
    with db.engine.begin() as cx:
        hid = cx.execute(text("INSERT INTO history (mam_id, title, qb_status) VALUES ('77','Del','added')")).lastrowid
    assert any(i["id"] == hid for i in client.get("/history").json()["items"])
    client.delete(f"/history/{hid}")
    assert not any(i["id"] == hid for i in client.get("/history").json()["items"])


# ---------------- path mapping ----------------
import importer


@pytest.mark.parametrize("qb_path,expected", [
    ("/downloads/Book", "/media/torrents/Book"),
    ("/downloads", "/media/torrents"),
    ("/downloadsX/Book", "/downloadsX/Book"),          # prefix must match a whole segment
    ("/data/Book", "/srv/data/Book"),                   # second mapping
    ("/media/torrents/Book", "/media/torrents/Book"),   # already in-container
    ("/mnt/user/media/torrents/B", "/media/torrents/B"),  # legacy Unraid fallback
    ("/mnt/media/torrents/B", "/media/torrents/B"),
    ("", ""),
])
def test_map_qb_path(qb_path, expected):
    pm = [("/downloads", "/media/torrents"), ("/data", "/srv/data")]
    assert importer.map_qb_path(qb_path, pm) == expected


def test_sanitize():
    assert importer.sanitize("  A: B/C\\D   E ") == "A - B﹨C﹨D E"
    assert importer.sanitize("   ") == "Unknown"
