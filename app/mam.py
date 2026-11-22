"""The only module that talks to MyAnonamouse.

Every request (and every MAM URL handed to qBittorrent) passes through
`check_allowed`, which enforces docs/MAM_API_ALLOWLIST.md. Anything not on
that list raises MamEndpointNotAllowed before a socket is opened.

See docs/MAM_COMPLIANCE.md for the rule -> code -> test mapping.
"""
import json, logging, os, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urlencode

import httpx

APP_VERSION = "0.7.0"
USER_AGENT = f"mam-audiofinder/{APP_VERSION}"

# Fixed on purpose: never configurable, so the cookie can't be sent elsewhere.
MAM_SCHEME = "https"
MAM_HOST = "www.myanonamouse.net"
MAM_BASE = f"{MAM_SCHEME}://{MAM_HOST}"

SEARCH_PATH = "/tor/js/loadSearchJSONbasic.php"
DOWNLOAD_PATH = "/tor/download.php"

log = logging.getLogger("mam")

# Tests replace this with an httpx.MockTransport. Never set in production.
transport: httpx.AsyncBaseTransport | None = None


# ---------------------------- Errors ----------------------------
class MamError(Exception):
    """Base class. Messages are always redacted and never contain MAM HTML."""


class MamEndpointNotAllowed(MamError):
    """Request blocked by the allowlist guard; nothing was sent."""


class MamAuthError(MamError):
    """MAM rejected the cookie (401/403, or a redirect, usually to login)."""


class MamRateLimitError(MamError):
    """MAM signalled rate limiting or unavailability (429/503)."""


class MamUnexpectedResponse(MamError):
    """Anything else that isn't the documented success shape."""


# ---------------------------- Allowlist ----------------------------
SEARCH_TOP_LEVEL = {"tor", "perpage", "dlLink", "description", "isbn", "mediaInfo", "my_snatched"}
SEARCH_FLAGS = {"dlLink", "description", "isbn", "mediaInfo", "my_snatched"}

SRCH_IN = {"title", "author", "narrator", "series", "description", "filenames", "fileTypes", "tags"}
# Documented: 13 AudioBooks, 14 E-Books (15/16 exist but the app doesn't use them).
MAIN_CATS = {"13", "14"}
CAT_MEDIA = {"13": "audiobook", "14": "ebook"}

# media selector -> (main_cat, default srchIn). "both" is one request with both
# documented categories (main_cat is a documented array).
MEDIA_SEARCH = {
    "audiobook": (["13"], ["title", "author", "narrator"]),
    "ebook": (["14"], ["title", "author", "series"]),  # narrator is meaningless for ebooks
    "both": (["13", "14"], ["title", "author", "narrator", "series"]),
}
SEARCH_TYPES = {"all", "active", "inactive", "fl", "fl-VIP", "VIP", "nVIP", "nMeta"}
SORT_TYPES = {"default", "random"} | {
    f"{base}{d}"
    for base in ("title", "file", "size", "seeders", "leechers", "snatched", "date", "bmka", "reseed", "category")
    for d in ("Asc", "Desc")
}
PERPAGE_MIN, PERPAGE_MAX = 5, 100

