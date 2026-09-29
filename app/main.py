"""FastAPI surface for Faultline.

The UI is a single static page, so the API stays small: everything the console
needs, and nothing it does not.
"""

from __future__ import annotations

import threading
import traceback
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.datastructures import Headers

from app import analysis, config, corpus, memory
from app.memory import engine, run_blocking

app = FastAPI(title="Faultline", version="0.1.0")

_state: dict[str, Any] = {
    "mode": None,
    "seeded": False,
    "seeding": False,
    "progress": {"stage": "idle", "pct": 0.0, "detail": ""},
    "error": None,
    "learning_curve": None,
}
_seed_lock = threading.Lock()


def _err(exc: Exception, status: int = 500) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": str(exc), "trace": traceback.format_exc()[-2500:]},
    )


# ----------------------------------------------------------------- lifecycle


@app.on_event("startup")
def _startup() -> None:
    try:
        _state["mode"] = engine.start()
        _state["error"] = None
    except Exception as exc:
        _state["error"] = f"{type(exc).__name__}: {exc}"


@app.on_event("shutdown")
def _shutdown() -> None:
    run_blocking(engine.stop)


# --------------------------------------------------------------------- status


class StateResponse(BaseModel):
    mode: str | None
    seeded: bool
    seeding: bool
    progress: dict[str, Any]
    error: str | None
    bank_incidents: str
    bank_team: str
    corpus: dict[str, int]


@app.get("/api/state")
def get_state() -> StateResponse:
    return StateResponse(
        mode=_state["mode"],
        seeded=_state["seeded"],
        seeding=_state["seeding"],
        progress=_state["progress"],
        error=_state["error"],
        bank_incidents=config.BANK_INCIDENTS,
        bank_team=config.BANK_TEAM,
        corpus={
            "incidents": corpus.incident_count(),
            "services": len(corpus.SERVICES),
            "open_actions": len(corpus.open_action_items()),
        },
    )


@app.get("/api/corpus")
def get_corpus() -> dict[str, Any]:
    return {
        "org": corpus.ORG,
        "services": corpus.SERVICES,
        "incidents": corpus.INCIDENTS,
        "open_actions": corpus.open_action_items(),
        "service_state": corpus.SERVICE_STATE,
        "live_alert": corpus.LIVE_ALERT,
        "clusters": analysis.CLUSTERS,
        "cluster_labels": analysis.CLUSTER_LABEL,
    }


# --------------------------------------------------------------------- setup


@app.post("/api/setup")
def setup(force: bool = False) -> dict[str, Any]:
    if not engine.connected:
        try:
            _state["mode"] = engine.start()
        except Exception as exc:
            return {"error": str(exc)}

    if _state["seeding"]:
        return {"status": "already running"}

    with _seed_lock:
        if _state["seeded"] and not force:
            return {"status": "already seeded"}
        _state["seeding"] = True
        _state["error"] = None

    def progress(stage: str, pct: float, detail: str) -> None:
        _state["progress"] = {"stage": stage, "pct": round(pct, 4), "detail": detail}

    def work() -> None:
        try:
            progress("checking memory", 0.0, "")
            already = (not force) and run_blocking(engine.is_seeded)
            if already:
                progress("memory already seeded", 0.5, "reusing Hindsight banks")
                run_blocking(engine.ensure_banks, False)
                run_blocking(engine.install_mental_models)
                if _state["learning_curve"] is None:
                    progress("measuring", 0.8, "")
                    _state["learning_curve"] = run_blocking(analysis.measure, engine)
                _state["seeded"] = True
                progress("ready", 1.0, "")
                return

            progress("creating banks", 0.0, "")
            run_blocking(engine.ensure_banks, force)
            run_blocking(engine.install_mental_models)
            run_blocking(engine.seed, progress)
            progress("consolidating observations", 0.98, "")
            _state["learning_curve"] = run_blocking(analysis.measure, engine)
            _state["seeded"] = True
            progress("ready", 1.0, "")
        except Exception as exc:
            _state["error"] = f"{type(exc).__name__}: {exc}"
            progress("failed", 1.0, str(exc)[:200])
        finally:
            _state["seeding"] = False

    threading.Thread(target=work, daemon=True).start()
    return {"status": "started"}


@app.get("/api/progress")
def get_progress() -> dict[str, Any]:
    return {"progress": _state["progress"], "seeding": _state["seeding"], "error": _state["error"]}


