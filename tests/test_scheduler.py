"""Phase 2 step 4: the opt-in wishlist scheduler (ROADMAP rule 7).

Time is faked: run_once() takes a clock and a sleep function, so the 30-90 s
gaps and the 24 h cap are checked without waiting.
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import text

import db
import main
import mam
import scheduler
import wishlist
from conftest import FAKE_TOKEN
from test_wishlist import mam_returns, tor

COOKIE = f"mam_id={FAKE_TOKEN}"
T0 = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clean(monkeypatch, net):
    # Notifications are on in these tests; accept them quietly unless a test inspects them.
    net.hosts["ntfy.test"] = lambda r: httpx.Response(200, json={})
    with db.engine.begin() as cx:
        for t in ("wishlist", "wishlist_seen", "mam_request_log", "app_state"):
            cx.execute(text(f"DELETE FROM {t}"))
    s = main.settings
    for k, v in {"WISHLIST_SCHEDULER_ENABLED": False, "WISHLIST_MAX_REQUESTS_PER_DAY": 20,
                 "WISHLIST_INTERVAL_HOURS": 72, "WISHLIST_DELAY_MIN_SECONDS": 30,
                 "WISHLIST_DELAY_MAX_SECONDS": 90, "NOTIFY_WEBHOOK_URL": "https://ntfy.test/books",
                 "NOTIFY_FORMAT": "ntfy", "NOTIFY_TOKEN": "", "NOTIFY_CLICK_URL": ""}.items():
        monkeypatch.setattr(s, k, v)
    yield
    scheduler._task = None


@pytest.fixture
def inbox(net):
    got = []
    def h(r):
        got.append(json.loads(r.read()))
        return httpx.Response(200, json={})
    net.hosts["ntfy.test"] = h
    return got


class Clock:
    """Fake clock; sleep() advances it and records each gap."""
    def __init__(self, start=T0):
        self.now = start
        self.sleeps = []

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += timedelta(seconds=seconds)


def due_item(query="wanted book", media="ebook", mode="notify", next_check=T0 - timedelta(minutes=1), **kw):
    item = wishlist.create(query, media=media, mode=mode, **kw)
    with db.engine.begin() as cx:
        cx.execute(text("UPDATE wishlist SET next_check_at = :n, created_at = :c WHERE id = :id"),
                   {"n": wishlist._fmt(next_check), "c": wishlist._fmt(T0 - timedelta(days=3)), "id": item["id"]})
    return wishlist.get(item["id"])


def run(clock, rand=None):
    kw = {"now_fn": clock, "sleep": clock.sleep}
    if rand:
        kw["rand"] = rand
    return asyncio.run(scheduler.run_once(COOKIE, **kw))


# ---------------- ROADMAP: disabled means no MAM traffic without a user action ----------------
def test_disabled_scheduler_never_starts_and_sends_nothing(net, client, inbox):
    due_item(), due_item("another")
    assert scheduler._task is None  # the lifespan didn't start it
    assert scheduler.start() is None
    assert client.get("/scheduler/status").json()["state"] == "disabled"
    client.get("/wishlist")
    client.get("/wishlist/summary")
    assert net.mam_requests == [] and inbox == []


def test_disabled_scheduler_doesnt_record_halts(net, client):
    item = due_item()
    net.mam_handler = lambda r: httpx.Response(403)
    client.post(f"/wishlist/{item['id']}/check")
    assert scheduler.halted() is None


# ---------------- one at a time, with gaps ----------------
def test_due_items_are_checked_one_at_a_time_with_30_to_90s_gaps(net, inbox):
    a = due_item("first", next_check=T0 - timedelta(hours=2))
    b = due_item("second", next_check=T0 - timedelta(hours=1))
    c = due_item("third", next_check=T0 - timedelta(minutes=5))
    bodies = mam_returns(net, [], [], [])
    clock = Clock()
    assert run(clock) == 3
    assert [x["tor"]["text"] for x in bodies] == ["first", "second", "third"]  # oldest due first
    assert len(clock.sleeps) == 2 and all(30 <= s <= 90 for s in clock.sleeps)
    for item in (a, b, c):
        nxt = wishlist.get(item["id"])["next_check_at"]
        assert nxt > wishlist._fmt(T0 + timedelta(hours=60))  # rescheduled ~72 h out


def test_delay_never_below_30_seconds(monkeypatch):
    monkeypatch.setattr(main.settings, "WISHLIST_DELAY_MIN_SECONDS", 1)
    monkeypatch.setattr(main.settings, "WISHLIST_DELAY_MAX_SECONDS", 5)
    assert scheduler.delay_bounds() == (30, 30)


def test_not_due_paused_and_done_items_are_skipped(net):
    due_item("later", next_check=T0 + timedelta(hours=1))
    p = due_item("paused")
    wishlist.update(p["id"], {"status": "paused"})
    d = due_item("done")
    wishlist.update(d["id"], {"status": "done"})
    m = due_item("matched still wanted")
    with db.engine.begin() as cx:
        cx.execute(text("UPDATE wishlist SET status='matched' WHERE id=:i"), {"i": m["id"]})
    bodies = mam_returns(net, [])
    assert run(Clock()) == 1
    assert bodies[0]["tor"]["text"] == "matched still wanted"


def test_single_in_flight_across_scheduler_and_manual_checks(net, monkeypatch):
    for i in range(3):
        due_item(f"item {i}")
    manual = due_item("manual", next_check=T0 + timedelta(days=1))
    live = {"now": 0, "max": 0}

    async def slow(request):
        live["now"] += 1
        live["max"] = max(live["max"], live["now"])
        await asyncio.sleep(0.02)
        live["now"] -= 1
        return httpx.Response(200, json={"error": "Nothing returned, out of 0"})
    monkeypatch.setattr(mam, "transport", httpx.MockTransport(slow))

    async def both():
        clock = Clock()
        async def tiny_sleep(s):
            clock.sleeps.append(s)
            await asyncio.sleep(0)
        await asyncio.gather(
            scheduler.run_once(COOKIE, now_fn=clock, sleep=tiny_sleep),
            wishlist.check(manual["id"], COOKIE, now=T0),
            wishlist.check(manual["id"], COOKIE, now=T0),
        )
    asyncio.run(both())
    assert live["max"] == 1


# ---------------- daily cap ----------------
def test_daily_cap_stops_the_run_without_halting(net, monkeypatch):
    monkeypatch.setattr(main.settings, "WISHLIST_MAX_REQUESTS_PER_DAY", 2)
    for i in range(3):
        due_item(f"item {i}")
    bodies = mam_returns(net, [], [], [])
    clock = Clock()
    assert run(clock) == 2
    assert len(bodies) == 2 and scheduler.halted() is None
    assert run(clock) == 0  # still within the same 24 h
    clock.now += timedelta(hours=25)
    with db.engine.begin() as cx:  # make the third item still due after the jump
        cx.execute(text("UPDATE wishlist SET next_check_at = :n WHERE query = 'item 2'"), {"n": wishlist._fmt(T0)})
    assert run(clock) == 1


def test_manual_checks_count_toward_the_same_cap(net, monkeypatch):
    monkeypatch.setattr(main.settings, "WISHLIST_MAX_REQUESTS_PER_DAY", 1)
    m = due_item("manual", next_check=T0 + timedelta(days=1))
    due_item("scheduled")
    mam_returns(net, [], [])
    asyncio.run(wishlist.check(m["id"], COOKIE, now=T0))
    assert run(Clock()) == 0


# ---------------- ROADMAP: halt on error, notify once ----------------
@pytest.mark.parametrize("reply,err", [
    (httpx.Response(403), "MamAuthError"),
    (httpx.Response(302, headers={"location": "/login.php"}), "MamAuthError"),
    (httpx.Response(429), "MamRateLimitError"),
    (httpx.Response(200, text="<html>"), "MamUnexpectedResponse"),
])
def test_error_halts_everything_and_notifies_once(net, inbox, reply, err):
    due_item("first", next_check=T0 - timedelta(hours=2))
    due_item("second", next_check=T0 - timedelta(hours=1))
    net.mam_handler = lambda r: reply
    clock = Clock()
    assert run(clock) == 1  # the failing request, then nothing
    assert len(net.mam_requests) == 1
    h = scheduler.halted()
    assert h and h["reason"].startswith(err) and FAKE_TOKEN not in h["reason"]
    assert [m["tags"] for m in inbox] == [["warning"]]
    assert "Resume" in inbox[0]["message"]

    # Still halted on later runs (and after a "restart": the state is in the DB).
    clock.now += timedelta(days=5)
    assert run(clock) == 0
    assert len(net.mam_requests) == 1 and len(inbox) == 1


def test_resume_is_needed_and_then_checks_continue(net, client, inbox, monkeypatch):
    monkeypatch.setattr(main.settings, "WISHLIST_SCHEDULER_ENABLED", True)
    due_item()
    net.mam_handler = lambda r: httpx.Response(403)
    run(Clock())
    assert client.get("/scheduler/status").json()["state"] == "halted"
    assert client.get("/wishlist/summary").json()["scheduler"] == "halted"
    mam_returns(net, [])
    assert client.post("/scheduler/resume").json()["halted"] is None
    clock = Clock()
    clock.now += timedelta(days=4)
    assert run(clock) == 1


def test_halt_notifies_only_on_the_first_call(inbox):
    assert asyncio.run(scheduler.halt("one")) is True
    assert asyncio.run(scheduler.halt("two")) is False
    assert len(inbox) == 1 and scheduler.halted()["reason"] == "one"


def test_manual_check_error_halts_when_enabled(net, client, inbox, monkeypatch):
    monkeypatch.setattr(main.settings, "WISHLIST_SCHEDULER_ENABLED", True)
    item = due_item()
    net.mam_handler = lambda r: httpx.Response(302, headers={"location": "/login.php"})
    assert client.post(f"/wishlist/{item['id']}/check").status_code == 424
    assert scheduler.halted()["reason"].startswith("MamAuthError")
    assert len(inbox) == 1


def test_search_cookie_error_halts_but_other_search_errors_dont(net, client, monkeypatch):
    monkeypatch.setattr(main.settings, "WISHLIST_SCHEDULER_ENABLED", True)
    net.mam_handler = lambda r: httpx.Response(500)
    client.post("/search", json={"tor": {"text": "x"}})
    assert scheduler.halted() is None
    net.mam_handler = lambda r: httpx.Response(403)
    client.post("/search", json={"tor": {"text": "x"}})
    assert scheduler.halted() is not None


def test_internal_error_in_loop_halts(net, monkeypatch):
    monkeypatch.setattr(main.settings, "WISHLIST_SCHEDULER_ENABLED", True)

    async def broken(*a, **kw):
        raise RuntimeError("bug")
    monkeypatch.setattr(scheduler, "run_once", broken)
    calls = []

    async def stop_after_one(s):
        calls.append(s)
        raise asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scheduler.loop(sleep=stop_after_one))
    assert scheduler.halted()["reason"].startswith("The scheduler hit an internal error")
    assert 30 <= calls[0] <= 90


def test_no_cookie_means_no_requests(net):
    due_item()
    assert asyncio.run(scheduler.run_once("", now_fn=Clock(), sleep=Clock().sleep)) == 0
    assert net.requests == []


# ---------------- auto mode ----------------
def test_auto_mode_adds_the_best_match(net, inbox):
    item = due_item(mode="auto")
    mam_returns(net, [tor(904001, filetype="pdf", seeders=50), tor(904002, filetype="epub", seeders=5),
                      tor(904003, filetype="epub", seeders=20)])
    run(Clock())
    adds = [r for r in net.qb_requests if r.url.path == "/api/v2/torrents/add"]
    assert len(adds) == 1 and "tid%3D904003" in adds[0].read().decode()
    got = wishlist.get(item["id"])
    assert got["status"] == "done" and got["fulfilled"] == ["ebook"]
    with db.engine.begin() as cx:
        assert cx.execute(text("SELECT media_type FROM history WHERE mam_id='904003'")).scalar() == "ebook"
    assert [m["tags"] for m in inbox] == [["books"], ["inbox_tray"]]  # match, then auto-grab


def test_auto_mode_both_adds_one_per_media(net):
    item = due_item(media="both", mode="auto")
    mam_returns(net, [tor(904101, main_cat=13, filetype="mp3", seeders=90),
                      tor(904102, main_cat=13, filetype="m4b", seeders=3), tor(904103)])
    run(Clock())
    adds = [r.read().decode() for r in net.qb_requests if r.url.path == "/api/v2/torrents/add"]
    assert len(adds) == 2 and any("904102" in a for a in adds) and any("904103" in a for a in adds)
    assert wishlist.get(item["id"])["status"] == "done"


def test_auto_mode_qb_failure_leaves_the_match(net):
    item = due_item(mode="auto")
    def qb(request):
        if request.url.path == "/api/v2/torrents/add":
            return httpx.Response(200, text="Fails.")
        return net.default_qb(request)
    net.qb_handler = qb
    mam_returns(net, [tor(904201)])
    run(Clock())
    got = wishlist.get(item["id"])
    assert got["status"] == "matched" and got["match_count"] == 1


def test_manual_check_never_auto_grabs(net, client):
    item = due_item(mode="auto")
    mam_returns(net, [tor(904301)])
    client.post(f"/wishlist/{item['id']}/check")
    assert not [r for r in net.qb_requests if r.url.path == "/api/v2/torrents/add"]
