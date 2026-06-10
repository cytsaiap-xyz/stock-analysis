# Django + Channels Web Migration — Design Spec

**Date:** 2026-06-10
**Status:** Approved (pending spec review)
**Topic:** Replace the FastAPI web app with a Django + Channels app (auto-reload via `runserver`).

## Goal

Replace the FastAPI/uvicorn web layer with a **Django + Channels** application that
serves the same UI and the same live-debate stream. The motivation is developer
ergonomics: `python manage.py runserver` auto-reloads on any code change, so the
server need not be restarted manually. The committee engine, the CLI, and the
desktop GUI are untouched.

## Decisions (locked)

1. **Streaming:** WebSocket via **Django Channels** (faithful to today's WebSocket;
   `app.js` stays a WebSocket client).
2. **FastAPI is replaced**, not kept alongside — `web/server.py`, `fastapi`, and
   `uvicorn` are removed; `django`, `channels`, `daphne` are added.
3. The synchronous committee engine is reused as-is via the existing
   thread-worker pattern (no async rewrite of the engine).
4. The existing frontend (`web/static/app.js`, `index.html`, `style.css`) is kept
   and served by Django; `app.js` is unchanged (same WS path + `/api/committee`).

## Project structure

```
manage.py                       Django entrypoint
config/                         Django project package
  __init__.py
  settings.py                   minimal: staticfiles + channels; DEBUG=True; sqlite (no models)
  urls.py                       GET / , GET /api/committee , /reports/<path>
  asgi.py                       ProtocolTypeRouter: http -> Django, websocket -> Channels
committee_web/                  Django app
  __init__.py
  apps.py
  views.py                      index(), committee_info()  (thin; reuse get_profile)
  run.py                        _run_committee thread-worker (moved from web/server.py)
  consumers.py                  RunConsumer(AsyncWebsocketConsumer) — the live debate
  routing.py                    websocket_urlpatterns: ws/run/<market>/<stock_no> -> RunConsumer
web/static/                     KEPT: app.js, index.html, style.css (served by Django staticfiles)
```

`web/server.py` is deleted. `web/static/` stays as the static-files source.

## Components

### 1. ASGI entrypoint — `config/asgi.py`

A `ProtocolTypeRouter` routes `http` to Django's ASGI app and `websocket` through
Channels' `AuthMiddlewareStack` (or a bare `URLRouter`, since there is no auth) to
`committee_web.routing.websocket_urlpatterns`. `DJANGO_SETTINGS_MODULE=config.settings`.

### 2. Settings — `config/settings.py`

Minimal, dev-oriented:
- `INSTALLED_APPS`: `django.contrib.staticfiles`, `channels`, `committee_web`.
- `ASGI_APPLICATION = "config.asgi.application"`.
- `CHANNEL_LAYERS`: in-memory (`channels.layers.InMemoryChannelLayer`). No Redis —
  the consumer owns its own queue; the channel layer is included only for
  completeness/future cross-consumer needs.
- `STATIC_URL = "/static/"`, `STATICFILES_DIRS = [web/static]`.
- `DATABASES`: a sqlite default (Django requires the key; no models/migrations are
  defined by our apps, so no DB is actually exercised).
- `DEBUG = True`, `ALLOWED_HOSTS = ["*"]`, a dev `SECRET_KEY` read from env with a
  hardcoded dev fallback, `TEMPLATES` configured for app template dirs.
- `load_dotenv()` is invoked (committee/config already does this on import; settings
  also call it defensively so env is present before the engine imports).

### 3. HTTP views — `committee_web/views.py`

- `index(request)` → returns `web/static/index.html` (FileResponse or a TemplateView
  reading that file). No templating logic needed; the page is static and JS-driven.
- `committee_info(request)` → reads `?market=` (default `tw`), normalizes via
  `_safe_market`, builds the payload from `get_profile(market)`:
  `{market, research[], challengers[], chair, verifier, phase_names, agent_names,
  reflection_passes, ui}` (identical to the FastAPI version) and returns
  `JsonResponse`. The per-agent dict keeps the `label` field (not `zh`).
- `_safe_market(market)` returns `market if market in ("tw","us") else "tw"`.

### 4. Reports serving

`reports/<path>.html` is served in dev via `django.views.static.serve` (or a
`re_path` to a static serve view) rooted at the `reports/` directory, so the "open
report" link (`/reports/<file>`) works. The report worker writes to `reports/` as
today.

### 5. URL routing — `config/urls.py`

- `path("", views.index)`
- `path("api/committee", views.committee_info)`
- `re_path(r"^reports/(?P<path>.*)$", serve, {"document_root": REPORTS_DIR})`
- staticfiles are served automatically by `runserver` in DEBUG.

### 6. WebSocket routing — `committee_web/routing.py`

