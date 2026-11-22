"""HTTP routes: /health, /search and /add use only the documented MAM forms."""
import json

import httpx

import db
import main
import qb
import mam
from conftest import FAKE_TOKEN, load_fixture
from sqlalchemy import text

DL = "FAKEdlHASHaaaaaaaaaaaaaaaa"


def form_of(req: httpx.Request) -> dict:
    from urllib.parse import parse_qs
    return {k: v[0] for k, v in parse_qs(req.read().decode()).items()}


def qb_adds(net):
    return [r for r in net.qb_requests if r.url.path == "/api/v2/torrents/add"]


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_search_returns_normalized_results(net, client):
    net.mam_handler = lambda r: httpx.Response(200, json=load_fixture("synthetic_search.json"))
    r = client.post("/search", json={"tor": {"text": "example", "sortType": "default"}, "perpage": 25})
    assert r.status_code == 200
    data = r.json()
    assert [x["id"] for x in data["results"]] == ["100001", "100002"]
    assert len(net.mam_requests) == 1


def test_search_ignores_client_supplied_extra_keys(net, client):
    seen = {}
    def h(r):
        seen["body"] = json.loads(r.read())
        return httpx.Response(200, json={"data": [], "total": "0", "total_found": "0"})
    net.mam_handler = h
    r = client.post("/search", json={
        "tor": {"text": "x", "main_cat": ["15"], "browseFlagsHideVsShow": "1"},
        "perpage": 25, "thumbnail": "1",
    })
    assert r.status_code == 200
    assert seen["body"]["tor"]["main_cat"] == ["13"]
    assert "browseFlagsHideVsShow" not in seen["body"]["tor"]
    assert "thumbnail" not in seen["body"]


def test_empty_search_returns_no_results(net, client):
    net.mam_handler = lambda r: httpx.Response(200, json={"error": "Nothing returned, out of 0"})
    r = client.post("/search", json={"tor": {"text": "zzqqxxnotabook"}})
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_search_auth_failure_surfaces_reason(net, client):
    net.mam_handler = lambda r: httpx.Response(403)
    r = client.post("/search", json={"tor": {"text": "x"}})
    assert r.status_code == 424
    assert r.json()["error"] == "MamAuthError"
    assert "cookie" in r.json()["detail"].lower()
    assert FAKE_TOKEN not in r.text
    assert len(net.mam_requests) == 1


def test_add_with_dl_hands_qb_documented_url_and_app_never_calls_mam(net, client):
    r = client.post("/add", json={"id": "123", "title": "Example", "dl": DL})
    assert r.status_code == 200, r.text
    assert net.mam_requests == []
    (add,) = qb_adds(net)
    form = form_of(add)
    assert form["urls"] == f"https://www.myanonamouse.net/tor/download.php/{DL}?tid=123"
    assert "fl" not in form["urls"].split("?", 1)[1]
    assert "mamid=123" in form["tags"]


def test_add_without_dl_fetches_once_with_tid(net, client):
    net.mam_handler = lambda r: httpx.Response(200, content=b"d4:infod4:name1:xee",
                                               headers={"content-type": "application/x-bittorrent"})
    r = client.post("/add", json={"id": "456", "title": "No Hash"})
    assert r.status_code == 200, r.text
    (req,) = net.mam_requests
    assert str(req.url) == "https://www.myanonamouse.net/tor/download.php?tid=456"
    assert len(qb_adds(net)) == 1


def test_add_dl_without_id_is_rejected(net, client):
    r = client.post("/add", json={"dl": DL})
    assert r.status_code == 400
    assert net.requests == []


def test_add_qb_url_failure_does_not_fall_back_to_cookie_fetch(net, client):
    def qb(request):
        if request.url.path == "/api/v2/torrents/add":
            return httpx.Response(200, text="Fails.")
        return net.default_qb(request)
    net.qb_handler = qb
    r = client.post("/add", json={"id": "123", "dl": DL})
    assert r.status_code == 424
    assert net.mam_requests == []
    assert DL not in r.text