_DIGITS = re.compile(r"^\d+$")
_HEX = re.compile(r"^[0-9a-fA-F]+$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EMPTY_RESULT = re.compile(r"^Nothing returned, out of (\d+)$")
# dl hash: URL-safe base64 with optional '=' padding (shape confirmed from a
# sanitized capture, 2026-11-21). Nothing that could add a path segment or
# query string.
_DL_HASH = re.compile(r"^[A-Za-z0-9_-]{8,512}={0,2}$")


def _deny(msg: str):
    raise MamEndpointNotAllowed(msg)


def _is_id(v) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return v >= 0
    return isinstance(v, str) and bool(_DIGITS.match(v))


def _check_id_list(key: str, v):
    if not isinstance(v, list) or not all(_is_id(x) for x in v):
        _deny(f"tor.{key} must be a list of numeric ids")


def _check_tor(tor):
    if not isinstance(tor, dict):
        _deny("tor must be an object")
    for key, v in tor.items():
        if key == "text":
            if not isinstance(v, str):
                _deny("tor.text must be a string")
        elif key == "srchIn":
            if not isinstance(v, list) or not v or any(x not in SRCH_IN for x in v):
                _deny(f"tor.srchIn values must be from {sorted(SRCH_IN)}")
        elif key == "main_cat":
            if not isinstance(v, list) or not v or any(str(x) not in MAIN_CATS for x in v):
                _deny(f"tor.main_cat values must be from {sorted(MAIN_CATS)}")
        elif key in ("cat", "browse_lang"):
            _check_id_list(key, v)
        elif key == "searchType":
            if v not in SEARCH_TYPES:
                _deny("tor.searchType not allowed")
        elif key == "searchIn":
            if v != "torrents":
                _deny("tor.searchIn must be 'torrents'")
        elif key == "sortType":
            if v not in SORT_TYPES:
                _deny("tor.sortType not allowed")
        elif key in ("startNumber", "id"):
            if not _is_id(v):
                _deny(f"tor.{key} must be a non-negative integer")
        elif key in ("startDate", "endDate"):
            if not (_is_id(v) or (isinstance(v, str) and _DATE.match(v))):
                _deny(f"tor.{key} must be YYYY-MM-DD or a unix timestamp")
        elif key == "hash":
            if not (isinstance(v, str) and _HEX.match(v)):
                _deny("tor.hash must be hex")
        else:
            _deny(f"tor key not allowed: {key!r}")


def _check_search(query: list, body):
    if body is None:
        body = {}
    if not isinstance(body, dict):
        _deny("search body must be a JSON object")
    keys = [k for k, _ in query] + list(body.keys())
    if len(keys) != len(set(keys)):
        _deny("duplicate search parameter")
    for k in keys:
        if k not in SEARCH_TOP_LEVEL:
            _deny(f"search parameter not allowed: {k!r}")
    if "tor" not in body:
        _deny("search requires a tor object in the body")
    if any(k == "tor" for k, _ in query):
        _deny("tor must be sent in the body")
    values = dict(query) | body
    if "perpage" in values:
        pp = values["perpage"]
        if not _is_id(pp) or not (PERPAGE_MIN <= int(pp) <= PERPAGE_MAX):
            _deny(f"perpage must be {PERPAGE_MIN}-{PERPAGE_MAX}")
    for k in SEARCH_FLAGS & values.keys():
        if values[k] not in ("1", 1, True):
            _deny(f"{k} must be 1")
    _check_tor(body["tor"])


def _check_download_query(query: list):
    # Explicit, before the exact-match check, so the reason is clear in logs/tests.
    if any(k.lower().rstrip("[]") == "fl" for k, _ in query):
        _deny("the fl parameter is never allowed (it spends a freeleech wedge)")
    if len(query) != 1 or query[0][0] != "tid" or not _DIGITS.match(query[0][1]):
        _deny("download.php takes exactly one parameter: tid=<numeric id>")


def check_allowed(method: str, url: str, json_body=None) -> None:
    """Raise MamEndpointNotAllowed unless this request is on the allowlist."""
    method = method.upper()
    parts = urlsplit(url)
    if parts.scheme != MAM_SCHEME or parts.netloc != MAM_HOST:
        _deny("only https://www.myanonamouse.net is allowed")
    if parts.fragment:
        _deny("URL fragments not allowed")
    if "%" in parts.path or "//" in parts.path or ".." in parts.path:
        _deny("unexpected characters in path")
    try:
        query = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=bool(parts.query))
    except ValueError:
        _deny("malformed query string")

    path = parts.path
    if path == SEARCH_PATH:
        if method != "POST":
            _deny("search must be POST")
        _check_search(query, json_body)
        return

    if path == DOWNLOAD_PATH or path.startswith(DOWNLOAD_PATH + "/"):
        if method != "GET":
            _deny("download must be GET")
        if json_body is not None:
            _deny("download takes no body")
        _check_download_query(query)
        rest = path[len(DOWNLOAD_PATH):]
        if rest and not _DL_HASH.match(rest[1:]):
            _deny("dl hash has unexpected characters")
        return

    _deny(f"endpoint not on the allowlist: {path!r}")