```python
websocket_urlpatterns = [
    re_path(r"^ws/run/(?P<market>[^/]+)/(?P<stock_no>[^/]+)$", RunConsumer.as_asgi()),
]
```

Same path shape as today (`/ws/run/{market}/{stock_no}`), so `app.js` is unchanged.

### 7. The run worker — `committee_web/run.py`

`_run_committee(stock_no, market, q, collector, ledger)` moves **verbatim** from
`web/server.py` (logic unchanged): subscribe a queue + collector to the EventBus,
build `get_profile(_safe_market(market))`, run the Orchestrator with all 6
templates + `reflection_passes`, `save_report(..., twse=profile.client,
labels=profile.labels)`, emit a `report` event, and push a `_DONE_SENTINEL` in a
`finally`. Exceptions become an `error` event (run never crashes the socket).
`serialize_event(e)` (the Event→dict helper) moves here too.

### 8. The Channels consumer — `committee_web/consumers.py`

`RunConsumer(AsyncWebsocketConsumer)`:
- `connect`: `await self.accept()`; read `self.scope["url_route"]["kwargs"]`
  (`market`, `stock_no`); create a `queue.Queue`, `ReportCollector`, `EvidenceLedger`;
  start `_run_committee` on a daemon thread; then loop: drain the queue and
  `await self.send(text_data=json.dumps(serialize_event(item)))` for each event,
  `await asyncio.sleep(0)` / short sleep when empty, until the `_DONE_SENTINEL` is
  seen, then `await self.close()`. (Mirrors the FastAPI `await`-drain loop; the
  thread→async bridge is a polled `queue.Queue`, exactly as today.)
- `disconnect`: best-effort stop (the worker is a daemon thread; the drain loop
  exits when the socket closes).

### 9. Launch + auto-reload

`python manage.py runserver [host:port]` runs Channels' daphne-backed dev server,
which **auto-reloads on code change in DEBUG** — the project goal. `start-web.sh` is
updated to call `manage.py runserver` (keeping the `HOST`/`PORT` env overrides).
`start-web.ps1` updated to match.

## Dependencies

- **Add:** `django` (5.x), `channels`, `daphne` (provides the ASGI `runserver`).
- **Remove:** `fastapi`, `uvicorn`.
- Unchanged: `openai`, `requests`, `pandas`, `python-dotenv`, `ddgs`, `yfinance`,
  `pytest`. (`watchfiles` is not required — Django has its own autoreloader.)

## Testing

- `committee_web/views.py` — Django `Client` (`django.test.Client`): `GET
  /api/committee?market=us` returns English roster + `ui.title`; `market=tw` returns
  Chinese; unknown market falls back to TW. Ports the existing assertions.
- `committee_web/run.py` — `_run_committee("2330", "us", q, ...)` with monkeypatched
  `Orchestrator`/`LLMClient`/`save_report`/`build_registry` asserts the forced
  market builds a `UsClient` (ported from the current `test_web.py`).
- `committee_web/consumers.py` — a Channels `WebsocketCommunicator` test with the run
  worker stubbed to emit a couple of events + the sentinel; asserts the client
  receives them and the socket closes.
- Tests need Django configured: a `tests/conftest.py` (or pytest-django) sets
  `DJANGO_SETTINGS_MODULE=config.settings` and calls `django.setup()`. Use plain
  `django.test` + `channels.testing` to avoid adding `pytest-django` if feasible; if
  the async consumer test needs it, add `pytest-asyncio`/`pytest-django` as a test
  dep.
- `tests/test_web.py` (FastAPI) is removed; replaced by `tests/test_django_web.py`.
- The rest of the suite (engine, markets, gui, llm, report, …) is unchanged and must
  stay green.

## What stays the same / is removed

**Unchanged:** `agentcore/`, `committee/` (engine, markets, data, report), `main.py`
(CLI), `gui.py` (desktop GUI), `web/static/*` (frontend), the event protocol, the
TW/US switch, the report builder.

**Removed:** `web/server.py`, `fastapi`, `uvicorn`.

## Risks / notes

- **Channels async↔sync bridge.** The engine is sync and runs on a daemon thread; the
  consumer polls a `queue.Queue`. This is the same pattern proven in the FastAPI
  version, so risk is low; the only new surface is the consumer's async drain loop.
- **Test harness.** Django needs settings configured before import; the consumer test
  may pull in `pytest-django`/`pytest-asyncio`. Kept out of scope creep by testing
  the views/worker directly and keeping the consumer test minimal.
- **No DB/auth/admin.** Deliberately omitted; this is a thin streaming app, not a CRUD
  site. If those are wanted later they are additive.

## Out of scope (follow-on)

- Production deployment (a real ASGI server, Redis channel layer, `collectstatic`).
- Auth, database models, Django admin.
- Any change to the CLI or desktop GUI.
