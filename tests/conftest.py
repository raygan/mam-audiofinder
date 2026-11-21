"""Test setup. No test may reach the network: every httpx client is routed
through a MockTransport, and MAM traffic fails the test unless a test
explicitly installs a MAM handler."""
import json, os, sys, tempfile
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Fake values only. Never put a real cookie or dl hash in tests.
FAKE_TOKEN = "FAKE-test-cookie-0123456789"
QB_URL = "http://qb.test:8080"

_tmp = Path(tempfile.mkdtemp(prefix="mamaf-test-"))
os.environ["APP_DB_PATH"] = str(_tmp / "history.db")
os.environ["APP_CONFIG_PATH"] = str(_tmp / "config.json")
os.environ["MAM_COOKIE"] = FAKE_TOKEN
os.environ["QB_URL"] = QB_URL
os.environ["QB_PATH_MAP"] = "/downloads=/media/torrents"
os.environ["LIB_DIR"] = str(_tmp / "library")
os.environ.pop("MAM_CAPTURE_DIR", None)

sys.path.insert(0, str(ROOT / "app"))

import mam  # noqa: E402
import main  # noqa: E402


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class Net:
    """Records every request; routes MAM and qB to per-test handlers."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.mam_handler = None
        self.qb_handler = self.default_qb

    @property
    def mam_requests(self):
        return [r for r in self.requests if r.url.host == mam.MAM_HOST]

    @property
    def qb_requests(self):
        return [r for r in self.requests if r.url.host == "qb.test"]

    def default_qb(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v2/auth/login":
            return httpx.Response(200, text="Ok.")
        if path == "/api/v2/torrents/add":
            return httpx.Response(200, text="Ok.")
        if path == "/api/v2/torrents/info":
            return httpx.Response(200, json=[{"hash": "abc123", "name": "Example"}])
        return httpx.Response(404)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == mam.MAM_HOST:
            if self.mam_handler is None:
                pytest.fail(f"Unexpected MAM request: {request.method} {mam.redact(request.url)}")
            return self.mam_handler(request)
        if request.url.host == "qb.test":
            return self.qb_handler(request)
        pytest.fail(f"Unexpected network request: {request.method} {request.url}")


@pytest.fixture(autouse=True)
def net(monkeypatch):
    n = Net()
    t = httpx.MockTransport(n.handle)
    monkeypatch.setattr(mam, "transport", t)

    real_async = httpx.AsyncClient

    class RoutedAsyncClient(real_async):
        def __init__(self, *a, **kw):
            if kw.get("transport") is None:
                kw["transport"] = t
            super().__init__(*a, **kw)

    # main.py talks to qB with httpx.AsyncClient; route that too.
    monkeypatch.setattr(main.httpx, "AsyncClient", RoutedAsyncClient)
    return n


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c