# ---------------------------- Cookie ----------------------------
_COOKIE_TOKEN = re.compile(r"^[A-Za-z0-9%._~+/=-]+$")


def build_cookie(raw: str | None) -> str:
    """Return 'mam_id=<value>' or '' if no usable mam_id was supplied.

    Accepts either the bare token or a pasted cookie header; only mam_id is
    kept. Any other cookie in a pasted header is dropped.
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    if "=" in raw or ";" in raw:
        value = ""
        for part in raw.split(";"):
            name, _, val = part.strip().partition("=")
            if name.strip() == "mam_id":
                value = val.strip()
                break
    else:
        value = raw
    if not value or not _COOKIE_TOKEN.match(value):
        return ""
    return f"mam_id={value}"


# ---------------------------- Redaction ----------------------------
_secrets: set[str] = set()

_REDACT_PATTERNS = [
    (re.compile(r"(mam_id=)[^;\s\"']+"), r"\1REDACTED"),
    (re.compile(r"(download\.php/)[^?\s\"'#]+"), r"\1REDACTED"),
    (re.compile(r"(\"dl\"\s*:\s*\")[^\"]*(\")"), r"\1REDACTED\2"),
    (re.compile(r"('dl'\s*:\s*')[^']*(')"), r"\1REDACTED\2"),
]


def register_secret(value: str | None):
    """Remember a literal value (e.g. the cookie token) to mask everywhere."""
    if value and len(value) >= 6:
        _secrets.add(value)


def redact(s) -> str:
    s = str(s)
    for secret in sorted(_secrets, key=len, reverse=True):
        s = s.replace(secret, "REDACTED")
    for pat, repl in _REDACT_PATTERNS:
        s = pat.sub(repl, s)
    return s


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Redact the template and each arg in place, keeping the args'
        # structure (uvicorn's access formatter unpacks them).
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, (str, httpx.URL)) else a for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: redact(v) if isinstance(v, (str, httpx.URL)) else v for k, v in record.args.items()}
        if record.exc_info:
            # Pre-render the traceback redacted; Formatter prints exc_text as-is.
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


_FILTER = RedactingFilter()


def install_log_redaction():
    """Attach the redacting filter to every known handler. Idempotent."""
    # httpx logs full request URLs (incl. dl hashes) at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    names = [None, "mam", "httpx", "uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"]
    for name in names:
        lg = logging.getLogger(name)
        if _FILTER not in lg.filters:
            lg.addFilter(_FILTER)
        for h in lg.handlers:
            if _FILTER not in h.filters:
                h.addFilter(_FILTER)


# ---------------------------- Fixture capture (opt-in, dev only) ----------------------------
# When MAM_CAPTURE_DIR is set, each response to a user-initiated request is
# written there sanitized: dl hashes are replaced by same-shape dummies, owner
# names are blanked, Set-Cookie is dropped, and HTML bodies are not stored.
_SANITIZE_KEYS_BLANK = {"owner_name", "ownership"}  # ownership = [uploader_id, "name"]


def _shape(s: str) -> str:
    return re.sub(r"[a-z]", "a", re.sub(r"[A-Z]", "A", re.sub(r"\d", "0", s)))


def _sanitize(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "dl" and isinstance(v, str):
                out[k] = _shape(v)
            elif k in _SANITIZE_KEYS_BLANK:
                out[k] = "REDACTED"
            elif k == "owner":
                out[k] = "0"
            else:
                out[k] = _sanitize(v)
        return out
    if isinstance(obj, list):
        return [_sanitize(x) for x in obj]
    if isinstance(obj, str):
        return redact(obj)
    return obj


def _capture(kind: str, r: httpx.Response):
    cap_dir = os.getenv("MAM_CAPTURE_DIR")
    if not cap_dir:
        return
    try:
        ctype = r.headers.get("content-type", "")
        rec = {
            "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": kind,
            "status": r.status_code,
            "content_type": ctype,
            "location": redact(r.headers.get("location", "")) or None,
            "body_length": len(r.content),
        }
        if kind == "download":
            rec["body_starts_with_bencode"] = r.content[:1] == b"d"
        else:
            try:
                rec["json"] = _sanitize(r.json())
            except ValueError:
                rec["json"] = None
                rec["note"] = "body was not JSON (not stored)"
        Path(cap_dir).mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        path = Path(cap_dir) / f"{kind}-{r.status_code}-{stamp}.json"
        path.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("MAM response captured to %s", path)
    except Exception as e:
        log.warning("MAM capture failed: %s", e)


# ---------------------------- Transport ----------------------------
def _client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout, follow_redirects=False, transport=transport)


def _headers(cookie: str, accept: str) -> dict:
    return {"Cookie": cookie, "User-Agent": USER_AGENT, "Accept": accept}


def _check_status(r: httpx.Response):
    if r.is_redirect or 300 <= r.status_code < 400:
        raise MamAuthError(f"MAM redirected (HTTP {r.status_code}); the mam_id cookie is probably invalid or expired")
    if r.status_code in (401, 403):
        raise MamAuthError(f"MAM rejected the mam_id cookie (HTTP {r.status_code})")
    if r.status_code in (429, 503):
        raise MamRateLimitError(f"MAM is rate-limiting or unavailable (HTTP {r.status_code})")
    if r.status_code != 200:
        raise MamUnexpectedResponse(f"MAM returned HTTP {r.status_code}")


async def _send(method: str, url: str, cookie: str, accept: str, json_body=None, timeout: float = 30) -> httpx.Response:
    """The single place an HTTP request to MAM is made."""
    check_allowed(method, url, json_body)
    if not cookie:
        raise MamAuthError("MAM cookie is not configured")
    try:
        async with _client(timeout) as client:
            r = await client.request(method, url, headers=_headers(cookie, accept), json=json_body)
    except httpx.HTTPError as e:
        raise MamUnexpectedResponse(redact(f"MAM request failed: {type(e).__name__}")) from None
    return r


# ---------------------------- Normalisation ----------------------------
def _to_int(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, str) and _DIGITS.match(v.strip()):
        return int(v.strip())
    return v


def _flatten(v) -> str:
    # {"8320":"John Steinbeck"} or its JSON-string form -> "John Steinbeck"
    if isinstance(v, dict):
        return ", ".join(str(x) for x in v.values())
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("{") or s.startswith("["):
            try:
                obj = json.loads(s)
                if isinstance(obj, (dict, list)):
                    return _flatten(obj)
            except Exception:
                pass
        s = re.sub(r'^\{|\}$', '', s)
        parts = [chunk.split(":", 1)[-1] for chunk in s.split(",")]
        parts = [p.strip().strip('"').strip("'") for p in parts if p.strip()]
        return ", ".join(parts)
    return "" if v is None else str(v)


def _detect_format(item: dict) -> str:
    # Documented field first (docs say filetypes; the example shows filetype).
    for key in ("filetypes", "filetype", "format", "container", "encoding", "format_name"):
        val = item.get(key)
        if isinstance(val, list):
            val = " ".join(str(x) for x in val)
        if isinstance(val, str) and val.strip():
            toks = [t for t in re.split(r"[\s,/|]+", val.strip()) if t]
            return "/".join(dict.fromkeys(t.upper() for t in toks))
    name = item.get("title") or item.get("name") or ""
    toks = re.findall(r'(?i)\b(mp3|m4b|flac|aac|ogg|opus|wav|alac|ape|epub|pdf|mobi|azw3|cbz|cbr)\b', name)
    return "/".join(dict.fromkeys(t.upper() for t in toks))


def _json_obj(v) -> dict:
    """author_info / series_info arrive as JSON strings of {id: ...}."""
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v.strip().startswith("{"):
        try:
            obj = json.loads(v)
            return obj if isinstance(obj, dict) else {}
        except ValueError:
            return {}
    return {}


def _series(item: dict) -> list[tuple[str, str, str]]:
    """[(series_id, name, number)] from {"97828": ["Name", "3", 3.0]}."""
    out = []
    for sid, val in _json_obj(item.get("series_info")).items():
        if isinstance(val, list) and val:
            out.append((str(sid), str(val[0]), str(val[1]) if len(val) > 1 else ""))
        elif isinstance(val, str):
            out.append((str(sid), val, ""))
    return out


_FORMAT_WORDS = re.compile(r"(?i)\b(mp3|m4b|m4a|flac|aac|ogg|opus|epub|pdf|mobi|azw3?|cbz|cbr|djvu|fb2|unabridged|retail)\b")


def _norm_title(title: str) -> str:
    t = re.sub(r"[\[(].*?[\])]", " ", title or "")  # [EPUB], (Unabridged) ...
    t = _FORMAT_WORDS.sub(" ", t)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t.lower()).split())


def _media_type(item: dict) -> str:
    mt = CAT_MEDIA.get(str(item.get("main_cat") or ""))
    if mt:
        return mt
    # Fallback seen in real responses: mediatype 1 = audio, 2 = ebook.
    return {"1": "audiobook", "2": "ebook"}.get(str(item.get("mediatype") or ""), "")


def group_key(item: dict) -> str:
    """Torrents of the same book share a key: same media type, same author
    ids, and the same series id + number (or, without a series, the same
    normalised title). Audiobook and ebook versions are never grouped, and
    audiobooks with different narrators are different recordings, so the
    narrator ids are part of an audiobook's key."""
    media = _media_type(item)
    authors = sorted(_json_obj(item.get("author_info")))
    who = ",".join(authors) or _norm_title(_flatten(item.get("author_info")))
    if media == "audiobook":
        narrators = sorted(_json_obj(item.get("narrator_info")))
        who += "|n:" + (",".join(narrators) or _norm_title(_flatten(item.get("narrator_info"))))
    series = [s for s in _series(item) if s[2]]
    if series:
        what = "s:" + ";".join(f"{sid}#{num}" for sid, _, num in sorted(series))
    else:
        what = "t:" + _norm_title(item.get("title") or item.get("name") or "")
    return f"{media}|{who}|{what}"


