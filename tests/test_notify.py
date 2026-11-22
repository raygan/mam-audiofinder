"""Phase 2 step 3: ntfy / JSON webhook notifications."""
import asyncio
import json

import httpx
import pytest
from sqlalchemy import text

import db
import main
import notify
import wishlist
from conftest import FAKE_TOKEN
from test_wishlist import check, mam_returns, tor

NTFY = "https://ntfy.test/books"


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    with db.engine.begin() as cx:
        for t in ("wishlist", "wishlist_seen", "mam_request_log", "app_state"):
            cx.execute(text(f"DELETE FROM {t}"))
    s = main.settings
    for k, v in {"NOTIFY_WEBHOOK_URL": NTFY, "NOTIFY_FORMAT": "ntfy", "NOTIFY_TOKEN": "",
                 "NOTIFY_CLICK_URL": "", "NOTIFY_BODY_TEMPLATE": "", "NOTIFY_ON_IMPORT": False,
                 "WISHLIST_MAX_REQUESTS_PER_DAY": 20}.items():
        monkeypatch.setattr(s, k, v)


@pytest.fixture
def inbox(net):
    got = []
    def h(r):
        got.append(r)
        return httpx.Response(200, json={"id": "x"})
    net.hosts["ntfy.test"] = h
    return got


def body(r):
    return json.loads(r.read())


def send(*a):
    return asyncio.run(notify.send(*a))


# ---------------- format ----------------
def test_ntfy_json_publish_shape(inbox, monkeypatch):
    monkeypatch.setattr(main.settings, "NOTIFY_CLICK_URL", "https://books.example/wishlist/view")
    assert send("match", "Wishlist: 1 new match for “Hex Kittens”", "📖 Hex Kittens 6 (EPUB, 12 seeders)")
    (r,) = inbox
    assert str(r.url) == "https://ntfy.test/"  # JSON publishing goes to the server root
    b = body(r)
    assert b["topic"] == "books" and b["title"].startswith("Wishlist") and "Hex Kittens 6" in b["message"]
    assert b["tags"] == ["books"] and b["click"] == "https://books.example/wishlist/view"
    assert "authorization" not in r.headers


def test_ntfy_under_a_path_prefix(inbox, monkeypatch):
    monkeypatch.setattr(main.settings, "NOTIFY_WEBHOOK_URL", "https://ntfy.test/ntfy/books")
    send("test", "t", "m")
    assert str(inbox[0].url) == "https://ntfy.test/ntfy" and body(inbox[0])["topic"] == "books"


def test_token_is_sent_as_bearer(inbox, monkeypatch):
    monkeypatch.setattr(main.settings, "NOTIFY_TOKEN", "tk_secret123")
    send("test", "t", "m")
    assert inbox[0].headers["authorization"] == "Bearer tk_secret123"


def test_generic_json_default_and_template(inbox, monkeypatch):
    monkeypatch.setattr(main.settings, "NOTIFY_FORMAT", "json")
    monkeypatch.setattr(main.settings, "NOTIFY_WEBHOOK_URL", "https://ntfy.test/api/webhook/abc")
    send("match", 'Title "quoted"', "line1\nline2")
    assert str(inbox[0].url) == "https://ntfy.test/api/webhook/abc"
    assert body(inbox[0]) == {"event": "match", "title": 'Title "quoted"', "message": "line1\nline2", "click": ""}
    monkeypatch.setattr(main.settings, "NOTIFY_BODY_TEMPLATE", '{"msg": "{{title}}: {{message}}", "kind": "{{event}}"}')
    send("match", 'Title "quoted"', "line1\nline2")
    assert body(inbox[1]) == {"msg": 'Title "quoted": line1\nline2', "kind": "match"}


def test_no_url_means_no_request(net, monkeypatch):
    monkeypatch.setattr(main.settings, "NOTIFY_WEBHOOK_URL", "")
    assert send("test", "t", "m") is False
    assert net.requests == []


@pytest.mark.parametrize("url", ["https://www.myanonamouse.net/x", "https://myanonamouse.net/x", "ftp://ntfy.test/x", "ntfy.test/books"])
def test_bad_targets_are_refused_without_sending(net, monkeypatch, url):
    monkeypatch.setattr(main.settings, "NOTIFY_WEBHOOK_URL", url)
    assert send("test", "t", "m") is False
    assert net.requests == []


@pytest.mark.parametrize("reply", [httpx.Response(500), httpx.Response(401), httpx.Response(302, headers={"location": "/x"})])
def test_rejected_notification_returns_false(net, reply):
    net.hosts["ntfy.test"] = lambda r: reply
    assert send("test", "t", "m") is False


def test_network_error_returns_false_and_is_redacted(net, caplog):
    def boom(r):
        raise httpx.ConnectError(f"refused mam_id={FAKE_TOKEN}")
    net.hosts["ntfy.test"] = boom
    assert send("test", "t", "m") is False