@app.get("/api/learning-curve")
async def get_learning_curve() -> dict[str, Any]:
    if _state["learning_curve"] is None:
        if not _state["seeding"]:
            try:
                _state["learning_curve"] = await memory.call(analysis.measure, engine)
            except Exception as exc:
                return {"error": str(exc)}
    return _state["learning_curve"] or {}


# --------------------------------------------------------------------- triage


class AlertIn(BaseModel):
    """An alert supplied by the caller rather than the corpus.

    The demo ships one curated alert, which is fair to be sceptical about. This
    lets somebody paste an alert from their own infrastructure and find out what
    the memory does with it. A failure mode it has never seen comes back with
    nothing in it, which is the correct answer and a useful thing to watch.
    """

    service: str
    alert_text: str
    title: str | None = None
    severity: str | None = None
    raw_evidence: list[str] | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "service": "checkout-web",
                "severity": "SEV1",
                "title": "Deadlocks on ledger_entries",
                "alert_text": "[CRITICAL] checkout-web checkout_error_rate=0.38 over 5m\n  error: Postgres ERROR: deadlock detected on ledger_entries\n  deadlocks: 37 in 5m",
            }
        }
    }


class TriageRequest(BaseModel):
    with_memory: bool = True
    alert: AlertIn | None = None


@app.post("/api/triage")
async def triage(req: TriageRequest) -> Any:
    """Triage an alert.

    Omit `alert` to use the curated demo alert. Supply one to run the same
    pipeline over an alert the memory has never seen.
    """
    if not engine.connected:
        return _err(RuntimeError("memory engine not connected"), 503)

    if req.alert is None:
        alert = dict(corpus.LIVE_ALERT)
    else:
        a = req.alert
        alert = {
            "service": a.service,
            "alert_text": a.alert_text,
            "title": a.title or "Supplied alert",
            "severity": a.severity or "SEV?",
            "raw_evidence": a.raw_evidence or [],
            "source_label": "supplied by caller",
            "received": "now",
        }

    try:
        result = await memory.call(engine.triage, alert, req.with_memory)
        return {
            "alert": alert,
            "payload": result.payload,
            "recalled": result.recalled,
            "mental_models": result.mental_models,
            "trace": result.trace,
            "baseline": result.baseline,
            "with_memory": req.with_memory,
        }
    except Exception as exc:
        return _err(exc)


@app.get("/api/mental-models")
async def mental_models() -> dict[str, Any]:
    if not engine.connected:
        return {"error": "not connected"}
    try:
        return await memory.call(engine._mental_model_text)
    except Exception as exc:
        return {"error": str(exc)}


# --------------------------------------------------------------------- resolve


class ResolveRequest(BaseModel):
    root_cause: str | None = None
    resolution: str | None = None
    runbook: str | None = None
    action_items: list[dict[str, Any]] | None = None


@app.post("/api/resolve")
async def resolve(req: ResolveRequest) -> dict[str, Any]:
    """Retain the live incident, then let consolidation strengthen the fingerprints."""
    if not engine.connected:
        return _err(RuntimeError("memory engine not connected"), 503)
    try:
        return await memory.call(_do_resolve, req)
    except Exception as exc:
        return _err(exc)


def _do_resolve(req: ResolveRequest) -> dict[str, Any]:
    """Builds and retains the postmortem for the live incident.

    Runs on the memory thread via memory.call, so it must not touch anything
    that is not defined here.
    """
    resolution = corpus.LIVE_RESOLUTION
    root_cause = req.root_cause or resolution["root_cause"]
    resolution_text = req.resolution or resolution["resolution"]
    runbook = req.runbook or resolution["runbook"]
    actions = req.action_items or resolution["action_items"]

    alert = corpus.LIVE_ALERT
    record = "\n".join(
        [
            f"INCIDENT {alert['alert_id']} — {alert['title']}",
            f"Service: {alert['service']}  Severity: {alert['severity']}  "
            f"Detected by: {alert['source']}",
            f"Received: {alert['received']}",
            "",
            "ALERT AS IT FIRED:",
            alert["alert_text"],
            "",
            "EVIDENCE:",
            *alert["raw_evidence"],
            "",
            f"ROOT CAUSE: {root_cause}",
            f"RESOLUTION: {resolution_text}",
            f"RUNBOOK USED: {runbook}",
            "",
            "POSTMORTEM ACTION ITEMS:",
            *[
                f"  [{'COMPLETED' if a['status'] == 'done' else 'NEVER COMPLETED'}] "
                f"{a['text']} (owner: {a['owner']})"
                + (f" — {a['note']}" if a.get("note") else "")
                for a in actions
            ],
        ]
    )
    engine.client.retain(
        bank_id=config.BANK_INCIDENTS,
        content=record,
        context=f"live incident {alert['alert_id']} ({alert['service']})",
        metadata={
            "incident_id": alert["alert_id"],
            "service": alert["service"],
            "severity": alert["severity"],
            "kind": "postmortem",
        },
        tags=["iam", "sts", "auth", "sev2", "payout-worker", "live"],
    )
    for act in actions:
        if act.get("status") != "done":
            engine.client.retain(
                bank_id=config.BANK_TEAM,
                content=(
                    f"OPEN REMEDIATION ACTION from incident {alert['alert_id']} on service "
                    f"{alert['service']}, raised {alert['received']}.\n"
                    f"Action: {act['text']}\nOwner: {act['owner']}\n"
                    f"Status: never completed.\nReviewer note: {act.get('note', '')}"
                ),
                context="postmortem action item",
                metadata={
                    "incident_id": alert["alert_id"],
                    "service": alert["service"],
                    "owner": act["owner"],
                    "kind": "action_item",
                },
                tags=["action-item", alert["service"]],
            )
    engine.refresh_mental_models()
    return {"status": "retained", "incident_id": alert["alert_id"]}


