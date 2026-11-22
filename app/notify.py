"""Outgoing notifications (ROADMAP Phase 2): one webhook, ntfy by default.

Never contacts MAM. Payloads never include the cookie, dl values or
download links; text passes through mam.redact() as a backstop. Sending is
best effort: a failure is logged and never breaks a check or an import.
"""
import json, logging
from urllib.parse import urlsplit, urlunsplit

import httpx

import mam
from config import settings

log = logging.getLogger("mam-audiofinder")

FORMATS = ("ntfy", "json")
TAGS = {"match": ["books"], "auto_grab": ["inbox_tray"], "halt": ["warning"],
        "import": ["white_check_mark"], "test": ["bell"]}


def target_problem(url: str) -> str | None:
    """None if `url` is an acceptable webhook target, else why not."""
    if not url:
        return "NOTIFY_WEBHOOK_URL is not set"
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return "The notification URL must start with http:// or https://"
    host = parts.hostname.lower()
    if host == mam.MAM_HOST or host.endswith("myanonamouse.net"):
        return "Notifications can't be sent to MyAnonamouse"
    return None


def _ntfy_request(url: str, title: str, message: str, event: str, click: str | None):
    """ntfy "publish as JSON": POST to the server root with the topic in the body."""
    parts = urlsplit(url)
    topic = parts.path.strip("/").split("/")[-1] if parts.path.strip("/") else ""
    if not topic:
        raise ValueError("The ntfy URL needs a topic, e.g. https://ntfy.example.com/books")
    base_path = "/".join(parts.path.strip("/").split("/")[:-1])
    root = urlunsplit((parts.scheme, parts.netloc, f"/{base_path}" if base_path else "/", "", ""))
    body = {"topic": topic, "title": title, "message": message, "tags": TAGS.get(event, [])}
    if click:
        body["click"] = click
    if event == "halt":
        body["priority"] = 4
    return root, {"json": body}


def _json_request(url: str, title: str, message: str, event: str, click: str | None):
    values = {"event": event, "title": title, "message": message, "click": click or ""}
    template = settings.NOTIFY_BODY_TEMPLATE
    if template:
        # {{name}} placeholders, each replaced with a JSON-escaped string.
        body = template
        for k, v in values.items():
            body = body.replace("{{" + k + "}}", json.dumps(v)[1:-1])
        return url, {"content": body.encode("utf-8"), "headers": {"Content-Type": "application/json"}}
    return url, {"json": values}


async def send(event: str, title: str, message: str) -> bool:
    """Send one notification. Returns True if the webhook accepted it."""
    url = settings.NOTIFY_WEBHOOK_URL
    if not url:
        return False
    problem = target_problem(url)
    if problem:
        log.warning("Notification not sent: %s", problem)
        return False
    title, message = mam.redact(title)[:250], mam.redact(message)[:3500]
    click = settings.NOTIFY_CLICK_URL or None
    try:
        if settings.NOTIFY_FORMAT == "json":
            target, kw = _json_request(url, title, message, event, click)
        else:
            target, kw = _ntfy_request(url, title, message, event, click)
        headers = dict(kw.pop("headers", {}))
        if settings.NOTIFY_TOKEN:
            headers["Authorization"] = f"Bearer {settings.NOTIFY_TOKEN}"
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as c:
            r = await c.post(target, headers=headers, **kw)
        if r.status_code >= 300:
            log.warning("Notification not accepted: HTTP %s", r.status_code)
            return False
        return True
    except Exception as e:
        log.warning("Notification failed: %s", mam.redact(f"{type(e).__name__}: {e}"))
        return False


# ---------------------------- messages ----------------------------
def _describe(r: dict) -> str:
    icon = {"audiobook": "🎧", "ebook": "📖"}.get(r.get("media_type"), "•")
    bits = [b for b in (r.get("format"), f"{r.get('seeders')} seeders" if r.get("seeders") is not None else None) if b]
    return f"{icon} {r.get('title') or 'Untitled'}" + (f" ({', '.join(bits)})" if bits else "")


async def wishlist_matches(item: dict, matches: list[dict]) -> bool:
    if not matches:
        return False
    name = item.get("label") or item.get("query")
    n = len(matches)
    title = f"Wishlist: {n} new match{'es' if n != 1 else ''} for “{name}”"
    lines = [_describe(r) for r in matches[:10]]
    if n > 10:
        lines.append(f"…and {n - 10} more")
    return await send("match", title, "\n".join(lines))


async def imported(title: str, media_type: str) -> bool:
    if not settings.NOTIFY_ON_IMPORT:
        return False
    where = "ebook import folder" if media_type == "ebook" else "Audiobookshelf library"
    return await send("import", f"Imported: {title}", f"Copied to the {where}.")
