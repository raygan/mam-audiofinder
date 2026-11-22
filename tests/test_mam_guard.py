"""The allowlist guard: unlisted endpoints, unlisted params, and fl are rejected
and never sent (docs/MAM_API_ALLOWLIST.md, ROADMAP rule 1)."""
import asyncio

import pytest

import mam
from mam import MamEndpointNotAllowed, check_allowed

BASE = mam.MAM_BASE
SEARCH = f"{BASE}/tor/js/loadSearchJSONbasic.php"
DL = "FAKEdlHASHaaaaaaaaaaaa"


def ok_body(**tor):
    return {"tor": {"text": "x", "srchIn": ["title"], "main_cat": ["13"], **tor}, "perpage": 25}


# ---------------- allowed ----------------
def test_documented_search_is_allowed():
    check_allowed("POST", f"{SEARCH}?dlLink=1", ok_body(searchType="active", sortType="seedersDesc"))


def test_full_documented_tor_key_set_is_allowed():
    check_allowed("POST", SEARCH, {
        "tor": {
            "text": "x", "srchIn": sorted(mam.SRCH_IN), "main_cat": ["13", "14"],
            "cat": ["39"], "browse_lang": [1], "searchType": "fl-VIP", "searchIn": "torrents",
            "sortType": "dateDesc", "startNumber": "0", "startDate": "2026-01-01",
            "endDate": "1767225600", "id": "5", "hash": "abcdef0123",
        },
        "perpage": 100, "dlLink": "1", "description": "1", "isbn": "1", "mediaInfo": "1", "my_snatched": "1",
    })


def test_documented_download_forms_are_allowed():
    check_allowed("GET", f"{BASE}/tor/download.php?tid=123")
    check_allowed("GET", f"{BASE}/tor/download.php/{DL}?tid=123")
    assert mam.build_dl_url(DL, "123") == f"{BASE}/tor/download.php/{DL}?tid=123"


# ---------------- host / scheme ----------------
@pytest.mark.parametrize("url", [
    "http://www.myanonamouse.net/tor/download.php?tid=1",
    "https://myanonamouse.net/tor/download.php?tid=1",
    "https://evil.example/tor/download.php?tid=1",
    "https://www.myanonamouse.net.evil.example/tor/download.php?tid=1",
    "https://user@www.myanonamouse.net/tor/download.php?tid=1",
    "https://www.myanonamouse.net:8443/tor/download.php?tid=1",
])
def test_other_hosts_rejected(url):
    with pytest.raises(MamEndpointNotAllowed):
        check_allowed("GET", url)


# ---------------- endpoints ----------------
@pytest.mark.parametrize("path", [
    "/", "/t/123", "/api/list.php", "/tor/browse.php", "/jsonLoad.php", "/login.php",
    "/tor/js/loadSearchJSONbasic.php/../x", "/tor/download.phpx?tid=1", "/preferences/index.php",
    "/bonusBuy.php", "/tor/download.php/a/b?tid=1", "/tor/download.php/%2e%2e?tid=1",
])
def test_unlisted_endpoints_rejected(path):
    with pytest.raises(MamEndpointNotAllowed):
        check_allowed("GET", BASE + path)
    with pytest.raises(MamEndpointNotAllowed):
        check_allowed("POST", BASE + path, ok_body())


def test_wrong_methods_rejected():
    with pytest.raises(MamEndpointNotAllowed):
        check_allowed("GET", SEARCH, ok_body())
    with pytest.raises(MamEndpointNotAllowed):
        check_allowed("POST", f"{BASE}/tor/download.php?tid=1")


# ---------------- search params ----------------
@pytest.mark.parametrize("body", [
    {**ok_body(), "thumbnail": "1"},
    {**ok_body(), "foo": "1"},
    {**ok_body(), "perpage": 1000},
    {**ok_body(), "perpage": 1},
    {**ok_body(), "dlLink": "yes"},
    ok_body(browseFlagsHideVsShow="0"),
    ok_body(unknown="x"),
    ok_body(main_cat=["15"]),
    ok_body(main_cat=["13", "99"]),
    ok_body(main_cat=[]),
    ok_body(srchIn=["title", "comments"]),
    ok_body(searchType="everything"),
    ok_body(searchIn="requests"),
    ok_body(sortType="hacked"),
    ok_body(startNumber="-1"),
    ok_body(startDate="yesterday"),
    ok_body(hash="not-hex"),
    ok_body(cat=["x"]),
    {"perpage": 25},
    {"tor": "text"},
])
def test_unlisted_search_params_rejected(body):
    with pytest.raises(MamEndpointNotAllowed):
        check_allowed("POST", SEARCH, body)


def test_unlisted_search_query_params_rejected():
    with pytest.raises(MamEndpointNotAllowed):
        check_allowed("POST", f"{SEARCH}?thumbnail=1", ok_body())
    with pytest.raises(MamEndpointNotAllowed):
        check_allowed("POST", f"{SEARCH}?perpage=25", ok_body())  # duplicated in body


# ---------------- download params / fl ----------------
@pytest.mark.parametrize("query", [
    "fl=1", "tid=1&fl=1", "fl=1&tid=1", "tid=1&fl=", "tid=1&FL=1", "tid=1&fl[]=1", "tid=1&f%6C=1",
])
def test_fl_is_always_rejected(query):
    for url in (f"{BASE}/tor/download.php?{query}", f"{BASE}/tor/download.php/{DL}?{query}"):
        with pytest.raises(MamEndpointNotAllowed, match="fl"):
            check_allowed("GET", url)