# --------------------------------------------------------------------- memory


@app.get("/api/memories")
async def memories(limit: int = 60, q: str | None = None) -> dict[str, Any]:
    """Raw memory inspection, so the demo can show that the memories are real."""
    if not engine.connected:
        return {"error": "not connected"}
    try:
        if q:
            res = await memory.call(
                engine.client.recall,
                bank_id=config.BANK_INCIDENTS, query=q, budget="mid", max_tokens=3000
            )
            return {
                "mode": "recall",
                "query": q,
                "items": [
                    {
                        "text": getattr(i, "text", "") or "",
                        "type": getattr(i, "type", "") or "",
                        "score": getattr(i, "score", None),
                    }
                    for i in (getattr(res, "results", None) or [])[:limit]
                ],
            }
        res = await memory.call(
            engine.client.list_memories,
            bank_id=config.BANK_INCIDENTS, limit=limit, offset=0,
        )
        items = getattr(res, "items", None) or getattr(res, "memories", None) or []
        return {
            "mode": "list",
            "items": [
                {
                    "text": getattr(i, "text", None) or str(i),
                    "type": getattr(i, "type", "") or "",
                }
                for i in items
            ],
        }
    except Exception as exc:
        return {"error": str(exc)}


# ------------------------------------------------------------------- pages
# The landing page is the root, because a visitor should get the pitch first.
# The console lives at /console, and ?autotriage=1 there runs the demo on load.
#
# Every response here is marked no-store. This is a demo that gets edited right up
# to the minute it is shown, and a browser holding a cached stylesheet means a
# judge sees yesterday's page. That is not a theoretical risk: it happened during
# this build, twice.


class NoCacheFileResponse(FileResponse):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.headers["Cache-Control"] = "no-store, must-revalidate"
        self.headers["Pragma"] = "no-cache"
        self.headers["Expires"] = "0"


class NoCacheStatic(StaticFiles):
    """Static files that revalidate on every request.

    StaticFiles otherwise sends an ETag and lets the browser reuse a 304, which
    is correct for production and wrong for a project being edited live.
    """

    def file_response(self, *args: Any, **kwargs: Any) -> FileResponse:
        resp: FileResponse = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-store, must-revalidate"
        return resp


@app.get("/", include_in_schema=False)
def landing() -> NoCacheFileResponse:
    return NoCacheFileResponse(config.WEB_DIR / "landing.html")


@app.get("/console", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def console() -> NoCacheFileResponse:
    return NoCacheFileResponse(config.WEB_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> NoCacheFileResponse:
    # A single glyph, served rather than invented as a binary asset. See DESIGN.md:
    # invented marks are provisional until a human confirms one.
    return NoCacheFileResponse(config.WEB_DIR / "favicon.svg", media_type="image/svg+xml")


app.mount("/static", NoCacheStatic(directory=config.WEB_DIR), name="static")

# The written documentation, served so the links on the landing page resolve.
# /docs stays FastAPI's own generated API reference.
app.mount("/guide", StaticFiles(directory=config.DOCS_DIR, html=True), name="guide")


@app.get("/guide", include_in_schema=False)
def guide_index() -> FileResponse:
    """Directory listings do not render, so point it at the entry page."""
    return NoCacheFileResponse(config.DOCS_DIR / "README.md", media_type="text/markdown")