def normalize_result(item: dict) -> dict:
    series = _series(item)
    return {
        "media_type": _media_type(item),
        "group": group_key(item),
        "id": str(item.get("id") or item.get("tid") or ""),
        "title": item.get("title") or item.get("name"),
        "series": ", ".join(f"{name} #{num}" if num else name for _, name, num in series),
        "author_info": _flatten(item.get("author_info")),
        "narrator_info": _flatten(item.get("narrator_info")),
        "format": _detect_format(item),
        "size": item.get("size"),
        "seeders": _to_int(item.get("seeders")),
        "leechers": _to_int(item.get("leechers")),
        "catname": item.get("catname"),
        "added": item.get("added"),
        "dl": item.get("dl"),
    }


# ---------------------------- Public API ----------------------------
def clamp_perpage(v) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = 25
    return max(PERPAGE_MIN, min(PERPAGE_MAX, n))


async def search(
    cookie: str,
    text: str = "",
    media: str = "audiobook",
    srch_in: list[str] | None = None,
    main_cat: list[str] | None = None,
    search_type: str = "all",
    sort_type: str = "default",
    start_number: int = 0,
    perpage: int = 25,
) -> dict:
    """One documented JSON search. Returns {"results", "total", "total_found"}.

    `media` (audiobook | ebook | both) picks the documented main_cat and the
    default search fields; explicit srch_in / main_cat override it.
    """
    if media not in MEDIA_SEARCH:
        raise MamEndpointNotAllowed(f"unknown media type: {media!r}")
    media_cats, media_srch_in = MEDIA_SEARCH[media]
    tor = {
        "text": text or "",
        "srchIn": list(srch_in or media_srch_in),
        "searchType": search_type,
        "sortType": sort_type,
        "startNumber": str(int(start_number)),
        "main_cat": [str(c) for c in (main_cat or media_cats)],
    }
    # dlLink goes in the JSON body with the other top-level parameters: sent
    # as a query param (as before 0.8), MAM returned no dl field at all.
    body = {"tor": tor, "perpage": clamp_perpage(perpage), "dlLink": "1"}
    url = f"{MAM_BASE}{SEARCH_PATH}"

    r = await _send("POST", url, cookie, "application/json", json_body=body)
    _capture("search", r)
    _check_status(r)
    try:
        raw = r.json()
    except ValueError:
        raise MamUnexpectedResponse("MAM search returned a non-JSON body") from None
    if not isinstance(raw, dict):
        raise MamUnexpectedResponse("MAM search returned an unexpected JSON shape")
    if "data" not in raw:
        err = raw.get("error")
        # Observed from MAM (200 OK) when a search matches nothing. Only this
        # exact shape means "empty"; any other error still fails closed.
        m = _EMPTY_RESULT.match(err) if isinstance(err, str) else None
        if m and set(raw) == {"error"}:
            return {"results": [], "total": 0, "total_found": int(m.group(1))}
        detail = f": {redact(err)[:120]}" if isinstance(err, str) else ""
        raise MamUnexpectedResponse(f"MAM search returned no data{detail}")
    data = raw.get("data")
    if not isinstance(data, list):
        raise MamUnexpectedResponse("MAM search 'data' is not a list")

    return {
        "results": [normalize_result(it) for it in data if isinstance(it, dict)],
        "total": _to_int(raw.get("total")),
        # Docs say total_found; the real response (2026-11 capture) says found.
        "total_found": _to_int(raw.get("total_found", raw.get("found"))),
    }


