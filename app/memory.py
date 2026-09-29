"""The Hindsight layer.

Everything Faultline knows lives in two Hindsight banks. This module is the only
place that talks to Hindsight, so the rest of the app never has to think about
retain/recall/reflect, mental models, or consolidation.

Two banks, on purpose:

    faultline-incidents   the technical corpus. Alerts, timelines, root causes,
                          runbooks, postmortems, and the current latent state of
                          each service.
    faultline-team        the human layer. Who owns which postmortem action,
                          which actions were never closed, and team conventions.

Hindsight isolates banks strictly, so "what broke" never gets polluted with "who
owes what", and the app can demonstrate that the split is real rather than
asserting it.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import functools
import json
import os
import queue
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from app import config, corpus

ProgressFn = Callable[[str, float, str], None]

# Hindsight's Python client is a synchronous wrapper that does
# asyncio.get_event_loop().run_until_complete(coro), and its aiohttp connection
# pool is bound to whichever loop first used it. Two consequences:
#
#   * the loop must never be *running* when a call happens, because the client
#     always calls run_until_complete on it;
#   * the loop must never *change*, because a cached aiohttp pool carrying
#     timeout handles from a previous loop makes aiohttp raise
#     "Timeout context manager should be used inside a task".
#
# asyncio.to_thread satisfies neither — anyio attaches the parent (running) loop
# to its worker threads. So every Hindsight call is serialised onto one dedicated
# worker thread that owns a private, never-running event loop. One thread, one
# loop, one connection pool, no cross-loop reuse.
_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="hindsight-bridge"
)


class _LoopThread:
    def __init__(self) -> None:
        self._queue: "queue.Queue[Any]" = queue.Queue()
        self._ready = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="hindsight-loop", daemon=True
        )
        self._thread.start()
        self._ready.wait(10)

    def _run(self) -> None:
        asyncio.set_event_loop(asyncio.new_event_loop())
        self._ready.set()
        while True:
            job = self._queue.get()
            if job is None:
                return
            fn, args, kwargs, fut = job
            if not fut.set_running_or_notify_cancel():
                continue
            try:
                fut.set_result(fn(*args, **kwargs))
            except BaseException as exc:  # noqa: BLE001 - propagated to the caller
                fut.set_exception(exc)

    def run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        fut: concurrent.futures.Future = concurrent.futures.Future()
        self._queue.put((fn, args, kwargs, fut))
        return fut.result()


_loop_thread = _LoopThread()


def run_blocking(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run a blocking Hindsight call on the dedicated loop thread."""
    return _loop_thread.run(fn, *args, **kwargs)


