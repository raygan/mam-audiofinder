"""Settings: /data/config.json (written by /setup) overrides env vars."""
import json, logging, os
from typing import List, Tuple

import importer
import mam

log = logging.getLogger("mam-audiofinder")

CONFIG_PATH = os.getenv("APP_CONFIG_PATH", "/data/config.json")


def load_json_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def save_json_config(cfg: dict) -> None:
    dirpath = os.path.dirname(CONFIG_PATH)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def is_setup_disabled() -> bool:
    val = os.getenv("DISABLE_SETUP", "")
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def build_qb_path_map(raw_cfg, raw_env: str | None, dl_dir: str, qb_inner_prefix: str) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []

    # 1) JSON config: list of {qb_prefix, app_prefix}
    if isinstance(raw_cfg, list):
        for item in raw_cfg:
            if not isinstance(item, dict):
                continue
            qb = str(item.get("qb_prefix") or item.get("qb") or "").strip()
            app = str(item.get("app_prefix") or item.get("path") or "").strip()
            if not qb or not app:
                continue
            qb = qb.rstrip("/") or "/"
            app = app.rstrip("/") or "/"
            pairs.append((qb, app))

    # 2) Env string: "qb_prefix=app_prefix;other_qb=other_app"
    if not pairs and raw_env:
        val = raw_env.strip()
        if val:
            for part in val.split(";"):
                part = part.strip()
                if not part or "=" not in part:
                    continue
                qb, app = part.split("=", 1)
                qb = qb.strip().rstrip("/") or "/"
                app = app.strip().rstrip("/") or "/"
                if qb and app:
                    pairs.append((qb, app))

    # 3) Fallback: derive from QB_INNER_DL_PREFIX and DL_DIR
    if not pairs and qb_inner_prefix and dl_dir:
        qb = qb_inner_prefix.rstrip("/") or "/"
        app = dl_dir.rstrip("/") or "/"
        pairs.append((qb, app))

    return pairs


def _pos_int(raw, default: int) -> int:
    try:
        n = int(str(raw).strip())
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


