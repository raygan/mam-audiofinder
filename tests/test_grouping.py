"""Search-result grouping: torrents of the same book share a group key."""
import httpx

import mam
from conftest import load_fixture
from test_mam_http import COOKIE, run


def results(net, fixture, media="audiobook"):
    net.mam_handler = lambda r: httpx.Response(200, json=load_fixture(fixture)["json"])
    return run(mam.search(COOKIE, text="x", media=media))["results"]


def test_real_audiobook_versions_group_together(net):
    rs = results(net, "search_audiobook.json")
    ss3 = [r for r in rs if r["title"] == "Saving Supervillains 3"]
    assert {r["format"] for r in ss3} == {"M4B", "MP3"}
    assert len({r["group"] for r in ss3}) == 1
    # different books in the same series stay apart
    assert len({r["group"] for r in rs}) == len(rs) - 1


def test_real_both_search_never_mixes_audio_and_ebook(net):
    rs = results(net, "search_both.json", media="both")
    assert len(rs) == 9
    assert {r["media_type"] for r in rs} == {"audiobook", "ebook"}
    assert len({r["group"] for r in rs}) == 9  # same book, different media -> separate groups
    hk4 = [r for r in rs if r["title"] == "Hex Kittens 4"]
    assert {r["media_type"] for r in hk4} == {"audiobook", "ebook"}


def test_series_display(net):
    rs = results(net, "search_both.json", media="both")
    assert {r["series"] for r in rs if r["title"] == "Hex Kittens 4"} == {"Hex Kittens #4"}


def ebook(id_, title, filetype, authors='{"1":"Ann Author"}', series="{}"):
    return {"id": id_, "main_cat": 14, "title": title, "filetype": filetype,
            "author_info": authors, "series_info": series}


def test_no_series_groups_by_normalised_title():
    a = mam.normalize_result(ebook(1, "The Book [EPUB]", "epub"))
    b = mam.normalize_result(ebook(2, "The Book (PDF)", "pdf"))
    c = mam.normalize_result(ebook(3, "the book: retail", "cbz"))
    d = mam.normalize_result(ebook(4, "The Book", "epub", authors='{"2":"Someone Else"}'))
    e = mam.normalize_result(ebook(5, "The Other Book", "epub"))
    assert a["group"] == b["group"] == c["group"]
    assert d["group"] != a["group"] and e["group"] != a["group"]


def test_author_order_does_not_matter():
    a = mam.normalize_result(ebook(1, "X", "epub", authors='{"1":"A","2":"B"}'))
    b = mam.normalize_result(ebook(2, "X", "pdf", authors='{"2":"B","1":"A"}'))
    assert a["group"] == b["group"]


def test_series_number_beats_title_differences():
    s = '{"9":["Saga","2",2.0]}'
    a = mam.normalize_result(ebook(1, "Saga 2", "epub", series=s))
    b = mam.normalize_result(ebook(2, "Saga Book Two: The Sequel", "pdf", series=s))
    c = mam.normalize_result(ebook(3, "Saga 3", "epub", series='{"9":["Saga","3",3.0]}'))
    assert a["group"] == b["group"] != c["group"]


def test_mediatype_fallback():
    assert mam.normalize_result({"id": 1, "mediatype": 2})["media_type"] == "ebook"
    assert mam.normalize_result({"id": 1, "mediatype": "1"})["media_type"] == "audiobook"


def test_malformed_info_fields_do_not_crash():
    r = mam.normalize_result({"id": 1, "title": "T", "author_info": "{not json", "series_info": "[1,2]"})
    assert r["group"] and r["series"] == ""


def audiobook(id_, fmt, narrators):
    return {"id": id_, "main_cat": 13, "title": "Saga 1", "filetype": fmt,
            "author_info": '{"1":"Ann Author"}', "narrator_info": narrators,
            "series_info": '{"9":["Saga","1",1.0]}'}


def test_audiobooks_with_different_narrators_are_not_grouped():
    a = mam.normalize_result(audiobook(1, "m4b", '{"10":"Ned Narrator"}'))
    b = mam.normalize_result(audiobook(2, "mp3", '{"10":"Ned Narrator"}'))
    c = mam.normalize_result(audiobook(3, "m4b", '{"11":"Nia Other"}'))
    d = mam.normalize_result(audiobook(4, "m4b", '{"10":"Ned Narrator","11":"Nia Other"}'))
    assert a["group"] == b["group"]
    assert len({a["group"], c["group"], d["group"]}) == 3


def test_narrator_order_does_not_matter():
    a = mam.normalize_result(audiobook(1, "m4b", '{"10":"A","11":"B"}'))
    b = mam.normalize_result(audiobook(2, "mp3", '{"11":"B","10":"A"}'))
    assert a["group"] == b["group"]


def test_ebooks_ignore_narrator_field():
    base = ebook(1, "X", "epub", series='{"9":["Saga","1",1.0]}')
    a = mam.normalize_result({**base, "narrator_info": "{}"})
    b = mam.normalize_result({**base, "id": 2, "filetype": "pdf", "narrator_info": '{"10":"Someone"}'})
    assert a["group"] == b["group"]
