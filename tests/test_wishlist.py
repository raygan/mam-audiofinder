"""Phase 2 step 1: wishlist items, manual checks, match rules, daily cap."""
import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import text

import db
import main
import mam
import wishlist
from conftest import FAKE_TOKEN

COOKIE = f"mam_id={FAKE_TOKEN}"
EMPTY = {"error": "Nothing returned, out of 0"}


@pytest.fixture(autouse=True)
def clean_wishlist(monkeypatch):
    with db.engine.begin() as cx:
        for t in ("wishlist", "wishlist_seen", "mam_request_log", "app_state"):
            cx.execute(text(f"DELETE FROM {t}"))
    monkeypatch.setattr(main.settings, "WISHLIST_MAX_REQUESTS_PER_DAY", 20)
    monkeypatch.setattr(main.settings, "WISHLIST_INTERVAL_HOURS", 72)
    yield


def tor(id_, title="Wanted Book", main_cat=14, filetype="epub", seeders=10, snatched=0, lang="ENG",
        series='{"5":["Wanted","1",1.0]}'):
    return {"id": id_, "title": title, "main_cat": main_cat, "filetype": filetype, "seeders": seeders,
            "leechers": 0, "my_snatched": snatched, "lang_code": lang, "author_info": '{"1":"Ann Author"}',
            "narrator_info": "{}", "series_info": series, "size": "1 MiB", "added": "2026-11-23 10:00:00",
            "dl": f"AAAAaaaa0000{id_}=?tid={id_}"}


def mam_returns(net, *items):
    """Each MAM request gets the next reply; records request bodies."""
    replies = list(items)
    bodies = []
    def h(r):
        bodies.append(json.loads(r.read()))
        data = replies.pop(0) if replies else []
        return httpx.Response(200, json={"data": data, "total": len(data), "found": len(data)} if data else EMPTY)
    net.mam_handler = h
    return bodies


def check(item_id, now=None):
    return asyncio.run(wishlist.check(item_id, COOKIE, now=now))


# ---------------- create ----------------
def test_create_makes_no_mam_request_and_records_baseline(net, client):
    r = client.post("/wishlist", json={"query": "wanted book", "media": "ebook", "seen": ["900001", 900002, "x"]})
    assert r.status_code == 200, r.text
    item = r.json()
    assert item["status"] == "active" and item["mode"] == "notify"
    assert item["srch_in"] == ["title", "author", "series"]  # ebook default
    assert item["next_check_at"] > item["created_at"]
    assert net.requests == []
    with db.engine.begin() as cx:
        seen = {r[0] for r in cx.execute(text("SELECT mam_id FROM wishlist_seen WHERE is_match = 0"))}
    assert seen == {"900001", "900002"}


@pytest.mark.parametrize("body", [
    {"query": ""},
    {"query": "x", "media": "music"},
    {"query": "x", "mode": "grab"},
    {"query": "x", "srch_in": ["title", "comments"]},
    {"query": "x", "sort_type": "evil"},
    {"query": "x", "filters": {"colour": "red"}},
    {"query": "x", "filters": {"min_seeders": -1}},
    {"query": "x", "check_interval_hours": 0},
])
def test_create_validation(net, client, body):
    assert client.post("/wishlist", json=body).status_code in (400, 422)
    assert client.get("/wishlist").json()["items"] == []


# ---------------- the check request ----------------
def test_check_sends_one_documented_search(net, client):
    item = wishlist.create("wanted book", media="ebook")
    bodies = mam_returns(net, [])
    r = client.post(f"/wishlist/{item['id']}/check")
    assert r.status_code == 200, r.text
    (body,) = bodies
    assert body["tor"]["text"] == "wanted book"
    assert body["tor"]["main_cat"] == ["14"]
    assert body["tor"]["searchType"] == "active"
    assert body["tor"]["startDate"] == item["created_at"][:10]
    assert body["perpage"] == wishlist.CHECK_PERPAGE
    assert "fl" not in json.dumps(body["tor"]).replace('"fl-VIP"', "")


# ---------------- ROADMAP acceptance: one match, then none ----------------
def test_empty_item_later_gets_exactly_one_match_then_none(net):
    item = wishlist.create("wanted book", media="ebook")
    mam_returns(net, [], [tor(900101)], [tor(900101)])
    assert check(item["id"])["new_matches"] == []
    second = check(item["id"])
    assert [m["id"] for m in second["new_matches"]] == ["900101"]
    assert second["item"]["status"] == "matched" and second["item"]["match_count"] == 1
    assert check(item["id"])["new_matches"] == []
    assert len(wishlist.matches(item["id"])) == 1


def test_baseline_results_never_match(net):
    item = wishlist.create("wanted book", media="ebook", seen=["900201"])
    mam_returns(net, [tor(900201), tor(900202)])
    assert [m["id"] for m in check(item["id"])["new_matches"]] == ["900202"]


