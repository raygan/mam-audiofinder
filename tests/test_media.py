"""Phase 1 media selector: documented main_cat per media, one request for
"both", and media_type on every result."""
import json

import httpx
import pytest

from conftest import load_fixture

EMPTY = {"error": "Nothing returned, out of 0"}


def capture_body(net):
    seen = []
    def h(r):
        seen.append(json.loads(r.read()))
        return httpx.Response(200, json=EMPTY)
    net.mam_handler = h
    return seen


@pytest.mark.parametrize("media,cats,srch_in", [
    ("audiobook", ["13"], ["title", "author", "narrator"]),
    ("ebook", ["14"], ["title", "author", "series"]),
    ("both", ["13", "14"], ["title", "author", "narrator", "series"]),
])
def test_media_maps_to_documented_categories(net, client, media, cats, srch_in):
    seen = capture_body(net)
    r = client.post("/search", json={"tor": {"text": "x"}, "media": media})
    assert r.status_code == 200, r.text
    assert len(seen) == 1  # "both" is a single request
    assert seen[0]["tor"]["main_cat"] == cats
    assert seen[0]["tor"]["srchIn"] == srch_in


def test_default_media_is_audiobook_and_unchanged(net, client):
    seen = capture_body(net)
    client.post("/search", json={"tor": {"text": "x"}})
    assert seen[0]["tor"]["main_cat"] == ["13"]
    assert seen[0]["tor"]["srchIn"] == ["title", "author", "narrator"]


@pytest.mark.parametrize("media", ["music", "15", "", "AUDIOBOOK", ["13"]])
def test_unknown_media_rejected_without_sending(net, client, media):
    if media == "":
        seen = capture_body(net)
        assert client.post("/search", json={"tor": {"text": "x"}, "media": ""}).status_code == 200
        assert seen[0]["tor"]["main_cat"] == ["13"]  # empty falls back to the default
        return
    r = client.post("/search", json={"tor": {"text": "x"}, "media": media})
    assert r.status_code == 400
    assert net.requests == []


def test_results_carry_media_type(net, client):
    body = load_fixture("search_audiobook.json")["json"]
    body = {**body, "data": body["data"][:1] + [{**body["data"][1], "id": 5, "main_cat": 14, "filetype": "epub"}]}
    net.mam_handler = lambda r: httpx.Response(200, json=body)
    results = client.post("/search", json={"tor": {"text": "x"}, "media": "both"}).json()["results"]
    assert [x["media_type"] for x in results] == ["audiobook", "ebook"]
    assert results[1]["format"] == "EPUB"


def test_unknown_main_cat_has_empty_media_type():
    import mam
    assert mam.normalize_result({"id": 1, "main_cat": 16})["media_type"] == ""
    assert mam.normalize_result({"id": 1, "main_cat": "14"})["media_type"] == "ebook"


def test_pages_use_new_name(client):
    page = client.get("/setup").text
    assert "Book Finder" in page and "Audiobook Finder" not in page
