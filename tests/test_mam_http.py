"""Honest headers, cookie handling, fail-closed responses, normalisation and
log redaction for mam.py."""
import asyncio, io, logging

import httpx
import pytest

import mam
from conftest import FAKE_TOKEN, load_fixture

COOKIE = f"mam_id={FAKE_TOKEN}"


def run(coro):
    return asyncio.run(coro)


# ---------------- headers ----------------
def test_search_sends_honest_headers_and_only_mam_id(net):
    net.mam_handler = lambda r: httpx.Response(200, json=load_fixture("synthetic_search.json"))
    run(mam.search(COOKIE, text="dune"))
    (req,) = net.mam_requests
    assert req.headers["user-agent"] == f"mam-audiofinder/{mam.APP_VERSION}"
    assert "origin" not in req.headers
    assert "referer" not in req.headers
    assert req.headers["cookie"] == COOKIE
    assert str(req.url) == f"{mam.MAM_BASE}/tor/js/loadSearchJSONbasic.php?dlLink=1"


def test_fetch_torrent_sends_honest_headers(net):
    net.mam_handler = lambda r: httpx.Response(200, content=b"d8:announce0:e",
                                               headers={"content-type": "application/x-bittorrent"})
    assert run(mam.fetch_torrent(COOKIE, "42")) == b"d8:announce0:e"
    (req,) = net.mam_requests
    assert str(req.url) == f"{mam.MAM_BASE}/tor/download.php?tid=42"
    assert req.headers["user-agent"].startswith("mam-audiofinder/")
    assert "origin" not in req.headers and "referer" not in req.headers


@pytest.mark.parametrize("raw,expected", [
    ("abc123token", "mam_id=abc123token"),
    ("mam_id=abc123token", "mam_id=abc123token"),
    ("  mam_id=abc123token ; other=1 ", "mam_id=abc123token"),
    ("foo=bar; mam_id=abc123token; uid=5", "mam_id=abc123token"),
    ("mam_session=xyz", ""),
    ("foo=bar", ""),
    ("", ""),
    (None, ""),
    ("bad token with spaces", ""),
    ("mam_id=abc\r\nX-Evil: 1", ""),
])
def test_build_cookie_keeps_only_mam_id(raw, expected):
    assert mam.build_cookie(raw) == expected


def test_no_cookie_means_no_request(net):
    with pytest.raises(mam.MamAuthError):
        run(mam.search("", text="x"))
    assert net.requests == []


# ---------------- fail closed ----------------
@pytest.mark.parametrize("response,err", [
    (httpx.Response(302, headers={"location": "/login.php"}), mam.MamAuthError),
    (httpx.Response(301, headers={"location": "https://www.myanonamouse.net/"}), mam.MamAuthError),
    (httpx.Response(401), mam.MamAuthError),
    (httpx.Response(403), mam.MamAuthError),
    (httpx.Response(429), mam.MamRateLimitError),
    (httpx.Response(503), mam.MamRateLimitError),
    (httpx.Response(500), mam.MamUnexpectedResponse),
    (httpx.Response(404), mam.MamUnexpectedResponse),
    (httpx.Response(200, text="<html>login</html>", headers={"content-type": "text/html"}), mam.MamUnexpectedResponse),
    (httpx.Response(200, json={"error": "something went wrong"}), mam.MamUnexpectedResponse),
    (httpx.Response(200, json=["not", "a", "dict"]), mam.MamUnexpectedResponse),
    (httpx.Response(200, json={"data": "nope"}), mam.MamUnexpectedResponse),
])
def test_search_fails_closed_with_one_request(net, response, err):
    net.mam_handler = lambda r: response
    with pytest.raises(err):
        run(mam.search(COOKIE, text="x"))
    assert len(net.mam_requests) == 1  # no retries, no fallback endpoints


def test_redirect_is_not_followed(net):
    net.mam_handler = lambda r: httpx.Response(302, headers={"location": "https://evil.example/steal"})
    with pytest.raises(mam.MamAuthError):
        run(mam.search(COOKIE, text="x"))
    assert [r.url.host for r in net.requests] == [mam.MAM_HOST]


def test_network_error_is_unexpected_and_redacted(net):
    def boom(r):
        raise httpx.ConnectError(f"failed {COOKIE}")
    net.mam_handler = boom
    with pytest.raises(mam.MamUnexpectedResponse) as ei:
        run(mam.search(COOKIE, text="x"))
    assert FAKE_TOKEN not in str(ei.value)
    assert len(net.mam_requests) == 1


@pytest.mark.parametrize("response", [
    httpx.Response(200, text="<html>no</html>", headers={"content-type": "text/html"}),
    httpx.Response(200, content=b"", headers={"content-type": "application/x-bittorrent"}),
    httpx.Response(200, content=b"<!doctype html>", headers={"content-type": "application/octet-stream"}),
])
def test_fetch_torrent_rejects_non_torrent(net, response):
    net.mam_handler = lambda r: response
    with pytest.raises(mam.MamUnexpectedResponse):
        run(mam.fetch_torrent(COOKIE, "42"))
    assert len(net.mam_requests) == 1