# ---------------- ROADMAP acceptance: history never matches ----------------
def test_result_already_in_history_never_matches(net):
    db.record_history("900301", "Already got it", "", "", "", None, "ebook")
    item = wishlist.create("wanted book", media="ebook")
    mam_returns(net, [tor(900301)], [tor(900301)])
    assert check(item["id"])["new_matches"] == []
    assert check(item["id"])["new_matches"] == []


def test_my_snatched_never_matches(net):
    item = wishlist.create("wanted book", media="ebook")
    mam_returns(net, [tor(900401, snatched=1), tor(900402, snatched="0")])
    assert [m["id"] for m in check(item["id"])["new_matches"]] == ["900402"]


def test_wrong_media_type_never_matches(net):
    item = wishlist.create("wanted book", media="ebook")
    mam_returns(net, [tor(900501, main_cat=13, filetype="m4b")])
    assert check(item["id"])["new_matches"] == []


# ---------------- filters ----------------
@pytest.mark.parametrize("filters,result,ok", [
    ({"formats": ["epub"]}, dict(filetype="epub"), True),
    ({"formats": ["epub"]}, dict(filetype="pdf"), False),
    ({"formats": [".EPUB", "pdf"]}, dict(filetype="pdf"), True),
    ({"min_seeders": 5}, dict(seeders=4), False),
    ({"min_seeders": 5}, dict(seeders=5), True),
    ({"exclude": ["Abridged"]}, dict(title="Wanted Book (Abridged)"), False),
    ({"exclude": ["abridged"]}, dict(title="Wanted Book"), True),
    ({"lang_code": "eng"}, dict(lang="ENG"), True),
    ({"lang_code": "ENG"}, dict(lang="GER"), False),
])
def test_filters(net, filters, result, ok):
    item = wishlist.create("wanted book", media="ebook", filters=filters)
    mam_returns(net, [tor(900601, **result)])
    assert bool(check(item["id"])["new_matches"]) is ok


def test_filtered_out_results_stay_filtered_after_filter_change(net):
    # A result rejected once is "seen"; loosening filters later doesn't resurrect it.
    item = wishlist.create("wanted book", media="ebook", filters={"formats": ["epub"]})
    mam_returns(net, [tor(900701, filetype="pdf")], [tor(900701, filetype="pdf")])
    check(item["id"])
    wishlist.update(item["id"], {"filters": {}})
    assert check(item["id"])["new_matches"] == []


# ---------------- both / fulfilment ----------------
def test_both_item_is_done_only_when_both_media_are_fulfilled(net, client):
    item = wishlist.create("wanted book", media="both")
    bodies = mam_returns(net, [tor(900801, main_cat=13, filetype="m4b"), tor(900802)], [tor(900803)])
    res = check(item["id"])
    assert {m["media_type"] for m in res["new_matches"]} == {"audiobook", "ebook"}
    assert bodies[0]["tor"]["main_cat"] == ["13", "14"]

    after_audio = wishlist.mark_added(item["id"], "900801", "audiobook")
    assert after_audio["status"] == "matched" and after_audio["fulfilled"] == ["audiobook"]
    # Next check only searches the media still wanted.
    check(item["id"])
    assert bodies[1]["tor"]["main_cat"] == ["14"]
    done = wishlist.mark_added(item["id"], "900802", "ebook")
    assert done["status"] == "done"
    r = client.post(f"/wishlist/{item['id']}/check")
    assert r.status_code == 409
    assert len(bodies) == 2  # done items aren't searched


def test_add_with_wishlist_id_marks_item(net, client):
    item = wishlist.create("wanted book", media="ebook")
    r = client.post("/add", json={"id": "900901", "dl": "AAAAaaaa0000_-bb=?tid=900901", "media_type": "ebook",
                                  "wishlist_id": item["id"]})
    assert r.status_code == 200, r.text
    assert wishlist.get(item["id"])["status"] == "done"


def test_add_still_succeeds_if_wishlist_item_is_gone(net, client):
    r = client.post("/add", json={"id": "900902", "dl": "AAAAaaaa0000_-bb=?tid=900902", "media_type": "ebook",
                                  "wishlist_id": 999999})
    assert r.status_code == 200


# ---------------- daily cap ----------------
def test_daily_cap_refuses_before_sending(net, client, monkeypatch):
    monkeypatch.setattr(main.settings, "WISHLIST_MAX_REQUESTS_PER_DAY", 2)
    item = wishlist.create("wanted book", media="ebook")
    bodies = mam_returns(net, [], [], [])
    assert client.post(f"/wishlist/{item['id']}/check").status_code == 200
    assert client.post(f"/wishlist/{item['id']}/check").status_code == 200
    r = client.post(f"/wishlist/{item['id']}/check")
    assert r.status_code == 429 and "limit" in r.json()["detail"]
    assert len(bodies) == 2


def test_daily_cap_is_a_rolling_24_hours(net):
    item = wishlist.create("wanted book", media="ebook")
    mam_returns(net, [], [])
    t0 = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
    check(item["id"], now=t0)
    assert wishlist.requests_last_24h(t0 + timedelta(hours=23)) == 1
    assert wishlist.requests_last_24h(t0 + timedelta(hours=25)) == 0