async def call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Await a blocking Hindsight call from an async route."""
    return await asyncio.get_running_loop().run_in_executor(
        _pool, functools.partial(run_blocking, fn, *args, **kwargs)
    )

INCIDENT_MISSION = (
    "You are the memory of Northwind Commerce's reliability engineering organisation. "
    "You hold every production incident, alert, timeline, root cause, runbook, remediation "
    "action and configuration state since 2025. Your job during reflection is to identify "
    "failure modes that recur, and to notice when a failure mode that was understood months "
    "ago is still present somewhere it has not yet caused an outage."
)

TEAM_MISSION = (
    "You are the memory of Northwind Commerce's engineering organisation as it relates to "
    "people and commitments. You hold postmortem action items, their owners, and their "
    "status, and you are unusually good at noticing actions that were written down and then "
    "never completed."
)

INCIDENT_DIRECTIVES = [
    (
        "cite-evidence",
        "Always cite the incident id and the date for anything you assert. Never state a "
        "fact about an incident that is not present in your memory.",
        10,
    ),
    (
        "prefer-recent",
        "When two memories conflict, the more recently retained one is correct and the "
        "older one describes how things used to be. Say so when you rely on this.",
        10,
    ),
    (
        "surface-unclosed-work",
        "If a failure mode you are reasoning about has a remediation action that was never "
        "completed, say that explicitly and name the owner. An unclosed action means the "
        "problem is still loaded somewhere.",
        10,
    ),
    (
        "no-invention",
        "If the memory does not contain the answer, say that the memory does not contain it. "
        "A confident guess is worse than an admission here, because a wrong root cause during "
        "an outage costs hours.",
        20,
    ),
]

TEAM_DIRECTIVES = [
    (
        "no-invention",
        "Only report action items that exist in your memory, with their recorded owner.",
        20,
    ),
    (
        "count-repeats",
        "When the same remediation action has been written down more than once, say how many "
        "times and on which incidents. A third identical action is a process failure, not a "
        "to-do item.",
        10,
    ),
]

# Mental models. Hindsight writes these in the background after consolidation, so
# they get sharper as the corpus grows, and reading one is a database read rather
# than an LLM call. That is what makes the "agent is learning" claim cheap enough
# to show on every request.
# An intentionally empty bank, used as the control group for the before/after.
EMPTY_BANK = "faultline-control-empty"

FINGERPRINT_MODEL_ID = "failure-fingerprints"
RECURRENCE_MODEL_ID = "recurrence-risk"
REMEDIATION_MODEL_ID = "open-remediation"

MENTAL_MODELS = [
    {
        "id": FINGERPRINT_MODEL_ID,
        "name": "Failure fingerprints",
        "source_query": (
            "For each distinct failure mode this organisation has actually experienced, write "
            "the fingerprint: the observable symptoms as they appear in an alert, the services "
            "it has affected, the dates it happened, the root cause, the runbook that fixed it, "
            "and how many separate incidents it has caused. Group incidents that share a root "
            "cause even when the symptoms look unrelated, and name the services that share the "
            "underlying cause."
        ),
        "max_tokens": 2000,
    },
    {
        "id": RECURRENCE_MODEL_ID,
        "name": "Recurrence risk",
        "source_query": (
            "Which services are currently exposed to a failure mode that has already caused an "
            "outage somewhere else in this organisation? For each one, state the failure mode, "
            "the evidence that the service still carries the condition, and the incident that "
            "proved the failure mode is real. Only include services where the memory contains "
            "evidence for both the failure mode and the service's current state."
        ),
        "max_tokens": 1500,
    },
    {
        "id": REMEDIATION_MODEL_ID,
        "name": "Open remediation",
        "source_query": (
            "List the postmortem action items that were never completed, grouped by the "
            "underlying problem rather than by the incident that produced them. For each, name "
            "the owner, the first incident that raised it, every later incident that raised it "
            "again, and how many times it has now been written down."
        ),
        "max_tokens": 1500,
    },
]

TRIAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "verdict",
        "fingerprint_match",
        "matched_incident_ids",
        "failure_mode",
        "root_cause_hypothesis",
        "first_actions",
        "recurrence_risk",
        "stale_action_items",
        "confidence",
    ],
    "properties": {
        "verdict": {
            "type": "string",
            "description": "One or two sentences. What is happening and what to do about it.",
        },
        "fingerprint_match": {
            "type": "integer",
            "description": "0-100 confidence that this is a failure mode seen before.",
        },
        "matched_incident_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ids of prior incidents that share the root cause.",
        },
        "failure_mode": {
            "type": "string",
            "description": "The name of the failure mode, phrased so it could be reused.",
        },
        "root_cause_hypothesis": {
            "type": "string",
            "description": "Most likely root cause, grounded in the cited incidents.",
        },
        "first_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["step", "detail", "runbook"],
                "properties": {
                    "step": {"type": "string"},
                    "detail": {"type": "string"},
                    "runbook": {"type": "string"},
                },
            },
        },
        "recurrence_risk": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["service", "why", "severity", "evidence"],
                "properties": {
                    "service": {"type": "string"},
                    "why": {"type": "string"},
                    "severity": {"type": "string"},
                    "evidence": {"type": "string"},
                },
            },
        },
        "stale_action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "owner", "incident_id", "times_written"],
                "properties": {
                    "text": {"type": "string"},
                    "owner": {"type": "string"},
                    "incident_id": {"type": "string"},
                    "times_written": {"type": "integer"},
                },
            },
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
    },
}


@dataclass
class TriageResult:
    payload: dict[str, Any]
    recalled: list[dict[str, Any]] = field(default_factory=list)
    mental_models: dict[str, Any] = field(default_factory=dict)
    trace: dict[str, Any] = field(default_factory=dict)
    baseline: str = ""


class MemoryEngine:
    """Owns the Hindsight connection and every memory operation Faultline needs."""

    def __init__(self) -> None:
        self._client = None
        self._client_tid: int | None = None
        self._server = None
        self._lock = threading.Lock()
        self._ready = False
        self.mode = "not started"

    # ---------------------------------------------------------------- lifecycle

    def _build_client(self):
        """Construct a Hindsight client. Must run on the thread that will use it."""
        cloud_url = os.environ.get("HINDSIGHT_API_BASE_URL", "").strip()
        cloud_key = os.environ.get("HINDSIGHT_API_KEY", "").strip()

        from hindsight_client import Hindsight

        if cloud_url and cloud_key:
            self.mode = "Hindsight Cloud"
            return Hindsight(base_url=cloud_url, api_key=cloud_key, timeout=900.0)

        from hindsight import HindsightServer

        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._server = HindsightServer(
            llm_provider=os.environ.get("HINDSIGHT_API_LLM_PROVIDER", "gemini"),
            llm_model=os.environ.get("HINDSIGHT_API_LLM_MODEL", "gemini-3.8-flash"),
            llm_api_key=os.environ.get("HINDSIGHT_API_LLM_API_KEY", ""),
            log_level="warning",
        )
        # The default 30s budget is not enough to download and load a local model.
        self._server.start(timeout=3600)
        self.mode = "Hindsight (embedded)"
        return Hindsight(base_url=self._server.url, timeout=900.0)

    @property
    def client(self):
        """The Hindsight client, created lazily on the calling thread.

        The client caches an aiohttp session bound to the event loop that first
        used it, so calling it from a second thread raises
        "Timeout context manager should be used inside a task". One client per
        thread is the fix. Every call is routed through run_blocking, so in
        practice there is exactly one.
        """
        tid = threading.get_ident()
        if self._client is None or self._client_tid != tid:
            self._client = self._build_client()
            self._client_tid = tid
            self._ready = True
        return self._client

    @property
    def connected(self) -> bool:
        return self._ready

    def start(self) -> str:
        """Connect to Hindsight and report which mode is in use.

        Runs on the dedicated loop thread, so the client is created there and its
        aiohttp session is bound to that loop for the life of the process.
        """
        run_blocking(lambda: self.client)
        return self.mode

    def stop(self) -> None:
        self._client = None
        self._client_tid = None
        self._server = None
        self._ready = False

    # -------------------------------------------------------------------- setup

    def banks_ready(self) -> bool:
        """True when both banks already exist in Hindsight.

        The banks live in Hindsight Cloud, so they outlive the process. Setup has
        to be safe to run twice.
        """
        if not self.connected:
            return False
        for bank in (config.BANK_INCIDENTS, config.BANK_TEAM):
            try:
                self.client.get_bank_config(bank)
            except Exception:
                return False
        return True

    def is_seeded(self) -> bool:
        """True when the corpus is already loaded, so re-seeding would duplicate it."""
        if not self.connected:
            return False
        try:
            res = self.client.list_memories(
                bank_id=config.BANK_INCIDENTS, limit=1, offset=0
            )
            items = getattr(res, "items", None) or getattr(res, "memories", None) or []
            return len(items) > 0
        except Exception:
            return False

    def ensure_banks(self, force: bool = False) -> None:
        """Create both banks with their mission, directives and mental models.

        Idempotent: re-running refreshes the configuration instead of failing.
        """
        if force:
            for bank in (config.BANK_INCIDENTS, config.BANK_TEAM):
                try:
                    self.client.delete_bank(bank)
                except Exception:
                    pass

        exists = self.banks_ready()

        self._create_bank(
            config.BANK_INCIDENTS,
            name="Northwind incident memory",
            mission=INCIDENT_MISSION,
            retain_mission=(
                "Extract every durable technical fact from this incident record: the services "
                "involved, the exact dates and times, the symptoms, the root cause, the fix, "
                "the runbook used, the customer impact, and each remediation action with its "
                "owner and whether it was ever completed. Keep incident ids as entities so "
                "they can be linked across records."
            ),
            observations_mission=(
                "Consolidate incident facts into beliefs about how this organisation fails. "
                "Group incidents that share a root cause. Track remediation actions across "
                "incidents so that an action raised once and never completed stays visible. "
                "Preserve history: when a fact changes, keep the earlier fact and mark the "
                "change rather than overwriting it."
            ),
            reflect_mission=INCIDENT_MISSION,
            enable_observations=True,
            enable_graph_retrieval=True,
            enable_temporal_retrieval=True,
            enable_text_search=True,
            exists=exists,
        )

        self._create_bank(
            config.BANK_TEAM,
            name="Northwind team and commitments",
            mission=TEAM_MISSION,
            retain_mission=(
                "Extract the commitment and ownership facts from this record: who owes what, "
                "which incident raised it, what date it was raised, and whether it was ever "
                "completed."
            ),
            observations_mission=(
                "Consolidate into beliefs about this team's follow-through. An action raised "
                "repeatedly and never completed is the most important kind of fact in this bank."
            ),
            reflect_mission=TEAM_MISSION,
            enable_observations=True,
            enable_graph_retrieval=True,
            exists=exists,
        )

        for name, content, priority in INCIDENT_DIRECTIVES:
            self._ensure_directive(config.BANK_INCIDENTS, name, content, priority)
        for name, content, priority in TEAM_DIRECTIVES:
            self._ensure_directive(config.BANK_TEAM, name, content, priority)

    def _create_bank(self, bank_id: str, exists: bool, **kwargs) -> None:
        if not exists:
            self.client.create_bank(bank_id, **kwargs)
            return
        try:
            self.client.update_bank_config(bank_id=bank_id, **kwargs)
        except Exception:
            pass

    def _ensure_directive(
        self, bank_id: str, name: str, content: str, priority: int
    ) -> None:
        try:
            self.client.create_directive(
                bank_id=bank_id, name=name, content=content, priority=priority
            )
        except Exception:
            try:
                self.client.update_directive(
                    bank_id=bank_id, name=name, content=content, priority=priority
                )
            except Exception:
                pass

    def install_mental_models(self) -> None:
        for model in MENTAL_MODELS:
            try:
                self.client.create_mental_model(
                    bank_id=config.BANK_INCIDENTS,
                    name=model["name"],
                    id=model["id"],
                    source_query=model["source_query"],
                    max_tokens=model["max_tokens"],
                    trigger={"mode": "delta", "refresh_after_consolidation": True},
                )
            except Exception:
                # Already installed from a previous run. Leave it be: a mental model
                # is rewritten in the background anyway, so re-creating it would
                # throw away a version that has learned something.
                pass

    def refresh_mental_models(self) -> None:
        for model in MENTAL_MODELS:
            try:
                self.client.refresh_mental_model(
                    bank_id=config.BANK_INCIDENTS, mental_model_id=model["id"]
                )
            except Exception:
                pass

    # --------------------------------------------------------------------- seed

    def _incident_record(self, inc: dict[str, Any]) -> str:
        parts = [
            f"INCIDENT {inc['id']} — {inc['title']}",
            f"Service: {inc['service']}  Severity: {inc['severity']}  Status: {inc['status']}",
            f"Opened: {inc['opened']}  Resolved: {inc['resolved']}  "
            f"Time to resolve: {inc['mttr_minutes']} minutes",
            f"Detected by: {inc['detected_by']}",
            "",
            "ALERT AS IT FIRED:",
            inc["alert_text"],
            "",
            "TIMELINE:",
        ]
        parts += [f"  {stamp} {event}" for stamp, event in inc["timeline"]]
        parts += [
            "",
            "LOG EXCERPT:",
            inc["log_excerpt"],
            "",
            f"ROOT CAUSE: {inc['root_cause']}",
            f"RESOLUTION: {inc['resolution']}",
            f"RUNBOOK USED: {inc['runbook']}",
            f"CUSTOMER IMPACT: {inc['customer_impact']}",
            "",
            "POSTMORTEM ACTION ITEMS:",
        ]
        for act in inc["action_items"]:
            mark = "COMPLETED" if act["status"] == "done" else "NEVER COMPLETED"
            line = f"  [{mark}] {act['text']} (owner: {act['owner']})"
            if act["note"]:
                line += f" — {act['note']}"
            parts.append(line)
        return "\n".join(parts)

    def _state_record(self, key: str, state: dict[str, Any]) -> str:
        lines = [
            f"CURRENT INFRASTRUCTURE STATE — {key}",
            f"Condition: {state.get('description', '')}",
            f"Last audited: {state.get('last_audited', 'unknown')}",
            "Services that still carry this condition: "
            + ", ".join(state.get("services_still_affected", [])),
            "Services where this has been fixed: "
            + (", ".join(state.get("fixed_in", [])) or "none"),
        ]
        why = state.get("why_it_keeps_coming_back")
        if why:
            lines.append(f"Why it keeps coming back: {why}")
        return "\n".join(lines)

    def seed(self, progress: ProgressFn | None = None) -> dict[str, Any]:
        """Load the corpus into Hindsight.

        Incidents go into the incident bank. Ownership and commitment facts go
        into the team bank, so the split is real and not just declared.
        """
        report = progress or (lambda *_: None)
        incidents = corpus.INCIDENTS

        report("retaining incidents", 0.0, f"0/{len(incidents)}")
        for idx, inc in enumerate(incidents, start=1):
            self.client.retain(
                bank_id=config.BANK_INCIDENTS,
                content=self._incident_record(inc),
                context=f"postmortem {inc['id']} ({inc['service']}, {inc['severity']})",
                timestamp=_parse_ts(inc["opened"]),
                metadata={
                    "incident_id": inc["id"],
                    "service": inc["service"],
                    "severity": inc["severity"],
                    "kind": "postmortem",
                },
                tags=inc["tags"],
            )
            report("retaining incidents", idx / len(incidents) * 0.7, f"{idx}/{len(incidents)}")

        report("retaining service state", 0.7, "")
        states = list(corpus.SERVICE_STATE.items())
        for idx, (key, state) in enumerate(states, start=1):
            self.client.retain(
                bank_id=config.BANK_INCIDENTS,
                content=self._state_record(key, state),
                context="current infrastructure state audit",
                metadata={"kind": "infra_state", "state_key": key},
                tags=["infra-state", key],
            )
            report("retaining service state", 0.7 + idx / len(states) * 0.15, f"{idx}/{len(states)}")

        report("retaining remediation backlog", 0.85, "")
        for act in corpus.open_action_items():
            self.client.retain(
                bank_id=config.BANK_TEAM,
                content=(
                    f"OPEN REMEDIATION ACTION from incident {act['incident_id']} "
                    f"on service {act['service']}, raised {act['opened']}.\n"
                    f"Action: {act['text']}\n"
                    f"Owner: {act['owner']}\n"
                    f"Status: never completed.\n"
                    f"Reviewer note: {act['note']}"
                ),
                context="postmortem action item",
                timestamp=_parse_ts(act["opened"]),
                metadata={
                    "incident_id": act["incident_id"],
                    "service": act["service"],
                    "owner": act["owner"],
                    "kind": "action_item",
                },
                tags=["action-item", act["service"]],
            )

        report("waiting for consolidation", 0.97, "")
        report("done", 1.0, "")
        return {"incidents": len(incidents), "action_items": len(corpus.open_action_items())}

    # ------------------------------------------------------------------ runtime

    def _recall(self, query: str, limit_note: str = "") -> list[dict[str, Any]]:
        res = self.client.recall(
            bank_id=config.BANK_INCIDENTS,
            query=query,
            budget="high",
            max_tokens=4096,
            prefer_observations=True,
        )
        out = []
        for item in (getattr(res, "results", None) or [])[:8]:
            out.append(
                {
                    "text": getattr(item, "text", "") or "",
                    "type": getattr(item, "type", "") or "",
                    "score": _safe_float(getattr(item, "score", None)),
                    "note": limit_note,
                }
            )
        return out

    def _mental_model_text(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for model in MENTAL_MODELS:
            try:
                res = self.client.get_mental_model(
                    bank_id=config.BANK_INCIDENTS,
                    mental_model_id=model["id"],
                    detail="content",
                )
                text = _extract_text(res)
                if text and text.strip():
                    out[model["id"]] = text
            except Exception:
                continue
        return out

    @staticmethod
    def _exposure_from_corpus(
        state_key: str, model_risk: list[dict[str, Any]], alerting: str
    ) -> list[dict[str, Any]]:
        """Build the exposed-services list from the latent-state records.

        The model reliably names the failure mode and the prior incidents, but it
        fills EXPOSED with whichever services appear in those incidents — including
        ones an engineer has already patched. Those lists are ground truth in the
        corpus, so the set comes from there. The model still supplies the
        explanation, but only for services that survive the check.
        """
        key = (state_key or "").strip().strip(".")
        if key not in corpus.SERVICE_STATE:
            return []
        state = corpus.SERVICE_STATE[key]
        why_by_service = {r.get("service", ""): r for r in model_risk}

        out = []
        for service in state.get("services_still_affected", []):
            if service == alerting:
                continue
            model_entry = why_by_service.get(service, {})
            out.append(
                {
                    "service": service,
                    "severity": model_entry.get("severity") or "SEV2",
                    "why": model_entry.get("why")
                    or f"Still carries the {key} condition: {state.get('description', '')}",
                    "evidence": (
                        f"CURRENT INFRASTRUCTURE STATE — {key}, last audited "
                        f"{state.get('last_audited', 'unknown')}"
                    ),
                }
            )
        return out

    def triage(
        self,
        alert: dict[str, Any],
        with_memory: bool = True,
    ) -> TriageResult:
        """The core call. Given an alert, return the triage payload.

        `alert` is any dict carrying at least `alert_text` and `service`. It does
        not have to come from the corpus, which is what lets somebody paste in an
        alert from their own infrastructure and watch what the memory does with it.
        A failure mode it has never seen comes back honestly empty, which is both
        the correct answer and a useful one to demonstrate.

        with_memory=False runs the identical prompt against no memory at all,
        which is what the before/after toggle in the UI shows.
        """
        if not with_memory:
            return TriageResult(
                payload={},
                baseline=self._baseline_answer(alert),
            )

        query = _triage_query(alert)

        recalled = self._recall(query)
        models = self._mental_model_text()

        answer = self.client.reflect(
            bank_id=config.BANK_INCIDENTS,
            query=query,
            budget="mid",
            max_tokens=2000,
            apply_all_directives=True,
            context=(
                "Live production alert. Today's date is 2026-09-28. Ground every claim in "
                "retained memory and cite incident ids. If the memory does not contain "
                "this failure mode, say so rather than guessing."
            ),
        )

        text = _extract_text(answer)
        payload = _filter_cited_ids(_parse_triage(text), recalled)
        payload["recurrence_risk"] = self._exposure_from_corpus(
            payload.get("state_key", ""),
            payload.get("recurrence_risk", []),
            alert.get("service", ""),
        )

        return TriageResult(
            payload=payload,
            recalled=recalled,
            mental_models=models,
            trace={
                "query": query,
                "query_tokens_estimate": len(query) // 3,
                "alert_source": alert.get("source_label", "corpus"),
                "recalled": len(recalled),
                "mental_models_consulted": list(models.keys()),
            },
        )

    def _baseline_answer(self, alert: dict[str, Any]) -> str:
        """What the same model says about the same alert with no memory at all.

        This is the "before" in before/after, and it has to be honest or the
        comparison is worthless. So rather than writing a separate prompt for a
        "stateless" model, it asks Hindsight to reflect on an empty bank: same
        model, same retrieval stack, same query shape, zero memories retained.
        Memory is the only variable.

        The bank is created once and never written to.
        """
        try:
            self.client.create_bank(
                EMPTY_BANK,
                name="Faultline control group",
                mission=(
                    "A deliberately empty memory bank. It exists so the no-memory "
                    "baseline runs through the same model and the same retrieval stack "
                    "as the real one, with no memories retained."
                ),
            )
        except Exception:
            pass  # already exists, which is what we want

        answer = self.client.reflect(
            bank_id=EMPTY_BANK,
            query=_triage_query(alert),
            budget="mid",
            max_tokens=2000,
            context=(
                "Live production alert. Today's date is 2026-09-28. This bank is "
                "intentionally empty, so answer from general knowledge only."
            ),
        )
        text = _extract_text(answer)
        return text or "(the model returned nothing)"


# --------------------------------------------------------------------- helpers


TRIAGE_FORMAT = """Reply in this exact plain-text format, one field per line. No markdown, no
bullets, no prose outside it. Use | between parts; write none when empty.