def build_dl_url(dl: str, tid) -> str:
    """Documented cookie-less download URL, for handing to qBittorrent.

    MAM's dl value (confirmed 2026-11-21) is "<hash>?tid=<id>": the hash is
    URL-safe base64 (A-Z a-z 0-9 _ -, optional '=' padding) and MAM has
    already appended the documented ?tid=. A bare hash is also accepted.
    The query, if present, must be exactly tid=<this torrent's id>; anything
    else (fl, another param, a different id) is refused. The URL is rebuilt
    from the validated parts, unencoded, so the guard sees what qB fetches.
    """
    dl, tid = str(dl or ""), str(tid if tid is not None else "")
    if not _DIGITS.match(tid):
        _deny("download.php takes exactly one parameter: tid=<numeric id>")
    dl_hash, sep, query = dl.partition("?")
    if sep:
        try:
            pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True)
        except ValueError:
            _deny("dl hash has an unexpected query string")
        _check_download_query(pairs)  # exactly tid=<digits>; never fl
        if pairs[0][1] != tid:
            _deny("dl hash tid does not match the torrent id")
    if not _DL_HASH.match(dl_hash):
        _deny("dl hash has unexpected characters")
    url = f"{MAM_BASE}{DOWNLOAD_PATH}/{dl_hash}?{urlencode({'tid': tid})}"
    check_allowed("GET", url)
    return url


async def fetch_torrent(cookie: str, tid) -> bytes:
    """One cookie-authenticated GET /tor/download.php?tid=<id>. No retries."""
    url = f"{MAM_BASE}{DOWNLOAD_PATH}?{urlencode({'tid': str(tid)})}"
    r = await _send("GET", url, cookie, "application/x-bittorrent", timeout=60)
    _capture("download", r)
    _check_status(r)
    ctype = r.headers.get("content-type", "").lower()
    if "html" in ctype or not r.content.startswith(b"d"):
        raise MamUnexpectedResponse("MAM download did not return a .torrent file")
    return r.content