def test_add_fetch_auth_failure_fails_closed(net, client):
    net.mam_handler = lambda r: httpx.Response(302, headers={"location": "/login.php"})
    r = client.post("/add", json={"id": "789"})
    assert r.status_code == 424
    assert r.json()["error"] == "MamAuthError"
    assert len(net.mam_requests) == 1
    assert qb_adds(net) == []


def test_add_writes_history(net, client):
    client.post("/add", json={"id": "321", "title": "Hist", "dl": DL, "author": "A"})
    with db.engine.begin() as cx:
        row = cx.execute(text("SELECT mam_id, title, qb_hash FROM history WHERE mam_id='321'")).mappings().one()
    assert row["title"] == "Hist" and row["qb_hash"] == "abc123"


def test_settings_ignore_custom_mam_base(monkeypatch):
    monkeypatch.setenv("MAM_BASE", "https://evil.example")
    main.settings.reload()
    assert not hasattr(main.settings, "MAM_BASE")
    assert mam.MAM_BASE == "https://www.myanonamouse.net"


def test_home_and_setup_pages_render(client):
    assert client.get("/").status_code == 200
    assert client.get("/setup").status_code == 200


import pytest

@pytest.mark.parametrize("reply,ok", [
    (httpx.Response(200, text="Ok."), True),
    (httpx.Response(200, text="Fails."), False),
    (httpx.Response(200, json={"success_count": 1, "failure_count": 0, "pending_count": 0}), True),
    (httpx.Response(200, json={"success_count": 0, "failure_count": 0, "pending_count": 1}), True),
    (httpx.Response(200, json={"success_count": 0, "failure_count": 1, "pending_count": 0}), False),
    (httpx.Response(415, text="Torrent file is not valid"), False),
])
def test_qb_add_reply_parsing(reply, ok):
    assert qb.add_ok(reply) is ok


def test_add_succeeds_with_newer_qb_json_reply(net, client):
    def qb(request):
        if request.url.path == "/api/v2/torrents/add":
            return httpx.Response(200, json={"success_count": 0, "failure_count": 0, "pending_count": 1})
        return net.default_qb(request)
    net.qb_handler = qb
    r = client.post("/add", json={"id": "123", "dl": DL})
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("reply,ok", [
    (httpx.Response(200, text="Ok."), True),
    (httpx.Response(204), True),
    (httpx.Response(200, text="Fails."), False),
    (httpx.Response(403, text="Forbidden"), False),
    (httpx.Response(401), False),
])
def test_qb_login_reply_parsing(reply, ok):
    assert qb.login_ok(reply) is ok


def test_add_works_when_qb_login_returns_204(net, client):
    def qb(request):
        if request.url.path == "/api/v2/auth/login":
            return httpx.Response(204)
        return net.default_qb(request)
    net.qb_handler = qb
    r = client.post("/add", json={"id": "123", "dl": DL})
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("dl", [DL, ""])
def test_add_duplicate_returns_409_and_no_history(net, client, dl):
    net.mam_handler = lambda r: httpx.Response(200, content=b"d4:infod4:name1:xee",
                                               headers={"content-type": "application/x-bittorrent"})
    def qb(request):
        if request.url.path == "/api/v2/torrents/add":
            return httpx.Response(409, text="Conflict")
        return net.default_qb(request)
    net.qb_handler = qb
    r = client.post("/add", json={"id": "555", "title": "Dup", "dl": dl})
    assert r.status_code == 409
    assert r.json()["detail"] == "Already in qBittorrent"
    with db.engine.begin() as cx:
        assert cx.execute(text("SELECT COUNT(*) FROM history WHERE mam_id='555'")).scalar() == 0


def test_static_assets_are_versioned(client):
    html = client.get("/setup").text
    assert f"/static/setup.js?v={main._asset_version()}" in html



def test_add_with_real_format_dl_hands_qb_single_tid(net, client):
    h = "AAAAaaaa0000_-bbbb="
    r = client.post("/add", json={"id": "882573", "title": "Saving Supervillains", "dl": f"{h}?tid=882573"})
    assert r.status_code == 200, r.text
    assert net.mam_requests == []
    (add,) = qb_adds(net)
    assert form_of(add)["urls"] == f"https://www.myanonamouse.net/tor/download.php/{h}?tid=882573"
