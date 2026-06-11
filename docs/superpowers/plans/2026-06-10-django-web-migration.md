# Django + Channels Web Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the FastAPI web app with a Django + Channels app serving the same UI and live debate, launched with `python manage.py runserver` (auto-reloads on code change).

**Architecture:** Django serves the HTTP routes (`/`, `/api/committee`, `/reports/<f>`); a Channels `AsyncWebsocketConsumer` handles `/ws/run/<market>/<stock_no>`. The synchronous committee engine is reused unchanged via the existing thread+queue worker, which the consumer drains and streams as JSON. The frontend (`web/static/*`) is kept as-is; `agentcore/`, `committee/`, the CLI, and the desktop GUI are untouched.

**Tech Stack:** Django 5.x, Channels 4.x, daphne (ASGI dev server), vanilla JS, pytest. Run via `.venv/bin/python`.

**Spec:** `docs/superpowers/specs/2026-06-10-django-web-migration-design.md`

**Conventions:**
- Test with `.venv/bin/python -m pytest` and run Django commands with `.venv/bin/python manage.py …` (the default `python` is a broken anaconda 3.7).
- The frontend `app.js`/`index.html`/`style.css` stay in `web/static/` and are NOT modified (Channels routes the same WS path; `/api/committee` returns the same payload).
- Keep `web/server.py` and the FastAPI deps until the final cutover task, so the suite stays runnable throughout.

---

## File Structure

**Create:**
- `manage.py` — Django entrypoint
- `config/__init__.py`, `config/settings.py`, `config/urls.py`, `config/asgi.py`
- `committee_web/__init__.py`, `apps.py`, `views.py`, `run.py`, `consumers.py`, `routing.py`
- `tests/conftest.py` — configures Django for the test session
- `tests/test_django_web.py` — view + run-worker + consumer tests

**Modify:**
- `requirements.txt` — add `django`, `channels`, `daphne`; later remove `fastapi`, `uvicorn`
- `.gitignore` — add `db.sqlite3`
- `start-web.sh`, `start-web.ps1` — launch `manage.py runserver`

**Delete (final task):**
- `web/server.py`, `tests/test_web.py`

---

## Task 1: Dependencies

**Files:** Modify `requirements.txt`

- [ ] **Step 1: Add the Django deps** to `requirements.txt`. Insert after the `yfinance>=0.2` line (keep `fastapi`/`uvicorn` for now — they're removed in Task 4):

```
django>=5.0
channels>=4.0
daphne>=4.0
```

- [ ] **Step 2: Install + import check**

Run:
```bash
.venv/bin/python -m pip install -q 'django>=5.0' 'channels>=4.0' 'daphne>=4.0'
.venv/bin/python -c "import django, channels, daphne; print('django', django.get_version())"
```
Expected: prints `django 5.x`.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "build: add Django, Channels, daphne deps"
```

---

## Task 2: Django project + HTTP app (views, run worker) + tests

**Files:**
- Create: `manage.py`, `config/__init__.py`, `config/settings.py`, `config/urls.py`, `config/asgi.py`, `committee_web/__init__.py`, `committee_web/apps.py`, `committee_web/views.py`, `committee_web/run.py`, `tests/conftest.py`, `tests/test_django_web.py`
- Modify: `.gitignore`

- [ ] **Step 1: Create `manage.py`**

```python
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create the `config` package**

`config/__init__.py`: empty file.

`config/settings.py`:
```python
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
DEBUG = True
ALLOWED_HOSTS = ["*"]

# daphne must be first so its runserver (ASGI + websockets + autoreload) wins.
INSTALLED_APPS = [
    "daphne",
    "channels",
    "django.contrib.staticfiles",
    "committee_web",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": []},
}]

ASGI_APPLICATION = "config.asgi.application"
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# sqlite is configured only to satisfy Django; no models/migrations are defined.
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
                         "NAME": BASE_DIR / "db.sqlite3"}}

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "web" / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

`config/urls.py`:
```python
from django.conf import settings
from django.urls import path, re_path
from django.views.static import serve

from committee_web import views

urlpatterns = [
    path("", views.index),
    path("api/committee", views.committee_info),
    re_path(r"^reports/(?P<path>.*)$", serve, {"document_root": settings.REPORTS_DIR}),
]
```

`config/asgi.py` (HTTP only for now; the websocket protocol is added in Task 3). The `ASGIStaticFilesHandler` serves `/static/` in dev under daphne:
```python
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from channels.routing import ProtocolTypeRouter
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": ASGIStaticFilesHandler(django_asgi_app),
})
```

- [ ] **Step 3: Create the `committee_web` app**

`committee_web/__init__.py`: empty file.

`committee_web/apps.py`:
```python
from django.apps import AppConfig


class CommitteeWebConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "committee_web"
```

`committee_web/run.py` — the thread-worker, moved from `web/server.py` with names made importable (`run_committee`, `DONE_SENTINEL`, `serialize_event`, `safe_market`) and the report dir sourced from settings:
```python
import queue  # noqa: F401  (imported for type clarity; queues are created by callers)
from typing import Any, Dict

from django.conf import settings

from agentcore.events import Event, EventBus
from agentcore.evidence import EvidenceLedger  # noqa: F401
from agentcore.llm import LLMClient
from agentcore.orchestrator import Orchestrator
from agentcore.report import ReportCollector  # noqa: F401
from committee.config import API_KEY_ENV, BASE_URL, REFLECTION_PASSES
from committee.domain_tools import build_registry
from committee.markets import get_profile
from committee.report import save_report

DONE_SENTINEL = object()


def safe_market(market: str) -> str:
    return market if market in ("tw", "us") else "tw"


def serialize_event(e: Event) -> Dict[str, Any]:
    """Convert an Event dataclass to a JSON-safe dict for WebSocket transport."""
    return {"type": e.type, "agent": e.agent, "data": e.data, "ts": e.ts}


def run_committee(stock_no, market, q, collector, ledger) -> None:
    """Background worker: run the committee, push Events onto q, save the report,
    then push DONE_SENTINEL. Never raises — failures become an 'error' event."""
    try:
        bus = EventBus()
        bus.subscribe(q.put)
        bus.subscribe(collector)
        llm = LLMClient(base_url=BASE_URL, api_key_env=API_KEY_ENV)
        profile = get_profile(safe_market(market))
        registry = build_registry(profile.client, profile.descriptions)
        t = profile.templates
        committee = profile.committee
        orch = Orchestrator(research=committee.research, challengers=committee.challengers,
                            chair=committee.chair, verifier=committee.verifier,
                            analyst_task_template=t.analyst,
                            challenge_task_template=t.challenge,
                            rebuttal_task_template=t.rebuttal,
                            reflect_task_template=t.reflect,
                            reflection_passes=REFLECTION_PASSES,
                            verify_task_template=t.verify,
                            correction_task_template=t.correction)
        orch.run(stock_no=stock_no, llm=llm, registry=registry, bus=bus, ledger=ledger)
        path = save_report(stock_no, collector, ledger=ledger,
                           reports_dir=str(settings.REPORTS_DIR), twse=profile.client,
                           labels=profile.labels)
        q.put(Event(type="report", agent="system",
                    data={"path": path.name, "url": "/reports/" + path.name}))
    except Exception as exc:  # surface failures to the browser instead of dying silently
        q.put(Event(type="error", agent="system",
                    data={"tool": "run", "error": str(exc)}))
    finally:
        q.put(DONE_SENTINEL)
```

`committee_web/views.py`:
```python
from django.conf import settings
from django.http import FileResponse, JsonResponse

from committee.config import REFLECTION_PASSES
from committee.markets import get_profile

from committee_web.run import safe_market

_INDEX = settings.BASE_DIR / "web" / "static" / "index.html"


def index(request):
    return FileResponse(open(_INDEX, "rb"), content_type="text/html")


