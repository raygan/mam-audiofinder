"""Phase 1 step 2: per-media qB categories/tags, history.media_type, and
import routing by the History row."""
from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy import create_engine, text

import config
import db
import main

DL = "AAAAaaaa0000_-bbbb="


def adds(net):
    return [{k: v[0] for k, v in parse_qs(r.read().decode()).items()}
            for r in net.qb_requests if r.url.path == "/api/v2/torrents/add"]


# ---------------- settings ----------------
def fresh_settings(monkeypatch, **env):
    for k in ("QB_CATEGORY", "QB_CATEGORY_AUDIO", "QB_CATEGORY_EBOOK", "QB_POSTIMPORT_CATEGORY",
              "QB_POSTIMPORT_CATEGORY_AUDIO", "QB_POSTIMPORT_CATEGORY_EBOOK", "QB_TAGS"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return config.Settings()


def test_defaults(monkeypatch):
    s = fresh_settings(monkeypatch)
    assert s.qb_category("audiobook") == "mam-audiofinder"
    assert s.qb_category("ebook") == "mam-audiofinder-ebooks"
    assert s.qb_tags("audiobook") == ["MAM", "audiobook"]
    assert s.qb_tags("ebook") == ["MAM", "ebook"]
    assert s.postimport_category("audiobook") == "" and s.postimport_category("ebook") == ""


def test_legacy_category_keys_still_apply_to_audiobooks(monkeypatch):
    s = fresh_settings(monkeypatch, QB_CATEGORY="my-books", QB_POSTIMPORT_CATEGORY="done")
    assert s.qb_category("audiobook") == "my-books"
    assert s.postimport_category("audiobook") == "done"
    assert s.qb_category("ebook") == "mam-audiofinder-ebooks"
    assert s.postimport_category("ebook") == ""
    assert s.QB_CATEGORY == "my-books"


def test_new_keys_override_legacy(monkeypatch):
    s = fresh_settings(monkeypatch, QB_CATEGORY="old", QB_CATEGORY_AUDIO="new-audio", QB_CATEGORY_EBOOK="new-ebook",
                       QB_POSTIMPORT_CATEGORY_EBOOK="ebooks-done")
    assert (s.qb_category("audiobook"), s.qb_category("ebook")) == ("new-audio", "new-ebook")
    assert s.postimport_category("ebook") == "ebooks-done"


def test_user_tags_lose_media_words(monkeypatch):
    s = fresh_settings(monkeypatch, QB_TAGS="MAM, audiobook ,Ebook,mine")
    assert s.qb_tags("ebook") == ["MAM", "mine", "ebook"]
    assert s.qb_tags("audiobook") == ["MAM", "mine", "audiobook"]


# ---------------- /add ----------------
@pytest.mark.parametrize("media,category,tag", [
    ("audiobook", "mam-audiofinder", "audiobook"),
    ("ebook", "mam-audiofinder-ebooks", "ebook"),
])
def test_add_uses_media_category_and_tag(net, client, monkeypatch, media, category, tag):
    monkeypatch.setattr(main.settings, "QB_CATEGORY_AUDIO", "mam-audiofinder")
    monkeypatch.setattr(main.settings, "QB_CATEGORY_EBOOK", "mam-audiofinder-ebooks")
    monkeypatch.setattr(main.settings, "QB_TAGS", "MAM,audiobook")
    r = client.post("/add", json={"id": "4242", "title": "T", "dl": f"{DL}?tid=4242", "media_type": media})
    assert r.status_code == 200, r.text
    (form,) = adds(net)
    assert form["category"] == category
    tags = form["tags"].split(",")
    assert tag in tags and ({"audiobook", "ebook"} - {tag}).isdisjoint(tags)
    assert "mamid=4242" in tags
    row = [i for i in client.get("/history").json()["items"] if i["mam_id"] == "4242"][0]
    assert row["media_type"] == media


def test_add_without_media_type_is_audiobook(net, client):
    client.post("/add", json={"id": "4343", "dl": f"{DL}?tid=4343"})
    row = [i for i in client.get("/history").json()["items"] if i["mam_id"] == "4343"][0]
    assert row["media_type"] == "audiobook"


@pytest.mark.parametrize("media", ["music", "both", "Ebook"])
def test_add_rejects_unknown_media_type(net, client, media):
    r = client.post("/add", json={"id": "1", "dl": f"{DL}?tid=1", "media_type": media})
    assert r.status_code == 400
    assert net.requests == []


# ---------------- /qb/torrents ----------------
@pytest.mark.parametrize("media,category", [("audiobook", "cat-a"), ("ebook", "cat-e")])
def test_qb_torrents_lists_media_category(net, client, monkeypatch, media, category):
    monkeypatch.setattr(main.settings, "QB_CATEGORY_AUDIO", "cat-a")
    monkeypatch.setattr(main.settings, "QB_CATEGORY_EBOOK", "cat-e")
    seen = []
    def qb(request):
        if request.url.path == "/api/v2/torrents/info":
            seen.append(request.url.params["category"])
            return httpx.Response(200, json=[])
        return net.default_qb(request)
    net.qb_handler = qb
    assert client.get(f"/qb/torrents?media={media}").status_code == 200
    assert seen == [category]


def test_qb_torrents_rejects_unknown_media(net, client):
    assert client.get("/qb/torrents?media=both").status_code == 400
    assert net.requests == []


# ---------------- /import routing ----------------
def test_ebook_rows_cannot_be_imported_yet(net, client):
    with db.engine.begin() as cx:
        hid = cx.execute(text("INSERT INTO history (mam_id, title, qb_hash, qb_status, media_type) "
                              "VALUES ('9','E','ebhash','added','ebook')")).lastrowid
    r = client.post("/import", json={"author": "A", "title": "E", "hash": "ebhash", "history_id": hid})
    assert r.status_code == 400
    assert net.requests == []  # not even qB is asked


def test_history_media_type_lookup():
    with db.engine.begin() as cx:
        hid = cx.execute(text("INSERT INTO history (mam_id, qb_hash, media_type) VALUES ('1','hh','ebook')")).lastrowid
    assert db.history_media_type(hid) == "ebook"
    assert db.history_media_type(None, "hh") == "ebook"
    assert db.history_media_type(None, "unknown") == "audiobook"
    assert db.history_media_type(999999) == "audiobook"


# ---------------- migration 3 ----------------
def test_migration_3_backfills_existing_rows(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'h.db'}", future=True)
    with eng.begin() as cx:  # a 0.7 database: versions 1-2 applied, rows present
        cx.execute(text("""CREATE TABLE history (id INTEGER PRIMARY KEY, mam_id TEXT, title TEXT, dl TEXT,
                           added_at TEXT, qb_status TEXT, qb_hash TEXT, author TEXT, narrator TEXT, imported_at TEXT)"""))
        cx.execute(text("CREATE TABLE schema_version (version INTEGER NOT NULL)"))
        cx.execute(text("INSERT INTO schema_version VALUES (1), (2)"))
        cx.execute(text("INSERT INTO history (mam_id, title) VALUES ('5', 'Old')"))
    assert db.migrate(eng) == 3
    with eng.begin() as cx:
        assert cx.execute(text("SELECT media_type FROM history WHERE mam_id='5'")).scalar() == "audiobook"