class Settings:
    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        cfg = load_json_config()

        # The MAM base URL is fixed in mam.py; MAM_BASE is no longer configurable.
        legacy_base = cfg.get("MAM_BASE") or os.getenv("MAM_BASE")
        if legacy_base and legacy_base.rstrip("/") != mam.MAM_BASE:
            log.warning("Ignoring MAM_BASE=%r; the app only talks to %s", legacy_base, mam.MAM_BASE)

        raw_cookie = cfg.get("MAM_COOKIE")
        if raw_cookie is None:
            raw_cookie = os.getenv("MAM_COOKIE", "")
        # Only the mam_id cookie is ever sent; anything else pasted is dropped.
        self.MAM_COOKIE = mam.build_cookie(raw_cookie)
        mam.register_secret(self.MAM_COOKIE.partition("=")[2])

        self.QB_URL = (cfg.get("QB_URL") or os.getenv("QB_URL", "http://qbittorrent:8080")).rstrip("/")
        self.QB_USER = cfg.get("QB_USER") or os.getenv("QB_USER", "admin")
        self.QB_PASS = cfg.get("QB_PASS") or os.getenv("QB_PASS", "adminadmin")
        self.QB_SAVEPATH = cfg.get("QB_SAVEPATH") or os.getenv("QB_SAVEPATH", "")
        # Base tags; "audiobook"/"ebook" are added per torrent (see qb_tags).
        self.QB_TAGS = cfg.get("QB_TAGS") or os.getenv("QB_TAGS", "MAM")

        def pick(key, default=""):
            return cfg.get(key) or os.getenv(key) or default

        # Per-media qB categories. The *_AUDIO keys fall back to the pre-0.8
        # QB_CATEGORY / QB_POSTIMPORT_CATEGORY so existing setups don't change.
        self.QB_CATEGORY_AUDIO = pick("QB_CATEGORY_AUDIO", pick("QB_CATEGORY", "mam-audiofinder"))
        self.QB_CATEGORY_EBOOK = pick("QB_CATEGORY_EBOOK", "mam-audiofinder-ebooks")
        self.QB_POSTIMPORT_CATEGORY_AUDIO = pick("QB_POSTIMPORT_CATEGORY_AUDIO", pick("QB_POSTIMPORT_CATEGORY"))
        self.QB_POSTIMPORT_CATEGORY_EBOOK = pick("QB_POSTIMPORT_CATEGORY_EBOOK")
        self.QB_CATEGORY = self.QB_CATEGORY_AUDIO  # legacy name

        self.DL_DIR = cfg.get("DL_DIR") or os.getenv("DL_DIR", "/media/torrents")
        self.LIB_DIR = cfg.get("LIB_DIR") or os.getenv("LIB_DIR", "/media/audiobookshelf")
        self.IMPORT_MODE = (cfg.get("IMPORT_MODE") or os.getenv("IMPORT_MODE", "link")).lower()

        self.QB_INNER_DL_PREFIX = cfg.get("QB_INNER_DL_PREFIX") or os.getenv("QB_INNER_DL_PREFIX", "/downloads")

        raw_pm_cfg = cfg.get("QB_PATH_MAP")
        raw_pm_env = os.getenv("QB_PATH_MAP")
        self.QB_PATH_MAP = build_qb_path_map(raw_pm_cfg, raw_pm_env, self.DL_DIR, self.QB_INNER_DL_PREFIX)

        # Ebooks. Always copied; there is deliberately no import-mode setting.
        # In-container path of the ebook library's import (watch) folder.
        self.EBOOK_INGEST_DIR = (pick("EBOOK_INGEST_DIR") or "").rstrip("/")
        self.EBOOK_EXTENSIONS = importer.parse_ext_list(
            pick("EBOOK_EXTENSIONS"), importer.DEFAULT_EBOOK_EXTENSIONS)
        # Only decides which format is pre-selected; the user picks at import.
        self.EBOOK_FORMAT_PREFERENCE = importer.parse_ext_list(
            pick("EBOOK_FORMAT_PREFERENCE"), importer.DEFAULT_FORMAT_PREFERENCE)

        # Wishlist (Phase 2). The automatic scheduler is opt-in (ROADMAP rule 7).
        self.WISHLIST_SCHEDULER_ENABLED = str(pick("WISHLIST_SCHEDULER_ENABLED", "false")).strip().lower() in (
            "1", "true", "yes", "on")
        self.WISHLIST_INTERVAL_HOURS = _pos_int(pick("WISHLIST_INTERVAL_HOURS"), 72)
        # Every wishlist search (scheduled or "check now") counts toward this.
        self.WISHLIST_MAX_REQUESTS_PER_DAY = _pos_int(pick("WISHLIST_MAX_REQUESTS_PER_DAY"), 20)

        # Notifications: one webhook (ntfy by default). Never sent to MAM.
        self.NOTIFY_WEBHOOK_URL = (pick("NOTIFY_WEBHOOK_URL") or "").strip()
        fmt = str(pick("NOTIFY_FORMAT", "ntfy")).strip().lower()
        self.NOTIFY_FORMAT = fmt if fmt in ("ntfy", "json") else "ntfy"
        self.NOTIFY_TOKEN = (pick("NOTIFY_TOKEN") or "").strip()
        mam.register_secret(self.NOTIFY_TOKEN)  # keep it out of logs too
        self.NOTIFY_CLICK_URL = (pick("NOTIFY_CLICK_URL") or "").strip()
        self.NOTIFY_BODY_TEMPLATE = pick("NOTIFY_BODY_TEMPLATE") or ""
        self.NOTIFY_ON_IMPORT = str(pick("NOTIFY_ON_IMPORT", "false")).strip().lower() in ("1", "true", "yes", "on")

        self.UMASK = cfg.get("UMASK") or os.getenv("UMASK")


    # ---- per-media helpers ----
    def qb_category(self, media_type: str) -> str:
        return self.QB_CATEGORY_EBOOK if media_type == "ebook" else self.QB_CATEGORY_AUDIO

    def postimport_category(self, media_type: str) -> str:
        return self.QB_POSTIMPORT_CATEGORY_EBOOK if media_type == "ebook" else self.QB_POSTIMPORT_CATEGORY_AUDIO

    def qb_tags(self, media_type: str) -> list[str]:
        """Base QB_TAGS without any media word, plus the right media tag."""
        tags = [t.strip() for t in (self.QB_TAGS or "").split(",") if t.strip()]
        tags = [t for t in tags if t.lower() not in MEDIA_TYPES]
        return tags + [media_type]


MEDIA_TYPES = ("audiobook", "ebook")

settings = Settings()


def apply_umask() -> None:
    """Apply UMASK for created files/dirs."""
    if settings.UMASK:
        try:
            os.umask(int(settings.UMASK, 8))
        except Exception:
            pass


def needs_setup() -> bool:
    # Consider setup incomplete if we don't have a MAM cookie,
    # a library directory, or any qB path mapping.
    return not settings.MAM_COOKIE or not settings.LIB_DIR or not settings.QB_PATH_MAP