def committee_info(request):
    profile = get_profile(safe_market(request.GET.get("market", "tw")))
    c = profile.committee
    names = profile.labels.agent_names

    def info(a, group):
        return {"name": a.name, "label": names.get(a.name, a.name),
                "model": a.model, "tools": list(a.tool_names), "group": group}

    return JsonResponse({
        "market": profile.market,
        "research": [info(a, "research") for a in c.research],
        "challengers": [info(a, "challengers") for a in c.challengers],
        "chair": info(c.chair, "chair"),
        "verifier": info(c.verifier, "verifier"),
        "phase_names": profile.labels.phase_names,
        "agent_names": names,
        "reflection_passes": REFLECTION_PASSES,
        "ui": profile.ui,
    })
```

- [ ] **Step 4: Ignore the sqlite file** — append `db.sqlite3` to `.gitignore`.

- [ ] **Step 5: Create `tests/conftest.py`** so Django is configured for the suite:

```python
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
```

- [ ] **Step 6: Write the HTTP tests** — `tests/test_django_web.py`:

```python
import queue

from django.test import Client

from agentcore.evidence import EvidenceLedger
from agentcore.report import ReportCollector


def _client():
    return Client()


def test_committee_info_tw_is_chinese():
    d = _client().get("/api/committee?market=tw").json()
    assert d["ui"]["title"] == "台股投資委員會"
    assert d["phase_names"]["RESEARCH"] == "研究分析"
    assert next(a for a in d["research"] if a["name"] == "fundamental")["label"] == "基本面分析師"


def test_committee_info_us_is_english():
    d = _client().get("/api/committee?market=us").json()
    assert d["ui"]["title"] == "US Equity Investment Committee"
    assert d["phase_names"]["RESEARCH"] == "Research"
    assert next(a for a in d["research"] if a["name"] == "fundamental")["label"] == "Fundamentals Analyst"


def test_committee_info_unknown_market_falls_back_to_tw():
    d = _client().get("/api/committee?market=jp").json()
    assert d["ui"]["title"] == "台股投資委員會"


def test_index_serves_the_spa_html():
    resp = _client().get("/")
    body = b"".join(resp.streaming_content)
    assert b'name="market"' in body and b"app.js" in body


def test_run_committee_uses_forced_market(monkeypatch):
    """run_committee routes by the explicit market arg, not the ticker format."""
    import committee_web.run as run

    captured = {}

    class _StubOrch:
        def __init__(self, **kw):
            pass

        def run(self, **kw):
            captured["ran"] = True

    monkeypatch.setattr(run, "Orchestrator", _StubOrch)
    monkeypatch.setattr(run, "LLMClient", lambda **kw: object())
    monkeypatch.setattr(run, "save_report", lambda *a, **k: type("P", (), {"name": "x.html"})())
    monkeypatch.setattr(run, "build_registry",
                        lambda client, desc: captured.update(client_type=type(client).__name__) or "REG")

    q = queue.Queue()
    run.run_committee("2330", "us", q, ReportCollector(), EvidenceLedger())
    assert captured.get("ran") is True
    assert captured.get("client_type") == "UsClient"  # forced US despite TW ticker
```

- [ ] **Step 7: Run the new tests + `manage.py check`**

Run:
```bash
.venv/bin/python manage.py check
.venv/bin/python -m pytest tests/test_django_web.py -v
```
Expected: `check` reports no issues; all 5 tests PASS.

- [ ] **Step 8: Run the full suite** (nothing else should break)

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (existing tests + the 5 new ones; `tests/test_web.py` still passes — FastAPI is still present).

- [ ] **Step 9: Commit**

```bash
git add manage.py config committee_web tests/conftest.py tests/test_django_web.py .gitignore
git commit -m "feat: Django project + HTTP views + run worker"
```

---

## Task 3: Channels WebSocket consumer

**Files:**
- Create: `committee_web/consumers.py`, `committee_web/routing.py`
- Modify: `config/asgi.py`
- Test: `tests/test_django_web.py`

- [ ] **Step 1: Create `committee_web/consumers.py`**

```python
import asyncio
import json
import queue
import threading

from channels.generic.websocket import AsyncWebsocketConsumer