def test_failed_requests_count_toward_the_cap(net):
    item = wishlist.create("wanted book", media="ebook")
    net.mam_handler = lambda r: httpx.Response(403)
    with pytest.raises(mam.MamAuthError):
        check(item["id"])
    assert wishlist.requests_last_24h() == 1


# ---------------- errors ----------------
def test_mam_error_is_recorded_and_no_retry(net, client):
    item = wishlist.create("wanted book", media="ebook")
    net.mam_handler = lambda r: httpx.Response(302, headers={"location": "/login.php"})
    r = client.post(f"/wishlist/{item['id']}/check")
    assert r.status_code == 424 and r.json()["error"] == "MamAuthError"
    assert len(net.mam_requests) == 1
    got = wishlist.get(item["id"])
    assert "cookie" in got["last_error"].lower() and FAKE_TOKEN not in got["last_error"]
    assert got["status"] == "active"


def test_next_check_has_jitter_around_the_interval(net):
    item = wishlist.create("wanted book", media="ebook")
    mam_returns(net, [])
    t0 = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
    nxt = datetime.strptime(check(item["id"], now=t0)["item"]["next_check_at"], wishlist.TIME_FMT).replace(tzinfo=timezone.utc)
    assert timedelta(hours=72 * 0.9) <= nxt - t0 <= timedelta(hours=72 * 1.1)


# ---------------- API ----------------
def test_list_patch_dismiss_delete(net, client):
    item = wishlist.create("wanted book", media="ebook", label="Book 1")
    mam_returns(net, [tor(901001), tor(901002)])
    check(item["id"])
    listed = client.get("/wishlist").json()
    assert listed["items"][0]["match_count"] == 2 and listed["requests_last_24h"] == 1

    assert client.post(f"/wishlist/{item['id']}/matches/901001/dismiss").status_code == 200
    assert [m["mam_id"] for m in client.get(f"/wishlist/{item['id']}/matches").json()["matches"]] == ["901002"]
    assert client.post(f"/wishlist/{item['id']}/matches/999/dismiss").status_code == 404

    r = client.patch(f"/wishlist/{item['id']}", json={"status": "paused", "label": "Renamed", "mode": "auto"})
    assert r.status_code == 200 and (r.json()["status"], r.json()["label"], r.json()["mode"]) == ("paused", "Renamed", "auto")
    assert client.patch(f"/wishlist/{item['id']}", json={"status": "matched"}).status_code == 400
    assert client.patch(f"/wishlist/{item['id']}", json={"media": "audiobook"}).status_code == 400

    assert client.delete(f"/wishlist/{item['id']}").status_code == 200
    assert client.get(f"/wishlist/{item['id']}/matches").status_code == 404
    with db.engine.begin() as cx:
        assert cx.execute(text("SELECT COUNT(*) FROM wishlist_seen")).scalar() == 0


def test_matches_store_dl_for_adding_later(net):
    item = wishlist.create("wanted book", media="ebook")
    mam_returns(net, [tor(901101)])
    check(item["id"])
    (m,) = wishlist.matches(item["id"])
    assert m["result"]["dl"] == "AAAAaaaa0000901101=?tid=901101"


def test_missing_item_is_404(net, client):
    assert client.post("/wishlist/424242/check").status_code == 404
    assert net.requests == []


def test_migration_4_creates_tables(tmp_path):
    from sqlalchemy import create_engine
    eng = create_engine(f"sqlite:///{tmp_path / 'h.db'}", future=True)
    assert db.migrate(eng) >= 4
    with eng.begin() as cx:
        names = {r[0] for r in cx.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert {"wishlist", "wishlist_seen", "app_state", "mam_request_log"} <= names


# ---------------- step 2: pages ----------------
def test_wishlist_page_and_assets(net, client):
    page = client.get("/wishlist/view")
    assert page.status_code == 200 and "Wishlist" in page.text
    assert "/static/common.js?v=" in page.text and "/static/wishlist.js?v=" in page.text
    assert client.get("/static/wishlist.js").status_code == 200
    home = client.get("/").text
    assert 'href="/wishlist/view"' in home and 'id="resultsFooter"' in home
    assert 'id="saveWishBtn"' not in home  # no always-visible save button
    assert home.index("/static/common.js") < home.index("/static/app.js")  # helpers load first
    assert net.requests == []


def test_summary_counts_unreviewed_and_never_calls_mam(net, client):
    item = wishlist.create("wanted book", media="ebook")
    mam_returns(net, [tor(902001), tor(902002)])
    check(item["id"])
    before = len(net.mam_requests)
    s = client.get("/wishlist/summary").json()
    assert s == {"unreviewed": 2, "items": 1, "scheduler": "disabled"}
    wishlist.dismiss(item["id"], "902001")
    assert client.get("/wishlist/summary").json()["unreviewed"] == 1
    assert len(net.mam_requests) == before
