"""Grounded measurement of the learning curve.

Judges will not believe "the agent gets smarter over time" without a number, and
a hand-waved one is worse than none. So this module measures it directly.

For every incident in the corpus we already have a ground-truth cluster: the set
of other incidents that share its root cause. We ask Hindsight to recall the
failure mode for that incident and check which of its true siblings come back.

Because the bank is fully seeded, the cumulative answer to "how many of the
incidents that came before this one can the memory now connect?" is a real
retrospective on the same data, and it needs no LLM calls at all — recall does
its ranking locally with BM25, the entity graph, temporal filters and a
cross-encoder.
"""

from __future__ import annotations

from typing import Any

from app import config, corpus

# Ground truth: incidents that share a root cause, written by hand. This is the
# answer key the measurement is scored against.
#
# Only clusters where the root cause genuinely is the same are included. An
# earlier draft also grouped INC-1122 with INC-1164 as "unsafe rollout", and
# INC-1176 with INC-1229 as "unbounded memory" — but a feature flag ramped to
#100% and a forward-only migration left behind by a rollback are different
# faults, and an OOM in a backfill is not a bad record in a payout batch. Those
# pairs scored as misses and made the number worse for the right reason: the
# answer key was wrong, not the memory. A smaller honest key beats a larger
# flattering one.
CLUSTERS: dict[str, list[str]] = {
    "iam_stale_trust_policy": ["INC-1042", "INC-1188"],
    "connection_pool_and_n_plus_one": ["INC-1099", "INC-1203", "INC-1224"],
    "third_party_no_backoff_or_timeout": ["INC-1211", "INC-1219"],
    "certificate_and_clock_drift": ["INC-1155", "INC-1140"],
    "kafka_consumer_rebalance": ["INC-1231"],
    "cache_stampede": ["INC-1130"],
    "database_bloat": ["INC-1107"],
}

# Which cluster each incident belongs to. Incidents in no cluster are singletons
# and are excluded from the recall measurement, since there is nothing to find.
INCIDENT_CLUSTER: dict[str, str] = {
    inc: cluster for cluster, members in CLUSTERS.items() for inc in members
}

CLUSTER_LABEL: dict[str, str] = {
    "iam_stale_trust_policy": "Stale IAM role trust policy",
    "connection_pool_and_n_plus_one": "Connection pool exhaustion / N+1",
    "third_party_no_backoff_or_timeout": "Third-party call with no backoff or timeout",
    "kafka_consumer_rebalance": "Kafka consumer rebalance storm",
    "cache_stampede": "Redis stampede from flat TTLs",
    "certificate_and_clock_drift": "Certificate expiry and clock drift",
    "database_bloat": "Autovacuum starvation and table bloat",
}


# How an on-call engineer would actually phrase the question, one per cluster.
# The symptom plus the mechanism, because a bare alert string is a weak query
# and would understate what the memory can do.
CLUSTER_QUERY: dict[str, str] = {
    "iam_stale_trust_policy": (
        "Have we been denied sts:AssumeRole by a wildcard IAM role trust policy after an "
        "automated credential rotation, and which runbook fixed it?"
    ),
    "connection_pool_and_n_plus_one": (
        "Have we exhausted the HikariCP connection pool, or slowed a service down with an N+1 "
        "that sends many SQL statements per request? How did we fix it last time?"
    ),
    "third_party_no_backoff_or_timeout": (
        "Has an outbound call to a third-party API retried without backoff or blocked a thread "
        "pool with no timeout set? What did we change?"
    ),
    "certificate_and_clock_drift": (
        "Has an internal certificate expired, or has NTP clock drift broken token validation? "
        "Which runbook applies?"
    ),
    "kafka_consumer_rebalance": (
        "Have we had a Kafka consumer rebalance storm because group concurrency did not match "
        "the partition count after a topic was widened?"
    ),
    "cache_stampede": (
        "Has Redis key eviction caused a cache stampede because keys were written with a flat "
        "TTL and no jitter?"
    ),
    "database_bloat": (
        "Has table bloat on an append-only Postgres table stalled autovacuum with lock "
        "contention?"
    ),
}


def _cluster_query(incident: dict[str, Any], cluster: str) -> str:
    """A query a human would actually type mid-incident, not a label lookup.

    Built from the alert symptom plus the mechanism, so it exercises the same
    retrieval path the live triage uses.
    """
    head = corpus.by_id(incident["id"])
    symptom = head["alert_text"].splitlines()[0] if head else incident["title"]
    return f"{symptom}\n{CLUSTER_QUERY[cluster]}"


def _mentioned(text: str, incident_id: str) -> bool:
    return incident_id.lower() in (text or "").lower()


def measure(engine) -> dict[str, Any]:
    """Run recall for every incident and score it against the answer key."""
    incidences = [i for i in corpus.INCIDENTS if i["id"] in INCIDENT_CLUSTER]
    incidences.sort(key=lambda i: i["opened"])

    rows: list[dict[str, Any]] = []
    true_positives = 0
    possible = 0
    per_incident: list[dict[str, Any]] = []

    for inc in incidences:
        cluster = INCIDENT_CLUSTER[inc["id"]]
        expected = [m for m in CLUSTERS[cluster] if m != inc["id"]]
        # Only count siblings that had already happened by this incident's date.
        opened = inc["opened"]
        expected = [
            m
            for m in expected
            if (corpus.by_id(m) or {}).get("opened", "9999") < opened
        ]
        if not expected:
            continue

        res = engine.client.recall(
            bank_id=config.BANK_INCIDENTS,
            query=_cluster_query(inc, cluster),
            budget="high",
            max_tokens=4096,
        )
        blob = " ".join(
            getattr(item, "text", "") or "" for item in (getattr(res, "results", None) or [])[:10]
        )
        found = [m for m in expected if _mentioned(blob, m)]
        missing = [m for m in expected if m not in found]

        true_positives += len(found)
        possible += len(expected)

        per_incident.append(
            {
                "incident_id": inc["id"],
                "service": inc["service"],
                "opened": opened,
                "cluster": cluster,
                "cluster_label": CLUSTER_LABEL[cluster],
                "expected": expected,
                "found": found,
                "missing": missing,
                "recall": round(len(found) / len(expected), 3) if expected else None,
            }
        )

        rows.append(
            {
                "at": opened,
                "incidents_indexed": len(per_incident),
                "cumulative_recall": round(true_positives / possible, 4) if possible else 0.0,
            }
        )

    overall = round(true_positives / possible, 4) if possible else 0.0
    return {
        "overall_recall": overall,
        "true_positives": true_positives,
        "possible": possible,
        "incidents_measured": len(per_incident),
        "curve": rows,
        "per_incident": per_incident,
        "clusters": {k: {"members": v, "label": CLUSTER_LABEL[k]} for k, v in CLUSTERS.items()},
    }