from agentcore.evidence import EvidenceLedger
from agentcore.report import ReportCollector

from committee_web.run import DONE_SENTINEL, run_committee, serialize_event


class RunConsumer(AsyncWebsocketConsumer):
    """Streams a committee run over a WebSocket. The (synchronous) engine runs on
    a daemon thread that pushes Events onto a queue; this consumer drains the queue
    in the event loop and forwards each Event as JSON, then closes on the sentinel."""

    async def connect(self):
        await self.accept()
        kwargs = self.scope["url_route"]["kwargs"]
        q = queue.Queue()
        collector = ReportCollector()
        ledger = EvidenceLedger()
        threading.Thread(
            target=run_committee,
            args=(kwargs["stock_no"], kwargs["market"], q, collector, ledger),
            daemon=True,
        ).start()
        self._drain_task = asyncio.create_task(self._drain(q))

    async def _drain(self, q):
        try:
            while True:
                try:
                    item = q.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.05)
                    continue
                if item is DONE_SENTINEL:
                    break
                await self.send(text_data=json.dumps(serialize_event(item)))
        finally:
            await self.close()

    async def disconnect(self, code):
        task = getattr(self, "_drain_task", None)
        if task is not None:
            task.cancel()
```

- [ ] **Step 2: Create `committee_web/routing.py`**

```python
from django.urls import re_path

from committee_web.consumers import RunConsumer

websocket_urlpatterns = [
    re_path(r"^ws/run/(?P<market>[^/]+)/(?P<stock_no>[^/]+)$", RunConsumer.as_asgi()),
]
```

- [ ] **Step 3: Wire the websocket protocol into `config/asgi.py`** — replace the file with:

```python
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from channels.routing import ProtocolTypeRouter, URLRouter
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from committee_web.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": ASGIStaticFilesHandler(django_asgi_app),
    "websocket": URLRouter(websocket_urlpatterns),
})
```

(The `committee_web.routing` import is placed AFTER `get_asgi_application()` so the app registry is ready before the consumer module imports committee code.)

- [ ] **Step 4: Write the consumer test** — append to `tests/test_django_web.py`. It uses `asyncio.run` so no `pytest-asyncio` is needed, and routes through `URLRouter` so `url_route` kwargs are populated:

```python
def test_consumer_streams_events_then_closes(monkeypatch):
    import asyncio
    import json as _json

    from channels.routing import URLRouter
    from channels.testing import WebsocketCommunicator

    import committee_web.consumers as consumers
    from committee_web.routing import websocket_urlpatterns
    from committee_web.run import DONE_SENTINEL
    from agentcore.events import Event

    def _stub_run(stock_no, market, q, collector, ledger):
        q.put(Event(type="phase", agent="system",
                    data={"phase": "RESEARCH", "stock": stock_no}))
        q.put(DONE_SENTINEL)

    monkeypatch.setattr(consumers, "run_committee", _stub_run)

    async def _inner():
        comm = WebsocketCommunicator(URLRouter(websocket_urlpatterns), "/ws/run/us/AAPL")
        connected, _ = await comm.connect()
        assert connected
        msg = await comm.receive_from(timeout=2)
        assert _json.loads(msg)["type"] == "phase"
        await comm.disconnect()

    asyncio.run(_inner())
```

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_django_web.py -v`
Expected: all PASS (including the consumer test).

> If `WebsocketCommunicator` proves flaky in this environment (event-loop teardown), fall back to testing `_drain` directly: instantiate `RunConsumer`, set `consumer.send`/`consumer.close` to async stubs that record calls, put a `phase` Event + `DONE_SENTINEL` on a queue, and `asyncio.run(consumer._drain(q))`; assert the event was sent and `close` was awaited. Keep whichever test is green; do not leave a flaky test.