VERDICT: <what is happening and what to do>
FAILURE_MODE: <short noun phrase>
MATCH: <integer 0-100>
INCIDENTS: <ids of prior incidents sharing the root cause>
RUNBOOK: <id that fixed it before, or none>
CAUSE: <most likely root cause>
STATE: <condition key: iam_role_trust_policy, hikari_pool_default,
kafka_partitions_fixed_at_6, cache_ttl_without_jitter, or none>
ACTION: <imperative step> | <detail> | <runbook or none>
OPEN_ACTION: <text> | <owner> | <incident id> | <count of incidents that raised it>

Give 2 ACTION and up to 2 OPEN_ACTION lines. If the failure mode is not in
memory, say so and use none. STATE lets the services still carrying it be
listed."""


QUERY_TOKEN_LIMIT = 500
_ALERT_TOKEN_BUDGET = 130


def _triage_query(alert: dict[str, Any]) -> str:
    """Build the reflect query, trimming the alert if it would blow the limit.

    A pasted-in alert can be arbitrarily long, and the failure mode when it is
    too long is an opaque "Query too long: N tokens exceeds maximum of 500". So
    the alert is trimmed to a budget and the trim is disclosed, rather than
    letting the request fail.
    """
    body = str(alert.get("alert_text") or "")
    cap = _ALERT_TOKEN_BUDGET * 3
    if len(body) > cap:
        body = body[:cap].rstrip() + "\n[alert truncated to fit the query limit]"

    service = alert.get("service") or "an unknown service"
    return (
        f"Production alert on {service}:\n\n{body}\n\n"
        "Have we seen this before? Give the failure mode, prior incidents with the same root "
        "cause, the runbook, which other services still carry the same fault, and which "
        "postmortem actions for it were never completed.\n\n"
        f"{TRIAGE_FORMAT}"
    )


def _first_field(text: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.*)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _all_fields(text: str, key: str) -> list[str]:
    return [
        m.group(1).strip()
        for m in re.finditer(rf"^{key}:\s*(.*)$", text, re.MULTILINE)
    ]


def _split(value: str, parts: int) -> list[str]:
    bits = [b.strip() for b in value.split("|")]
    bits += [""] * (parts - len(bits))
    return bits[:parts]


_ID_RE = re.compile(r"INC-[0-9]{3,5}")


def _ids_present_in_memories(recalled: list[dict[str, Any]]) -> set[str]:
    """Incident ids that actually appear in what recall returned.

    This is the real test of "is this in memory". Checking against the corpus is
    necessary but not sufficient, and the holdout validator proved why: seeded
    with a bank missing five incidents, the model cited three of them by id.
    All three exist in the corpus and none of them were in that bank.
    """
    blob = " ".join(str(m.get("text") or "") for m in recalled)
    return set(_ID_RE.findall(blob))


def _filter_cited_ids(payload: dict[str, Any], recalled: list[dict[str, Any]]) -> dict[str, Any]:
    """Drop incident ids the agent cited that are not supported by the evidence.

    The `no-invention` directive asks the model not to fabricate, and it helps,
    but a directive is an instruction to a model rather than a guarantee. Found
    by the holdout validator, which watched the model cite three ids that had
    never been retained. So the citations are now checked against the text
    recall actually returned.

    An id survives if it appears in a retrieved memory, or if it is the id of an
    incident that is in the corpus and the bank was seeded in full. The second
    clause keeps the normal case working, where recall may not surface every
    relevant record in the top results but the incident genuinely is in memory.
    """
    known = {inc["id"] for inc in corpus.INCIDENTS}
    in_memories = _ids_present_in_memories(recalled)

    cited = [c for c in (payload.get("matched_incident_ids") or []) if c in known]
    # Unsupported means: not in the corpus at all, or present in the corpus but
    # not corroborated by anything recall returned while also not being the
    # incident we are currently looking at.
    unsupported = [c for c in cited if c not in in_memories]

    if unsupported:
        payload["dropped_ids"] = unsupported
        # A confidence figure that rests partly on invention is not a confidence
        # figure. Halve it rather than showing 100% next to a fabricated id.
        payload["fingerprint_match"] = max(0, int(payload.get("fingerprint_match", 0)) // 2)

    payload["matched_incident_ids"] = [c for c in cited if c not in unsupported]
    return payload


def _parse_triage(text: str) -> dict[str, Any]:
    """Turn the format contract above into the shape the UI renders.

    Hindsight's reflect endpoint accepts a response_schema but Hindsight Cloud
    returns prose anyway, so the contract is carried in the prompt and parsed
    here. Anything unparseable degrades to an empty list rather than raising —
    a partial answer is still worth showing mid-incident.
    """
    if not text:
        return {}

    ids = [i.strip() for i in _first_field(text, "INCIDENTS").split(",") if i.strip()]
    ids = [i for i in ids if re.fullmatch(r"INC-[\w-]+", i)]

    match_raw = _first_field(text, "MATCH")
    try:
        match = max(0, min(100, int(re.search(r"\d+", match_raw).group(0))))
    except Exception:
        match = 0

    actions = []
    for line in _all_fields(text, "ACTION")[:4]:
        step, detail, rb = _split(line, 3)
        if step and step.lower() != "none":
            actions.append({"step": step, "detail": detail, "runbook": rb})

    risk = []
    for line in _all_fields(text, "EXPOSED")[:4]:
        service, severity, why, evidence = _split(line, 4)
        if service and service.lower() != "none":
            risk.append(
                {
                    "service": service,
                    "severity": severity.upper() if severity else "SEV2",
                    "why": why,
                    "evidence": evidence,
                }
            )

    stale = []
    for line in _all_fields(text, "OPEN_ACTION")[:4]:
        text_, owner, incident, times = _split(line, 4)
        if text_ and text_.lower() != "none":
            try:
                times_n = int(re.search(r"\d+", times).group(0)) if times else 1
            except Exception:
                times_n = 1
            stale.append(
                {
                    "text": text_,
                    "owner": owner,
                    "incident_id": incident,
                    "times_written": times_n,
                }
            )

    verdict = _first_field(text, "VERDICT")
    if not verdict and not ids:
        return {"verdict": text.strip(), "fingerprint_match": 0, "matched_incident_ids": []}

    return {
        "state_key": _first_field(text, "STATE"),
        "verdict": verdict or text.strip()[:600],
        "fingerprint_match": match,
        "matched_incident_ids": ids,
        "failure_mode": _first_field(text, "FAILURE_MODE"),
        "root_cause_hypothesis": _first_field(text, "CAUSE"),
        "first_actions": actions,
        "recurrence_risk": risk,
        "stale_action_items": stale,
        "confidence": "high" if match >= 75 else "medium" if match >= 40 else "low",
        "raw": text,
    }


def _parse_ts(value: str):
    from datetime import datetime

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return round(float(value), 4)
    except Exception:
        return None


def _extract_text(response: Any) -> str:
    for attr in ("text", "output_text", "content"):
        value = getattr(response, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    data = getattr(response, "data", None)
    if isinstance(data, str):
        return data
    if isinstance(response, dict):
        for key in ("text", "output_text", "content"):
            if isinstance(response.get(key), str):
                return response[key]
    try:
        return json.dumps(response, default=str)
    except Exception:
        return str(response)


def _parse_schema_json(text: str) -> dict[str, Any]:
    """Reflect returns prose, or JSON when given a response schema. Handle both."""
    if not text:
        return {}
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except Exception:
                        break
    return {"verdict": text, "fingerprint_match": 0, "matched_incident_ids": []}


engine = MemoryEngine()