def test_payload_never_contains_cookie_or_download_links(inbox):
    text_in = f"mam_id={FAKE_TOKEN} https://www.myanonamouse.net/tor/download.php/AAAAaaaa0000==?tid=1"
    send("match", text_in, text_in)
    raw = inbox[0].read().decode()
    assert FAKE_TOKEN not in raw and "AAAAaaaa0000" not in raw


# ---------------- wishlist hook (ROADMAP acceptance) ----------------
def test_one_match_one_notification_then_none(net, inbox):
    item = wishlist.create("wanted book", media="ebook", label="Wanted")
    mam_returns(net, [], [tor(903001)], [tor(903001)])
    check(item["id"])
    assert inbox == []
    check(item["id"])
    assert len(inbox) == 1
    b = body(inbox[0])
    assert b["title"] == "Wishlist: 1 new match for “Wanted”" and "Wanted Book" in b["message"]
    assert "dl" not in b["message"] and "tid=" not in b["message"]
    check(item["id"])
    assert len(inbox) == 1


def test_failed_notification_does_not_fail_the_check(net):
    net.hosts["ntfy.test"] = lambda r: httpx.Response(500)
    item = wishlist.create("wanted book", media="ebook")
    mam_returns(net, [tor(903101)])
    res = check(item["id"])
    assert len(res["new_matches"]) == 1 and len(wishlist.matches(item["id"])) == 1


def test_many_matches_are_summarised(net, inbox):
    item = wishlist.create("wanted book", media="ebook")
    mam_returns(net, [tor(903200 + i, title=f"Book {i}") for i in range(12)])
    check(item["id"])
    b = body(inbox[0])
    assert b["title"].startswith("Wishlist: 12 new matches") and "…and 2 more" in b["message"]


# ---------------- import hook ----------------
def test_import_notification_only_when_enabled(inbox, monkeypatch):
    assert asyncio.run(notify.imported("Book", "audiobook")) is False
    assert inbox == []
    monkeypatch.setattr(main.settings, "NOTIFY_ON_IMPORT", True)
    assert asyncio.run(notify.imported("Book", "ebook")) is True
    assert body(inbox[0])["title"] == "Imported: Book"


# ---------------- setup + test button ----------------
def saved():
    import config
    try:
        return json.load(open(config.CONFIG_PATH))
    except FileNotFoundError:
        return {}


@pytest.fixture
def restore_config():
    """These tests save to the shared test config file; put it back so later
    tests that reload settings don't inherit a notification URL."""
    import os
    import config
    path = config.CONFIG_PATH
    before = open(path).read() if os.path.exists(path) else None
    yield
    if before is None:
        if os.path.exists(path):
            os.remove(path)
    else:
        with open(path, "w") as f:
            f.write(before)


def test_setup_saves_notify_settings_and_keeps_token_secret(client, monkeypatch, restore_config):
    for k in ("NOTIFY_WEBHOOK_URL", "NOTIFY_TOKEN", "NOTIFY_FORMAT"):
        monkeypatch.delenv(k, raising=False)
    r = client.post("/api/setup", json={"notify_webhook_url": NTFY, "notify_format": "ntfy",
                                        "notify_token": "tk_abc", "notify_on_import": True})
    assert r.status_code == 200, r.text
    assert saved()["NOTIFY_WEBHOOK_URL"] == NTFY and saved()["NOTIFY_TOKEN"] == "tk_abc"
    page = client.get("/setup").text
    assert "tk_abc" not in page and "Saved (leave blank to keep)" in page
    # blank token keeps it; the clear box removes it
    client.post("/api/setup", json={"notify_token": ""})
    assert saved()["NOTIFY_TOKEN"] == "tk_abc"
    client.post("/api/setup", json={"notify_clear_token": True})
    assert saved()["NOTIFY_TOKEN"] == ""


@pytest.mark.parametrize("url", ["https://www.myanonamouse.net/hook", "not a url"])
def test_setup_refuses_bad_notify_url(client, url, restore_config):
    before = saved().get("NOTIFY_WEBHOOK_URL")
    assert client.post("/api/setup", json={"notify_webhook_url": url}).status_code == 400
    assert saved().get("NOTIFY_WEBHOOK_URL") == before


def test_test_button_sends_one(client, inbox):
    assert client.post("/api/notify/test").status_code == 200
    assert len(inbox) == 1 and body(inbox[0])["tags"] == ["bell"]


def test_test_button_reports_failure(client, net):
    net.hosts["ntfy.test"] = lambda r: httpx.Response(403)
    r = client.post("/api/notify/test")
    assert r.status_code == 424


def test_test_button_without_url(client, net, monkeypatch):
    monkeypatch.setattr(main.settings, "NOTIFY_WEBHOOK_URL", "")
    assert client.post("/api/notify/test").status_code == 400
    assert net.requests == []