- [ ] **Step 6: Full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add committee_web/consumers.py committee_web/routing.py config/asgi.py tests/test_django_web.py
git commit -m "feat: Channels WebSocket consumer for the live debate"
```

---

## Task 4: Cutover — runserver launch, remove FastAPI

**Files:**
- Modify: `start-web.sh`, `start-web.ps1`, `requirements.txt`
- Delete: `web/server.py`, `tests/test_web.py`

- [ ] **Step 1: Point the launchers at Django.** Read `start-web.sh`, then replace its `exec` line so it runs `manage.py runserver` (keep the `HOST`/`PORT` env-var defaults already in the file):

```bash
exec "$PY" manage.py runserver "${HOST}:${PORT}"
```
Update the human-readable echo line's text if it names uvicorn. Do the same edit in `start-web.ps1` (replace the uvicorn invocation with `& $PY manage.py runserver "${HOST}:${PORT}"`).

- [ ] **Step 2: Remove the FastAPI deps** from `requirements.txt` — delete the `fastapi>=0.100` and `uvicorn>=0.24` lines.

- [ ] **Step 3: Delete the FastAPI app and its test**

```bash
git rm web/server.py tests/test_web.py
```

- [ ] **Step 4: Verify nothing imports the deleted module**

Run:
```bash
grep -rn "web.server\|from web import server\|import web.server" --include=*.py . | grep -v ".venv/" || echo "no references to web.server"
```
Expected: `no references to web.server`.

- [ ] **Step 5: Full suite + Django check**

Run:
```bash
.venv/bin/python manage.py check
.venv/bin/python -m pytest -q
```
Expected: `check` clean; suite PASS (now without `tests/test_web.py`).

- [ ] **Step 6: Manual smoke (operator — not a unit test).** Start the server and confirm it serves and auto-reloads:
```bash
.venv/bin/python manage.py runserver 8000
```
Open http://localhost:8000 — the page loads, TW/US toggle switches language, and starting an analysis streams the live debate over the WebSocket. Edit a `.py` file and confirm the console shows an auto-reload. (Controller will perform a scripted browser smoke in lieu of manual steps.)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt start-web.sh start-web.ps1
git commit -m "feat: launch via manage.py runserver; remove FastAPI app"
```

---

## Task 5: README

**Files:** Modify `README.md`

- [ ] **Step 1: Update the web-app launch command** wherever the README shows `uvicorn web.server:app` — replace with:
```bash
python manage.py runserver          # web → http://localhost:8000 (auto-reloads)
```
Keep the surrounding wording consistent with the README's tone; note it auto-reloads on code changes.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: web app now runs on Django (manage.py runserver)"
```

---

## Self-Review Notes

- **Spec coverage:** project structure + settings (T2), ASGI http+websocket (T2/T3), views/index/committee_info + `_safe_market` (T2), reports serving (T2 urls), run worker moved verbatim (T2), Channels consumer + routing (T3), deps add/remove (T1/T4), launch + auto-reload (T4), README (T5), testing — views via Django `Client`, run worker forced-market, consumer via `WebsocketCommunicator` (T2/T3). All spec sections map to a task.
- **Frontend untouched:** `web/static/*` is never edited; `app.js`'s `/ws/run/{market}/{ticker}` and `/api/committee?market=` match the Django/Channels routes. Verified by `test_index_serves_the_spa_html` and the committee_info tests.
- **Backward-compat during migration:** FastAPI (`web/server.py`, `tests/test_web.py`, deps) is kept until the final cutover (T4), so the suite is runnable at every commit.
- **Type/name consistency:** the worker is `run_committee` / sentinel `DONE_SENTINEL` / `serialize_event` / `safe_market` (run.py), imported the same way in `views.py` (`safe_market`) and `consumers.py` (`run_committee`, `DONE_SENTINEL`, `serialize_event`); the consumer test monkeypatches `committee_web.consumers.run_committee`. The `/api/committee` payload keeps the `label` field and `phase_names`/`agent_names`/`ui` keys the frontend already consumes.
- **No DB/auth:** INSTALLED_APPS omits auth/sessions/admin and MIDDLEWARE is minimal, so the Django `Client` works without migrations.
- **Out of scope (per spec):** production ASGI/Redis/collectstatic, auth/models/admin, CLI/GUI changes.