def test_error_messages_never_echo_body(net):
    net.mam_handler = lambda r: httpx.Response(500, text="SECRET-BODY-CONTENT")
    with pytest.raises(mam.MamUnexpectedResponse) as ei:
        run(mam.search(COOKIE, text="x"))
    assert "SECRET-BODY-CONTENT" not in str(ei.value)


# ---------------- normalisation ----------------
def test_normalize_handles_documented_quirks(net):
    net.mam_handler = lambda r: httpx.Response(200, json=load_fixture("synthetic_search.json"))
    out = run(mam.search(COOKIE, text="x"))
    a, b = out["results"]
    assert out["total"] == 2 and out["total_found"] == 2
    assert a["id"] == "100001" and a["title"] == "Example Audiobook Title"
    assert a["author_info"] == "Ann Author"
    assert a["narrator_info"] == "Ned Narrator, Nia Narrator"
    assert a["format"] == "M4B"                   # from documented filetypes
    assert a["seeders"] == 12 and a["leechers"] == 0  # strings coerced
    assert b["title"] == "Second Title Uses Name Key"  # name instead of title
    assert b["format"] == "MP3"                   # filetype instead of filetypes
    assert b["narrator_info"] == ""


def test_normalize_falls_back_to_title_parsing():
    assert mam.normalize_result({"id": 1, "title": "Book [M4B] mp3"})["format"] == "M4B/MP3"


def test_search_request_body_is_built_not_passed_through(net):
    seen = {}
    def h(r):
        seen["body"] = r.read()
        return httpx.Response(200, json={"data": [], "total": "0", "total_found": "0"})
    net.mam_handler = h
    run(mam.search(COOKIE, text="dune", sort_type="seedersDesc", perpage=999))
    import json
    body = json.loads(seen["body"])
    assert body["perpage"] == 100  # clamped
    assert body["tor"]["main_cat"] == ["13"]
    assert set(body) == {"tor", "perpage"}


# ---------------- redaction ----------------
def test_redact_masks_cookie_and_dl_hashes():
    mam.register_secret(FAKE_TOKEN)
    s = (f"Cookie: {COOKIE} url={mam.MAM_BASE}/tor/download.php/FAKEdlHASHaaaaaaaa?tid=1 "
         f'json={{"dl": "FAKEdlHASHbbbbbbbb"}} raw {FAKE_TOKEN}')
    out = mam.redact(s)
    assert FAKE_TOKEN not in out
    assert "FAKEdlHASH" not in out
    assert "tid=1" in out


def test_log_records_are_redacted():
    mam.register_secret(FAKE_TOKEN)
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.addFilter(mam.RedactingFilter())
    lg = logging.getLogger("test.redaction")
    lg.addHandler(handler)
    lg.setLevel(logging.INFO)
    try:
        lg.info("cookie %s url %s", COOKIE, f"{mam.MAM_BASE}/tor/download.php/FAKEdlHASHcccccccc?tid=9")
        try:
            raise RuntimeError(f"boom {FAKE_TOKEN}")
        except RuntimeError:
            lg.exception("failed")
    finally:
        lg.removeHandler(handler)
    text = buf.getvalue()
    assert FAKE_TOKEN not in text
    assert "FAKEdlHASH" not in text
    assert "RuntimeError" in text


def test_install_log_redaction_attaches_filter_and_quiets_httpx():
    mam.install_log_redaction()
    assert logging.getLogger("httpx").level >= logging.WARNING
    assert any(isinstance(f, mam.RedactingFilter) for f in logging.getLogger().filters)


# ---------------- capture (opt-in) ----------------
def test_capture_is_off_by_default_and_sanitizes_when_on(net, tmp_path, monkeypatch):
    import json
    net.mam_handler = lambda r: httpx.Response(200, json=load_fixture("synthetic_search.json"))
    run(mam.search(COOKIE, text="x"))
    assert not list(tmp_path.iterdir())

    monkeypatch.setenv("MAM_CAPTURE_DIR", str(tmp_path))
    run(mam.search(COOKIE, text="x"))
    (f,) = list(tmp_path.iterdir())
    rec = json.loads(f.read_text())
    text = f.read_text()
    assert rec["status"] == 200
    assert "FAKEdlHASH" not in text and "someuploader" not in text
    assert rec["json"]["data"][0]["dl"] == "AAAAaaAAAAaaaaaaaaaaaaaaaa"  # same shape, no value


def test_capture_does_not_store_html(net, tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("MAM_CAPTURE_DIR", str(tmp_path))
    net.mam_handler = lambda r: httpx.Response(403, text="<html>secret page</html>", headers={"content-type": "text/html"})
    with pytest.raises(mam.MamAuthError):
        run(mam.search(COOKIE, text="x"))
    (f,) = list(tmp_path.iterdir())
    assert "secret page" not in f.read_text()
    assert json.loads(f.read_text())["status"] == 403


def test_redaction_keeps_log_args_structure():
    # uvicorn's access formatter unpacks record.args; the filter must not flatten them.
    rec = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1,
                            '%s - "%s %s HTTP/%s" %d',
                            ("127.0.0.1:1", "GET", f"/x?c={COOKIE}", "1.1", 200), None)
    mam.RedactingFilter().filter(rec)
    assert isinstance(rec.args, tuple) and len(rec.args) == 5
    assert FAKE_TOKEN not in rec.getMessage()