@pytest.mark.parametrize("url", [
    f"{BASE}/tor/download.php?id=123",          # undocumented
    f"{BASE}/tor/download.php?id=123&tid=123",
    f"{BASE}/tor/download.php",                 # no tid
    f"{BASE}/tor/download.php/{DL}",            # dl form without tid
    f"{BASE}/tor/download.php?tid=abc",
    f"{BASE}/tor/download.php?tid=1&tid=2",
    f"{BASE}/tor/download.php?tid=1#frag",
])
def test_undocumented_download_forms_rejected(url):
    with pytest.raises(MamEndpointNotAllowed):
        check_allowed("GET", url)


@pytest.mark.parametrize("dl", ["abc?fl=1", "abc/def", "short", "a b c d e f g", "abc&fl=1xx", ""])
def test_build_dl_url_rejects_bad_hashes(dl):
    with pytest.raises(MamEndpointNotAllowed):
        mam.build_dl_url(dl, "123")


@pytest.mark.parametrize("tid", ["", "12a", "1&fl=1", None])
def test_build_dl_url_rejects_bad_tid(tid):
    with pytest.raises(MamEndpointNotAllowed):
        mam.build_dl_url(DL, tid)


def test_download_with_body_rejected():
    with pytest.raises(MamEndpointNotAllowed):
        check_allowed("GET", f"{BASE}/tor/download.php?tid=1", {"fl": 1})


# ---------------- rejected requests are never sent ----------------
def test_rejected_requests_never_reach_the_network(net):
    net.mam_handler = lambda r: pytest.fail("guard let a request through")
    bad = [
        ("GET", f"{BASE}/tor/download.php?id=1", None),
        ("GET", f"{BASE}/tor/download.php?tid=1&fl=1", None),
        ("GET", f"{BASE}/api/list.php", None),
        ("POST", SEARCH, {**ok_body(), "thumbnail": 1}),
    ]
    for method, url, body in bad:
        with pytest.raises(MamEndpointNotAllowed):
            asyncio.run(mam._send(method, url, "mam_id=x", "*/*", json_body=body))
    assert net.requests == []


def test_search_route_rejects_bad_sort_without_sending(net, client):
    r = client.post("/search", json={"tor": {"text": "x", "sortType": "evil"}, "perpage": 25})
    assert r.status_code == 400
    assert r.json()["error"] == "MamEndpointNotAllowed"
    assert net.requests == []



# ---------------- real dl format: "<hash>?tid=<id>" ----------------
# Same shape as a sanitized real value (letters/digits replaced, punctuation kept).
REAL_SHAPE_HASH = ("aAaAaa0aaAAAAa0AaAAAaaAaaaaaAaaAaAaA0A0AAAa_aa-AAA0AA0AAaAAAAAa0aAAAaaa0aaAAAAaAaAaaa0"
                   "AAAAaa-AaAAaaAA0AAaaa0AA0_0aaaaAaa0aA=")


def test_real_dl_format_builds_documented_url():
    url = mam.build_dl_url(f"{REAL_SHAPE_HASH}?tid=882573", "882573")
    assert url == f"{BASE}/tor/download.php/{REAL_SHAPE_HASH}?tid=882573"
    assert url.count("?") == 1 and url.count("tid=") == 1
    assert "%" not in url


def test_bare_hash_with_padding_still_works():
    assert mam.build_dl_url(REAL_SHAPE_HASH, 5) == f"{BASE}/tor/download.php/{REAL_SHAPE_HASH}?tid=5"
    assert mam.build_dl_url("AAAAaaaa0000==", "5").endswith("/AAAAaaaa0000==?tid=5")


@pytest.mark.parametrize("dl", [
    f"{REAL_SHAPE_HASH}?tid=999",            # tid doesn't match the torrent being added
    f"{REAL_SHAPE_HASH}?uid=882573",         # undocumented param
    f"{REAL_SHAPE_HASH}?tid=882573&fl=1",    # never fl
    f"{REAL_SHAPE_HASH}?fl=1&tid=882573",
    f"{REAL_SHAPE_HASH}?tid=882573&tid=882573",
    f"{REAL_SHAPE_HASH}?tid=",
    f"{REAL_SHAPE_HASH}?",
    f"{REAL_SHAPE_HASH}?tid=882573?x=1",
    "aaaa=bbbbcccc?tid=882573",              # '=' only allowed as trailing padding
    "AAAAaaaa0000===?tid=882573",
    "AAAA/aaaa0000?tid=882573",
    "AAAA%2Faaaa00?tid=882573",
])
def test_bad_real_format_dl_rejected(dl):
    with pytest.raises(MamEndpointNotAllowed):
        mam.build_dl_url(dl, "882573")


def test_padded_hash_passes_guard_but_mid_equals_does_not():
    check_allowed("GET", f"{BASE}/tor/download.php/{REAL_SHAPE_HASH}?tid=1")
    with pytest.raises(MamEndpointNotAllowed):
        check_allowed("GET", f"{BASE}/tor/download.php/aaaa=bbbbcccc?tid=1")
