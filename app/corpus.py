"""The Northwind Commerce incident corpus.

Synthetic but deliberately realistic: a mid-size commerce platform, ten services,
eighteen months of incidents, and — critically — postmortem action items that
were written down and then never finished. Those unfinished actions are what make
Faultline worth more than a runbook search, because they are the only way to know
that a failure mode is still loaded in a service nobody has touched yet.

The spine of the dataset is the IAM role trust policy thread:

    2026-03-14  payments-api burns 41 minutes on a stale IAM role (INC-1042).
                Postmortem action: "sweep every service for the same trust policy."
    2026-06-02  checkout-web hits the identical cause (INC-1188). Action items
                again written, again not done.
    2026-09-28  payout-worker starts throwing auth failures with a *different*
                symptom. Faultline connects all three.

If a demo can only show one thing, it is that chain.
"""

from __future__ import annotations

from typing import Any

ORG = "Northwind Commerce"
ENVIRONMENTS = ["production", "staging"]

SERVICES = [
    {
        "name": "payments-api",
        "owner": "Core Money",
        "tier": 1,
        "language": "Java 21 / Spring Boot",
        "replicas": 24,
        "notes": "Card authorisation and capture. Hard SLO: 99.95%.",
    },
    {
        "name": "payout-worker",
        "owner": "Core Money",
        "tier": 1,
        "language": "Python 3.12 / Celery",
        "replicas": 12,
        "notes": "Nightly merchant payouts and refunds.",
    },
    {
        "name": "checkout-web",
        "owner": "Storefront",
        "tier": 1,
        "language": "TypeScript / Node 22",
        "replicas": 18,
        "notes": "Customer-facing cart and checkout.",
    },
    {
        "name": "identity-gateway",
        "owner": "Platform",
        "tier": 1,
        "language": "Go 1.23",
        "replicas": 30,
        "notes": "OIDC issuer, session and token validation.",
    },
    {
        "name": "ledger-svc",
        "owner": "Core Money",
        "tier": 1,
        "language": "Kotlin / Spring Boot",
        "replicas": 16,
        "notes": "Double-entry ledger. Append-only, reconciled hourly.",
    },
    {
        "name": "fraud-scoring",
        "owner": "Risk",
        "tier": 2,
        "language": "Python 3.12",
        "replicas": 9,
        "notes": "Real-time transaction risk score, 120ms budget.",
    },
    {
        "name": "inventory-sync",
        "owner": "Fulfilment",
        "tier": 2,
        "language": "Java 21",
        "replicas": 8,
        "notes": "Warehouse stock reconciliation.",
    },
    {
        "name": "search-indexer",
        "owner": "Storefront",
        "tier": 3,
        "language": "Rust",
        "replicas": 6,
        "notes": "Product catalogue indexing. Rebuildable.",
    },
    {
        "name": "webhooks-relay",
        "owner": "Platform",
        "tier": 2,
        "language": "Rust",
        "replicas": 10,
        "notes": "Outbound partner webhooks with retries.",
    },
    {
        "name": "reporting-etl",
        "owner": "Data",
        "tier": 3,
        "language": "Python 3.12 / Airflow",
        "replicas": 5,
        "notes": "Nightly finance and growth reporting.",
    },
]

PEOPLE = {
    "priya": "Priya Raghunathan",
    "marcus": "Marcus Feld",
    "dana": "Dana Okafor",
    "tomas": "Tomás Herrera",
    "aisha": "Aisha Bello",
    "jonas": "Jonas Weber",
    "lena": "Lena Kovač",
    "rahul": "Rahul Menon",
    "sofia": "Sofia Duarte",
    "kenji": "Kenji Watanabe",
}

# Latent infrastructure state, current as of 2026-09-28. This is what the agent
# compares the live alert against to answer "is this loaded in a service that
# has not failed yet?"
SERVICE_STATE = {
    "iam_role_trust_policy": {
        "description": (
            "Role trust policy written as Principal={\"AWS\": \"*\"} with a "
            "condition only on the role name, so any principal in the account "
            "can assume cross-service roles."
        ),
        "last_audited": "2026-01-14",
        "services_still_affected": ["payout-worker", "inventory-sync", "webhooks-relay"],
        "fixed_in": ["payments-api", "checkout-web", "ledger-svc"],
        "why_it_keeps_coming_back": (
            "The base Terraform module terraform/modules/service-role still "
            "contains the wildcard principal and nobody changed the default."
        ),
    },
    "hikari_pool_default": {
        "description": (
            "HikariCP left at maximumPoolSize=10 while the service runs 24 "
            "replicas behind a connection-heavy ORM, so concurrency collapses "
            "to 10 in-flight DB sessions per pod."
        ),
        "last_audited": "2025-11-02",
        "services_still_affected": ["inventory-sync", "reporting-etl"],
        "fixed_in": ["payments-api"],
    },
    "kafka_partitions_fixed_at_6": {
        "description": (
            "Consumer group subscribed with a hardcoded concurrency of 6 while "
            "every topic has been widened to 24 partitions, so 18 partitions "
            "sit idle and rebalances reshuffle the whole group."
        ),
        "last_audited": "2026-04-19",
        "services_still_affected": ["webhooks-relay", "fraud-scoring"],
        "fixed_in": [],
    },
    "cache_ttl_without_jitter": {
        "description": (
            "Redis keys written with a flat 300s TTL and no jitter, so a warm-up "
            "or a keyspace refresh turns into a synchronised stampede."
        ),
        "last_audited": "2026-02-08",
        "services_still_affected": ["checkout-web", "fraud-scoring"],
        "fixed_in": ["search-indexer"],
    },
}


def _action(
    owner: str,
    text: str,
    status: str = "open",
    note: str = "",
) -> dict[str, str]:
    return {
        "owner": PEOPLE[owner] if owner in PEOPLE else owner,
        "text": text,
        "status": status,
        "note": note,
    }


INCIDENTS: list[dict[str, Any]] = [
    # ---------------------------------------------------------------- IAM thread
    {
        "id": "INC-1042",
        "service": "payments-api",
        "severity": "SEV1",
        "status": "resolved",
        "opened": "2026-03-14T09:12:00Z",
        "resolved": "2026-03-14T09:53:00Z",
        "title": "Card authorisation returning 503 for 41 minutes",
        "detected_by": "Datadog monitor: payments.auth.error_rate > 2% for 5m",
        "alert_text": (
            "[CRITICAL] payments-api auth_error_rate=0.37 over 5m window\n"
            "  service: payments-api   env: production   region: eu-west-1\n"
            "  http.status: 503 (34,182 requests)\n"
            "  error: AccessDenied - User: arn:aws:sts::9182:assumed-role/svc-payments/rotator "
            "is not authorized to perform: sts:AssumeRole on resource "
            "arn:aws:iam::9182:role/nw-core-ledger\n"
            "  iam:CredentialLastRotated=2026-03-13T02:00:00Z"
        ),
        "timeline": [
            ("09:12", "Datadog pages Core Money on-call (Rahul Menon). Ack within 3m."),
            ("09:18", "Rahul notes the last credential rotation was 31 hours ago and suspects IAM."),
            ("09:27", "Escalated to Platform (Jonas Weber) after no obvious application rollback."),
            ("09:34", "Jonas confirms sts:AssumeRole is denied for the rotator's assumed role."),
            ("09:41", "Applied runbook RB-07: re-issue the cross-service trust and force refresh."),
            ("09:53", "Error rate returned to 0.02%. Incident closed."),
        ],
        "log_excerpt": (
            "2026-03-14T09:12:04.221Z ERROR [payments-api] c.n.w.money.auth.StsClient - "
            "assumeRole failed: AccessDeniedException: User: arn:aws:sts::9182:assumed-role/"
            "svc-payments/rotator is not authorized to perform: sts:AssumeRole on "
            "arn:aws:iam::9182:role/nw-core-ledger\n"
            "2026-03-14T09:12:04.229Z ERROR [payments-api] c.n.w.money.auth.StsClient - "
            "retry 1/5 in 800ms (backoff base 400ms)\n"
            "2026-03-14T09:12:07.402Z ERROR [payments-api] c.n.w.money.CaptureService - "
            "downstream ledger unavailable, failing capture open"
        ),
        "root_cause": (
            "An automated IAM credential rotation at 02:00 replaced the svc-payments "
            "assumed role. The trust policy on nw-core-ledger was written with "
            "Principal={\"AWS\": \"*\"} plus a condition on the role name, so the "
            "rotation silently widened the trust to a principal that the ledger role's "
            "resource policy no longer permits. The service kept its cached token until "
            "its 12h refresh, so the failure was delayed and looked unrelated to the "
            "rotation."
        ),
        "resolution": "Re-issued the trust relationship and forced a token refresh via runbook RB-07.",
        "runbook": "RB-07",
        "customer_impact": "41 minutes of failed card authorisations. 1,204 orders retried, 87 abandoned.",
        "mttr_minutes": 41,
        "action_items": [
            _action("jonas", "Sweep every service for the wildcard Principal={\"AWS\": \"*\"} trust policy and replace with an explicit role list.", status="open", note="Never started."),
            _action("rahul", "Add a synthetic check that calls sts:AssumeRole cross-service every 10 minutes.", status="done"),
            _action("jonas", "Change terraform/modules/service-role so the wildcard is not the default.", status="open", note="Module never updated; still the default today."),
        ],
        "tags": ["iam", "sts", "credential-rotation", "sev1", "auth"],
    },
    {
        "id": "INC-1188",
        "service": "checkout-web",
        "severity": "SEV2",
        "status": "resolved",
        "opened": "2026-06-02T14:38:00Z",
        "resolved": "2026-06-02T15:22:00Z",
        "title": "Checkout sessions rejected with 401 after a 4-day-old deploy",
        "detected_by": "Grafana: checkout.session_reject_rate above 4%",
        "alert_text": (
            "[HIGH] checkout-web session_reject_rate=0.061 over 10m window\n"
            "  service: checkout-web   env: production   region: eu-central-1\n"
            "  http.status: 401 (11,904 requests)\n"
            "  error: token audience mismatch: expected 'nw-checkout' got 'nw-identity'\n"
            "  deploy: checkout-web@a91f2c7 deployed 2026-05-29T16:02Z"
        ),
        "timeline": [
            ("14:38", "Storefront on-call (Sofia Duarte) paged. 11,904 401s in 10m."),
            ("14:51", "Sofia checked deploy history, initially suspected the 4-day-old deploy a91f2c7."),
            ("15:04", "Marcus (Platform) found the real cause: an IAM role change, not the deploy."),
            ("15:13", "Same wildcard trust pattern as INC-1042, discovered during the March sweep that was never run."),
            ("15:22", "Trust policy replaced with an explicit allow-list. Errors cleared."),
        ],
        "log_excerpt": (
            "2026-06-02T14:38:11.004Z WARN [checkout-web] session.validate - audience mismatch\n"
            "  expected=nw-checkout received=nw-identity iss=https://id.northwind.internal\n"
            "2026-06-02T14:38:11.006Z INFO [checkout-web] session.validate - role assumption "
            "cached_at=2026-05-30T02:00:00Z age=3402h"
        ),
        "root_cause": (
            "Identical wildcard trust policy to INC-1042, still present in checkout-web. "
            "A trust policy rewrite on 2026-05-30 changed the audience claim on the role "
            "chain, but the service held a cached STS token for 4 days because the token "
            "refresh only ran on traffic spikes. Symptoms appeared in checkout, but the "
            "change was in IAM."
        ),
        "resolution": "Replaced wildcard trust with an explicit allow-list and forced refresh.",
        "runbook": "RB-07",
        "customer_impact": "44 minutes of failed checkouts. 3,410 carts lost, estimated 214k EUR lost.",
        "mttr_minutes": 44,
        "action_items": [
            _action("marcus", "Re-run the INC-1042 wildcard trust sweep across all remaining services.", status="open", note="Third time this action has been written. Still not done."),
            _action("sofia", "Add audience assertion to the session validator so this fails fast in staging.", status="done"),
        ],
        "tags": ["iam", "jwt", "audience", "stale-token", "checkout"],
    },
    {
        "id": "INC-1231",
        "service": "search-indexer",
        "severity": "SEV3",
        "status": "resolved",
        "opened": "2026-07-11T02:20:00Z",
        "resolved": "2026-07-11T04:05:00Z",
        "title": "Catalogue indexing stalled after a Kafka rebalance storm",
        "detected_by": "Synthetic check: indexer_lag_age > 15m",
        "alert_text": (
            "[WARN] search-indexer consumer_lag=284113 over 15m window\n"
            "  service: search-indexer   env: production   cluster: nw-eu-2\n"
            "  group: indexer-eur2-v3   partitions_assigned: 6 of 24\n"
            "  rebalances_last_hour: 41"
        ),
        "timeline": [
            ("02:20", "Synthetic check fires on consumer lag."),
            ("02:44", "Jonas finds 41 rebalances in the last hour."),
            ("03:10", "Root cause: topic widened to 24 partitions, consumer concurrency hardcoded at 6."),
            ("04:05", "Concurrency raised to 24 and rebalances stopped. Lag drained by 06:40."),
        ],
        "log_excerpt": (
            "2026-07-11T02:21:10Z INFO [search-indexer] consumer rebalance start gen=8841 "
            "assignment=[0,1,2,3,4,5] members=6\n"
            "2026-07-11T02:33:44Z INFO [search-indexer] consumer rebalance start gen=8867 "
            "assignment=[0,1,2,3,4,5] members=6\n"
            "2026-07-11T02:41:02Z WARN [search-indexer] 18 of 24 partitions unassigned"
        ),
        "root_cause": (
            "Topic catalogue.events was widened from 6 to 24 partitions during the June "
            "capacity work, but the consumer group concurrency stayed hardcoded at 6. "
            "The static group membership timeout (300s) plus a slow heartbeat on a loaded "
            "node triggered a rebalance roughly every 2 minutes, and each rebalance "
            "rewrote all 24 partition offsets."
        ),
        "resolution": "Raised group concurrency to match partition count and lowered session timeout to 45s.",
        "runbook": "RB-11",
        "customer_impact": "Catalogue search results stale for 4 hours. No checkout impact.",
        "mttr_minutes": 105,
        "action_items": [
            _action("jonas", "Make consumer concurrency derive from partition count so a topic widening cannot desync it again.", status="open", note="Manual change only; no guard in place."),
        ],
        "tags": ["kafka", "rebalance", "partitions", "lag"],
    },
    # ------------------------------------------------------- connection pooling
    {
        "id": "INC-1099",
        "service": "payments-api",
        "severity": "SEV1",
        "status": "resolved",
        "opened": "2026-04-09T17:45:00Z",
        "resolved": "2026-04-09T18:26:00Z",
        "title": "Connection pool exhaustion during the Black Friday promo spike",
        "detected_by": "Prometheus: hikaricp_connections_pending > 0 for 3m",
        "alert_text": (
            "[CRITICAL] payments-api hikaricp_connections_pending=48 over 3m window\n"
            "  service: payments-api   env: production   region: eu-west-1\n"
            "  active=10 idle=0 max=10\n"
            "  db.pool.timeout: 5000ms exceeded 61,204 times"
        ),
        "timeline": [
            ("17:45", "Pool exhaustion alert. Promo traffic 3.4x normal."),
            ("17:58", "Aisha (Core Money) identifies an N+1 introduced in the authorisation path."),
            ("18:11", "Runbook RB-03: raise pool size and disable the offending eager load."),
            ("18:26", "Pending connections back to 0. No data loss."),
        ],
        "log_excerpt": (
            "2026-04-09T17:45:02.883Z ERROR [payments-api] c.z.h.p.HikariPool - "
            "Connection is not available, request timed out after 5000ms\n"
            "2026-04-09T17:45:02.884Z WARN [payments-api] c.n.w.money.AuthRepo - "
            "1 query per authorisation, 63 statements per request"
        ),
        "root_cause": (
            "A merge in the authorisation path replaced a single joined fetch with a lazy "
            "per-row lookup, producing 63 SQL statements per authorisation. The Hikari pool "
            "is capped at maximumPoolSize=10, so the extra statements exhausted the pool and "
            "requests queued. This was a capacity problem and a query-shape problem at once."
        ),
        "resolution": "Raised maximumPoolSize to 40 and restored the batched fetch (runbook RB-03).",
        "runbook": "RB-03",
        "customer_impact": "41 minutes at 2.1% checkout failure during peak promotional traffic.",
        "mttr_minutes": 41,
        "action_items": [
            _action("aisha", "Add a per-request statement count guard that fails the build above 30.", status="done"),
            _action("aisha", "Propagate maximumPoolSize to every service from the shared Spring module.", status="open", note="Only payments-api was updated."),
        ],
        "tags": ["hikaricp", "connection-pool", "n+1", "latency", "capacity"],
    },
    {
        "id": "INC-1203",
        "service": "inventory-sync",
        "severity": "SEV2",
        "status": "resolved",
        "opened": "2026-07-28T05:10:00Z",
        "resolved": "2026-07-28T06:02:00Z",
        "title": "Warehouse sync stalled on HikariCP timeouts",
        "detected_by": "Grafana: db.pool.timeout rate elevated",
        "alert_text": (
            "[HIGH] inventory-sync db_pool_timeout_rate=0.22 over 10m window\n"
            "  service: inventory-sync   env: production\n"
            "  active=10 idle=0 max=10\n"
            "  error: Connection is not available, request timed out after 5000ms"
        ),
        "timeline": [
            ("05:10", "Pool timeout alert on inventory-sync."),
            ("05:31", "Same shape as the payments-api incident in April."),
            ("05:48", "Confirmed maximumPoolSize is still 10 here; only payments-api was raised."),
            ("06:02", "Pool raised to 30 via the shared module. Sync resumed."),
        ],
        "log_excerpt": (
            "2026-07-28T05:10:44.120Z ERROR [inventory-sync] c.z.h.p.HikariPool - "
            "Connection is not available, request timed out after 5000ms\n"
            "2026-07-28T05:10:44.121Z INFO [inventory-sync] sync.batch - batch 8812 "
            "processed 40 of 3100 rows before stall"
        ),
        "root_cause": (
            "Identical pool exhaustion to INC-1099 but without the N+1 amplifier. "
            "inventory-sync still runs maximumPoolSize=10 because the shared Spring "
            "module change from that incident was never applied outside payments-api. "
            "The batch worker holds a connection per row for upsert, so any warehouse "
            "feed larger than the pool saturates it."
        ),
        "resolution": "Raised maximumPoolSize to 30 and reduced connection hold time per row.",
        "runbook": "RB-03",
        "customer_impact": "52 minutes of stale stock counts on 1,204 SKUs.",
        "mttr_minutes": 52,
        "action_items": [
            _action("aisha", "Finish propagating maximumPoolSize through the shared Spring module.", status="open", note="Second time written. reporting-etl is also still on the old default."),
        ],
        "tags": ["hikaricp", "connection-pool", "batch", "sync"],
    },
    # --------------------------------------------------------- cache stampede
    {
        "id": "INC-1130",
        "service": "checkout-web",
        "severity": "SEV2",
        "status": "resolved",
        "opened": "2026-05-19T11:02:00Z",
        "resolved": "2026-05-19T11:49:00Z",
        "title": "Redis stampede after a full keyspace flush",
        "detected_by": "Redis SLOWLOG + checkout p99 alarm",
        "alert_text": (
            "[HIGH] checkout-web cart_load_p99_ms=2840 over 5m window\n"
            "  service: checkout-web   env: production\n"
            "  redis: keys=412 missing=398 evictions=0\n"
            "  origin: manual FLUSHALL by on-call during a cache incident"
        ),
        "timeline": [
            ("11:02", "p99 on cart load jumps to 2.8s after a manual FLUSHALL."),
            ("11:20", "Kenji (Storefront) confirms a flat 300s TTL on every cart key."),
            ("11:33", "All 398 hot keys expire within the same 2-second window."),
            ("11:49", "Jittered TTLs applied and a stale-while-revalidate path enabled."),
        ],
        "log_excerpt": (
            "2026-05-19T11:02:31.551Z WARN [checkout-web] cache.get - MISS key=cart:u88213 "
            "origin=db load=1890ms\n"
            "2026-05-19T11:03:02.114Z WARN [checkout-web] cache.get - miss_rate=0.94 "
            "db_connections=10/10"
        ),
        "root_cause": (
            "An on-call ran FLUSHALL to recover from a separate cache poisoning report. "
            "Every cart key was written with a flat 300s TTL, so the whole hot keyset "
            "expired within roughly the same two seconds and 94% of reads went to a "
            "Postgres that was already close to its connection limit."
        ),
        "resolution": "Applied 10% TTL jitter per key and added stale-while-revalidate on cart reads.",
        "runbook": "RB-08",
        "customer_impact": "47 minutes of 3-8s cart loads. 6% cart abandonment spike.",
        "mttr_minutes": 47,
        "action_items": [
            _action("kenji", "Add TTL jitter to every cached key write in the shared cache client.", status="open", note="Only checkout-web was patched; fraud-scoring still writes flat TTLs."),
            _action("kenji", "Add a FLUSHALL guard that requires a two-person approval.", status="done"),
        ],
        "tags": ["redis", "cache-stampede", "ttl", "flushall"],
    },
    # ------------------------------------------------------------- cert expiry
    {
        "id": "INC-1155",
        "service": "identity-gateway",
        "severity": "SEV1",
        "status": "resolved",
        "opened": "2026-05-30T02:41:00Z",
        "resolved": "2026-05-30T03:33:00Z",
        "title": "Mesh certificate expiry locked out every service",
        "detected_by": "Synthetic TLS probe from outside the mesh",
        "alert_text": (
            "[CRITICAL] identity-gateway tls_handshake_failure=1.0 over 2m window\n"
            "  service: identity-gateway   env: production\n"
            "  error: certificate has expired (notAfter=2026-05-30T02:39:00Z)\n"
            "  issuer: internal-ca-02   renewal_request_logged: 14 days ago"
        ),
        "timeline": [
            ("02:41", "Every service fails to reach identity-gateway over mTLS."),
            ("03:02", "Kenji finds the cert expired 2 minutes earlier; renewal request was logged 14 days ago."),
            ("03:19", "Runbook RB-14: emergency reissue with the backup CA."),
            ("03:33", "Handshakes recovered. 52 minutes total blast radius."),
        ],
        "log_excerpt": (
            "2026-05-30T02:41:09.331Z FATAL [identity-gateway] tls - handshake failure from "
            "10.42.7.19: x509: certificate has expired or is not yet valid: "
            "current time 2026-05-30T02:41:09Z is after 2026-05-30T02:39:00Z"
        ),
        "root_cause": (
            "The internal CA issued a 30-day leaf for identity-gateway, but the auto-renewal "
            "job had been failing silently for 14 days because the CA was migrated to "
            "internal-ca-02 and the job still pointed at internal-ca-01. The renewal request "
            "existed in the log the whole time and nobody alerted on it."
        ),
        "resolution": "Emergency reissue from the backup CA and forced a full mesh restart.",
        "runbook": "RB-14",
        "customer_impact": "52 minutes of total login outage across all services.",
        "mttr_minutes": 52,
        "action_items": [
            _action("kenji", "Alert when a certificate renewal request is older than 48 hours.", status="open", note="Alert rule written, never enabled in the ruleset."),
        ],
        "tags": ["tls", "mTLS", "certificate", "expiry", "ca", "outage"],
    },
    # ------------------------------------------------------------- OOM / heap
    {
        "id": "INC-1176",
        "service": "fraud-scoring",
        "severity": "SEV2",
        "status": "resolved",
        "opened": "2026-06-18T13:25:00Z",
        "resolved": "2026-06-18T13:52:00Z",
        "title": "OOMKilled during the fraud model rescore",
        "detected_by": "Kubernetes: container restarted, exit 137",
        "alert_text": (
            "[HIGH] fraud-scoring pod restarts=3 in 10m\n"
            "  service: fraud-scoring   env: production   pod=fraud-scoring-7d9f-2xk4m\n"
            "  exit_code: 137 (OOMKilled)   memory limit: 2Gi   peak: 2.03Gi\n"
            "  job: rescore_backfill_2026Q2"
        ),
        "timeline": [
            ("13:25", "Pod OOMKilled three times in 10 minutes during the Q2 rescore backfill."),
            ("13:38", "Lena finds the backfill materialises every transaction into a list."),
            ("13:52", "Backfill switched to a chunked generator. Restarts stopped."),
        ],
        "log_excerpt": (
            "2026-06-18T13:25:11.004Z WARN [fraud-scoring] heap - 2.03Gi requested, "
            "2Gi limit reached, container will be OOMKilled\n"
            "2026-06-18T13:25:11.900Z INFO [fraud-scoring] rescore - loaded 41,882,004 rows "
            "into memory as list"
        ),
        "root_cause": (
            "A quarterly model rescore job loaded the entire transaction table into a Python "
            "list. At 41.8M rows this needed roughly 6Gi against a 2Gi container limit, so the "
            "kubelet killed it repeatedly. Each restart re-read the table, so the job made "
            "no progress across three attempts."
        ),
        "resolution": "Rewrote the backfill as a chunked generator with a hard row cap per chunk.",
        "runbook": "RB-05",
        "customer_impact": "27 minutes where risk scores fell back to the previous model version.",
        "mttr_minutes": 27,
        "action_items": [
            _action("lena", "Add a memory ceiling assertion to every Airflow task that can read the transaction table.", status="open", note="Never implemented."),
        ],
        "tags": ["oom", "heap", "memory", "backfill", "kubernetes"],
    },
    # ------------------------------------------------- third-party rate limits
    {
        "id": "INC-1211",
        "service": "webhooks-relay",
        "severity": "SEV2",
        "status": "resolved",
        "opened": "2026-07-15T20:14:00Z",
        "resolved": "2026-07-15T21:30:00Z",
        "title": "Partner webhook relay burned its daily quota in 40 minutes",
        "detected_by": "Grafana: relay.delivery_failure_rate > 30%",
        "alert_text": (
            "[HIGH] webhooks-relay delivery_failure_rate=0.38 over 10m window\n"
            "  service: webhooks-relay   env: production\n"
            "  upstream: partner-pay-api  http.status: 429\n"
            "  quota_used: 1000000/1000000   retry_after: absent"
        ),
        "timeline": [
            ("20:14", "38% delivery failures. Upstream returned 429 with no Retry-After."),
            ("20:41", "Dmitri-less: Tomás (Platform) finds the retry loop has no backoff cap."),
            ("21:02", "Runbook RB-09: exponential backoff with a hard daily budget."),
            ("21:30", "Relay recovered; backlog drained overnight."),
        ],
        "log_excerpt": (
            "2026-07-15T20:14:22.771Z ERROR [webhooks-relay] upstream.partner-pay - "
            "HTTP 429 rate_limited, retrying in 0ms\n"
            "2026-07-15T20:14:22.772Z ERROR [webhooks-relay] upstream.partner-pay - "
            "HTTP 429 rate_limited, retrying in 0ms"
        ),
        "root_cause": (
            "The relay retried 429s with a zero delay and no attempt cap. One slow partner "
            "endpoint caused a tight retry loop that consumed the entire 1M daily quota in "
            "40 minutes, so genuine traffic was rejected for the rest of the day."
        ),
        "resolution": "Added exponential backoff with jitter, a daily request budget, and circuit breaking.",
        "runbook": "RB-09",
        "customer_impact": "76 minutes of failed partner notifications; 3 merchant integrations affected.",
        "mttr_minutes": 76,
        "action_items": [
            _action("tomas", "Add a per-partner daily request budget to the relay config schema.", status="done"),
        ],
        "tags": ["rate-limit", "429", "retry", "backoff", "webhook", "third-party"],
    },
    # ------------------------------------------------------------ DB / vacuum
    {
        "id": "INC-1107",
        "service": "ledger-svc",
        "severity": "SEV3",
        "status": "resolved",
        "opened": "2026-04-24T01:00:00Z",
        "resolved": "2026-04-24T04:30:00Z",
        "title": "Reconciliation stalled on autovacuum lock contention",
        "detected_by": "Nightly reconciliation job miss",
        "alert_text": (
            "[WARN] ledger-svc reconciliation job missed its window\n"
            "  service: ledger-svc   env: production\n"
            "  table: ledger_entries  bloat=61%%  dead_tuples=412000000\n"
            "  vacuum: last_autovacuum=2026-04-09T00:00:00Z"
        ),
        "timeline": [
            ("01:00", "Nightly reconciliation did not complete inside its window."),
            ("01:47", "Dana (Core Money) finds autovacuum has not run on ledger_entries in 15 days."),
            ("02:30", "Runbook RB-06: manual VACUUM ANALYZE, one shard at a time."),
            ("04:30", "Bloat down to 12%. Reconciliation finished at 04:12."),
        ],
        "log_excerpt": (
            "2026-04-24T01:47:22.104Z WARN [ledger-svc] db.vacuum - autovacuum skipped "
            "ledger_entries: lock contention with active transaction (xmin=88214493)\n"
            "2026-04-24T01:47:23.000Z WARN [ledger-svc] reconcile - shard 3/12 blocked "
            "waiting 1800s"
        ),
        "root_cause": (
            "ledger_entries is append-only and grew to 1.4B rows. The nightly reconciliation "
            "held a long transaction that pinned xmin and blocked autovacuum, so vacuum never "
            "ran. Table bloat reached 61% and the reconciliation itself slowed until it missed "
            "its window. A self-reinforcing deadlock between a long transaction and autovacuum."
        ),
        "resolution": "Manually vacuumed one shard at a time and added a statement timeout to reconciliation.",
        "runbook": "RB-06",
        "customer_impact": "No direct customer impact. Finance reporting was 3.5 hours late.",
        "mttr_minutes": 210,
        "action_items": [
            _action("dana", "Break the long reconciliation transaction into hourly chunks.", status="open", note="Written again after INC-1231, still open."),
        ],
        "tags": ["postgres", "autovacuum", "bloat", "lock-contention", "reconciliation"],
    },
    # ------------------------------------------------------------ flag rollout
    {
        "id": "INC-1122",
        "service": "checkout-web",
        "severity": "SEV1",
        "status": "resolved",
        "opened": "2026-05-06T18:44:00Z",
        "resolved": "2026-05-06T19:16:00Z",
        "title": "New pricing path rolled out to 100% of traffic in 4 minutes",
        "detected_by": "Synthetic checkout probe",
        "alert_text": (
            "[CRITICAL] checkout-web checkout_success_rate=0.31 over 3m window\n"
            "  service: checkout-web   env: production\n"
            "  flag: new_pricing_path_v2 targeting=100%% ramp=100%%\n"
            "  error: 422 UnprocessableEntity on 68%% of attempts"
        ),
        "timeline": [
            ("18:44", "Checkout success rate drops to 31%."),
            ("18:58", "Sofia finds the flag targeting jumped from 5% to 100% in a single edit."),
            ("19:05", "Runbook RB-12: immediate kill switch."),
            ("19:16", "Flag reverted. Success rate back to 99.4%."),
        ],
        "log_excerpt": (
            "2026-05-06T18:44:03.552Z ERROR [checkout-web] checkout.submit - "
            "422 UnprocessableEntity: rounding_mode missing on quote for currency=SEK\n"
            "2026-05-06T18:44:03.553Z INFO [checkout-web] flags - new_pricing_path_v2 "
            "target=100 ramp=100 previous=5"
        ),
        "root_cause": (
            "A pricing flag was edited from 5% to 100% targeting in the same deploy that "
            "introduced it. The new path required a rounding_mode field that only existed "
            "for 4 of 11 supported currencies, so any request in those currencies returned "
            "422. There was no kill switch, so the revert required a deploy rather than a "
            "flag toggle."
        ),
        "resolution": "Reverted the flag and shipped a kill switch the same day.",
        "runbook": "RB-12",
        "customer_impact": "32 minutes at 69% checkout failure for SEK, NOK and DKK customers.",
        "mttr_minutes": 32,
        "action_items": [
            _action("sofia", "Add a mandatory kill switch to the flag platform and require it for tier-1 services.", status="done"),
            _action("sofia", "Add a pre-deploy check that every flag change from under 20% to over 20% requires review.", status="open", note="Never added; the flag platform has no such rule."),
        ],
        "tags": ["feature-flag", "rollout", "kill-switch", "pricing", "ramp"],
    },
    # ---------------------------------------------------------- clock skew
    {
        "id": "INC-1140",
        "service": "identity-gateway",
        "severity": "SEV2",
        "status": "resolved",
        "opened": "2026-05-24T08:30:00Z",
        "resolved": "2026-05-24T08:58:00Z",
        "title": "Token validation failing on clock skew after an NTP step",
        "detected_by": "Grafana: token_rejections > 500/min",
        "alert_text": (
            "[HIGH] identity-gateway token_rejections_per_min=742\n"
            "  service: identity-gateway   env: production\n"
            "  error: token rejected: used before issued (leeway=0s)\n"
            "  node_time_offset: +38s  ntp_sync_status: unsynchronised"
        ),
        "timeline": [
            ("08:30", "742 token rejections per minute across all clients."),
            ("08:41", "Jonas finds node clock offset of 38 seconds after an NTP step."),
            ("08:52", "Runbook RB-09 equivalent: force NTP resync and widen leeway to 30s."),
            ("08:58", "Rejections returned to baseline."),
        ],
        "log_excerpt": (
            "2026-05-24T08:30:11.002Z WARN [identity-gateway] token.validate - "
            "token used before issued: iat=1753352401 now=1753352439 delta=38s leeway=0\n"
            "2026-05-24T08:30:11.002Z INFO [identity-gateway] ntp - clock drift 38s, "
            "last_sync=2026-05-24T07:12Z"
        ),
        "root_cause": (
            "A kernel upgrade on three nodes reset the clock, and NTP did not re-sync for "
            "18 minutes. The token validator used a zero leeway on nbf and iat, so any "
            "token minted on a correctly-synced node was rejected by a node running 38s fast."
        ),
        "resolution": "Forced NTP resync and set a 30s leeway on time-based claims.",
        "runbook": "RB-15",
        "customer_impact": "28 minutes of elevated 401s for roughly 40% of active sessions.",
        "mttr_minutes": 28,
        "action_items": [
            _action("jonas", "Set leeway=30s on nbf and iat validation.", status="done"),
            _action("jonas", "Alert on ntp_sync_status unsynchronised for more than 5 minutes.", status="open", note="Alert never created."),
        ],
        "tags": ["clock-skew", "jwt", "ntp", "token", "leeway"],
    },
    # ------------------------------------------------------ schema drift
    {
        "id": "INC-1164",
        "service": "ledger-svc",
        "severity": "SEV1",
        "status": "resolved",
        "opened": "2026-06-08T15:17:00Z",
        "resolved": "2026-06-08T16:44:00Z",
        "title": "Blue/green rollback left schema ahead of code",
        "detected_by": "Synthetic write probe",
        "alert_text": (
            "[CRITICAL] ledger-svc write_failures=0.94 over 5m window\n"
            "  service: ledger-svc   env: production   colour=green\n"
            "  error: column \"settlement_state\" does not exist\n"
            "  migration: V0147__add_settlement_state applied, code: pre-V0147 still deployed"
        ),
        "timeline": [
            ("15:17", "Green fleet cannot write. Blue is healthy but was scaled to zero."),
            ("15:40", "Dana identifies a forward-only migration left in place by a rollback."),
            ("16:12", "Runbook RB-13: roll forward with a compatible code build."),
            ("16:44", "Writes recovered. Blue brought back as the active colour."),
        ],
        "log_excerpt": (
            "2026-06-08T15:17:22.114Z ERROR [ledger-svc] jooq - SQLSyntaxError: "
            "column \"settlement_state\" does not exist\n"
            "2026-06-08T15:17:22.115Z INFO [ledger-svc] migrations - applied "
            "V0147__add_settlement_state at 15:11Z, code_version=pre-V0147"
        ),
        "root_cause": (
            "V0147 added a NOT NULL column and deployed green. Green was unhealthy for an "
            "unrelated reason, so the rollback returned to blue, but the migration was not "
            "reverted. Blue's older code did not select the new column, but the ORM's "
            "insert path did, and the column did not exist on the rolled-back schema because "
            "the migration had been marked applied in a separate tracking table."
        ),
        "resolution": "Rolled forward with a build compatible with V0147 and restored blue.",
        "runbook": "RB-13",
        "customer_impact": "87 minutes with all ledger writes rejected. Merchants saw delayed settlement.",
        "mttr_minutes": 87,
        "action_items": [
            _action("dana", "Pair every migration with a tested down-migration or mark it explicitly forward-only.", status="open", note="Forward-only markers exist for 4 of 61 migrations."),
            _action("dana", "Keep blue at 10% during a colour switch so rollback is a traffic shift, not a scale-up.", status="done"),
        ],
        "tags": ["migration", "schema-drift", "rollback", "blue-green", "deploy"],
    },
    # ---------------------------------------------------------- observability
    {
        "id": "INC-1190",
        "service": "reporting-etl",
        "severity": "SEV2",
        "status": "resolved",
        "opened": "2026-06-25T03:10:00Z",
        "resolved": "2026-06-25T05:40:00Z",
        "title": "Log volume filled the disk and took out the very logs we needed",
        "detected_by": "Blind: the alerting pipeline itself was down",
        "alert_text": (
            "[CRITICAL] observability-pipeline DOWN - no data received for 18m\n"
            "  node: log-collector-3   disk: 100%% used (inodes 0)\n"
            "  lost_window: 2026-06-25T02:52Z to 2026-06-25T03:10Z\n"
            "  note: this incident was detected by a human noticing a missing dashboard"
        ),
        "timeline": [
            ("03:10", "A data engineer noticed the Grafana dashboard was empty, not an alert."),
            ("03:34", "Disk on log-collector-3 was full; ingestion had stopped 18 minutes earlier."),
            ("04:20", "Freed disk by truncating rotated logs and restarted the collector."),
            ("05:40", "Backfilled the lost window from the node journal."),
        ],
        "log_excerpt": (
            "2026-06-25T02:51:44.002Z ERROR [log-collector-3] disk - no space left on device\n"
            "2026-06-25T02:51:44.003Z FATAL [log-collector-3] fluent-bit - "
            "output buffer full, dropping 1.4M records/min\n"
            "# this is the last line written before the filesystem stopped accepting writes"
        ),
        "root_cause": (
            "A debug log line was left in reporting-etl that printed one line per row of the "
            "transaction table, producing roughly 1.4M records per minute. The collector's "
            "retention policy keeps 14 days, so the disk filled in under two hours and the "
            "collector stopped accepting writes. Because the alerting pipeline depended on "
            "the same collectors, the outage silenced the very signal needed to diagnose it."
        ),
        "resolution": "Truncated rotated logs, added a disk-usage alert, and removed the debug line.",
        "runbook": "RB-16",
        "customer_impact": "No direct customer impact. 18 minutes of total observability blindness during a live incident.",
        "mttr_minutes": 150,
        "action_items": [
            _action("lena", "Reject merge requests that add per-row logging to a hot path.", status="open", note="Never implemented as an automated check."),
            _action("lena", "Ship a disk-usage alert at 80% on every collector node.", status="done"),
        ],
        "tags": ["observability", "disk", "log-volume", "alerting", "blindspot", "debug-logging"],
    },
    # ------------------------------------------------------ DNS / failover
    {
        "id": "INC-1208",
        "service": "checkout-web",
        "severity": "SEV2",
        "status": "resolved",
        "opened": "2026-07-09T06:22:00Z",
        "resolved": "2026-07-09T07:05:00Z",
        "title": "Partial regional failover left clients on a dead DNS answer",
        "detected_by": "Synthetic probe from eu-west",
        "alert_text": (
            "[HIGH] checkout-web dns_resolution_failure=0.28 over 5m window\n"
            "  service: checkout-web   env: production\n"
            "  resolver_cache_ttl: 300s   record: checkout.northwind.com\n"
            "  note: 28%% of clients cached the pre-failover answer"
        ),
        "timeline": [
            ("06:22", "eu-central-1 drained for a planned node patch; DNS repointed to eu-west-1."),
            ("06:35", "Sofia sees 28% failures concentrated on clients behind caching resolvers."),
            ("06:51", "Runbook RB-10: lower TTL and force a resolver flush via the edge provider."),
            ("07:05", "Failure rate decayed to baseline as the old TTL expired."),
        ],
        "log_excerpt": (
            "2026-07-09T06:22:31.220Z ERROR [edge] upstream - 502 from origin "
            "10.60.2.14 (drained node) client_resolved_ip=10.60.2.14\n"
            "2026-07-09T06:22:31.221Z INFO [edge] dns - record checkout.northwind.com "
            "ttl=300 resolver_cache_age=280s"
        ),
        "root_cause": (
            "A planned regional drain repointed DNS at the surviving region but the record TTL "
            "was 300 seconds and the edge provider's own cache was 280 seconds old at the moment "
            "of the switch. Clients that resolved just before the change kept the drained node "
            "address for up to five minutes with no fallback, because the origin pool had been "
            "scaled down ahead of the DNS cutover."
        ),
        "resolution": "Lowered the record TTL to 60s, flushed the edge resolver, and sequenced the drain after the DNS change.",
        "runbook": "RB-10",
        "customer_impact": "43 minutes of intermittent checkout failures affecting 28% of European clients.",
        "mttr_minutes": 43,
        "action_items": [
            _action("sofia", "Require the origin pool to stay at 100% for one TTL after a DNS change.", status="open", note="Written in the runbook text but not enforced by the drain script."),
        ],
        "tags": ["dns", "failover", "ttl", "edge", "regional", "cache"],
    },
    # ------------------------------------------------------- blocked threads
    {
        "id": "INC-1219",
        "service": "inventory-sync",
        "severity": "SEV3",
        "status": "resolved",
        "opened": "2026-07-22T22:05:00Z",
        "resolved": "2026-07-22T22:51:00Z",
        "title": "Thread starvation from a blocking call on a bounded pool",
        "detected_by": "Grafana: sync_thread_active == pool_max for 10m",
        "alert_text": (
            "[WARN] inventory-sync sync_threads_active=32 pool_max=32 for 10m\n"
            "  service: inventory-sync   env: production\n"
            "  error: throughput=0 rows/s while all threads blocked\n"
            "  blocked_on: carrier_api_http 429 with no backoff"
        ),
        "timeline": [
            ("22:05", "Sync throughput drops to zero with every worker thread blocked."),
            ("22:26", "Lena finds all 32 threads waiting on a carrier HTTP call with no timeout."),
            ("22:44", "Runbook RB-09: add a connect timeout and release the pool."),
            ("22:51", "Throughput restored; 3.1M rows synced overnight."),
        ],
        "log_excerpt": (
            "2026-07-22T22:05:12.004Z WARN [inventory-sync] pool - 32/32 threads active, "
            "0 idle, queue_depth=91822\n"
            "2026-07-22T22:05:12.005Z WARN [inventory-sync] carrier.api - HTTP 429, "
            "no backoff applied, timeout=none"
        ),
        "root_cause": (
            "The carrier API started returning 429 during a partner-side traffic spike. The "
            "client had neither a timeout nor backoff, so each of the 32 sync threads blocked "
            "indefinitely on the HTTP call. With a bounded pool, the entire service stalled "
            "even though the local database was healthy."
        ),
        "resolution": "Added a 5s connect timeout, exponential backoff, and released the pool to 48 threads.",
        "runbook": "RB-09",
        "customer_impact": "46 minutes of delayed warehouse sync. No customer-facing error.",
        "mttr_minutes": 46,
        "action_items": [
            _action("lena", "Lint rule: no outbound HTTP call without an explicit timeout.", status="open", note="Rule proposed twice, never added to the linter."),
        ],
        "tags": ["thread-pool", "blocking-io", "timeout", "backoff", "third-party", "starvation"],
    },
    # -------------------------------------------------------- clock/regression
    {
        "id": "INC-1224",
        "service": "payments-api",
        "severity": "SEV2",
        "status": "resolved",
        "opened": "2026-07-30T12:03:00Z",
        "resolved": "2026-07-30T12:49:00Z",
        "title": "p99 latency regression from an N+1 in the refund path",
        "detected_by": "Prometheus: http_request_duration_p99 > 1800ms",
        "alert_text": (
            "[HIGH] payments-api refund_p99_ms=2210 over 10m window\n"
            "  service: payments-api   env: production\n"
            "  deploy: payments-api@d41f8b2 deployed 2026-07-30T11:41Z\n"
            "  db.statements_per_request: 47 (baseline 8)\n"
            "  db.query_time_ratio: 0.91"
        ),
        "timeline": [
            ("12:03", "Refund p99 breaches 1.8s. 22 minutes after deploy d41f8b2."),
            ("12:20", "Aisha bisects to commit 7c1e9a0, which lazy-loads refund reasons."),
            ("12:36", "Runbook RB-03 plus a targeted rollback of d41f8b2."),
            ("12:49", "p99 back to 210ms. No customer-visible errors."),
        ],
        "log_excerpt": (
            "2026-07-30T12:03:44.118Z WARN [payments-api] perf - refund p99=2210ms "
            "statements_per_request=47 db_time_ratio=0.91\n"
            "2026-07-30T12:03:44.119Z INFO [payments-api] sql - N+1 detected on "
            "RefundReason: 46 additional selects per refund"
        ),
        "root_cause": (
            "Commit 7c1e9a0 replaced a fetch join on RefundReason with a lazy association, "
            "turning one refund lookup into 47 statements. The connection pool absorbed it, "
            "so there were no errors, only latency. It reached production because the "
            "performance test suite has no per-request statement count assertion, which was "
            "the action item from the April pool incident and still had not been added "
            "outside payments-api."
        ),
        "resolution": "Rolled back d41f8b2 and restored the fetch join.",
        "runbook": "RB-03",
        "customer_impact": "46 minutes of slow refunds. Support received 212 tickets.",
        "mttr_minutes": 46,
        "action_items": [
            _action("aisha", "Add a per-request statement count assertion to the performance suite for every service.", status="open", note="Third occurrence of the same action. Still open."),
        ],
        "tags": ["n+1", "latency", "regression", "deploy", "performance", "orm"],
    },
    {
        "id": "INC-1229",
        "service": "payout-worker",
        "severity": "SEV3",
        "status": "resolved",
        "opened": "2026-08-13T02:40:00Z",
        "resolved": "2026-08-13T03:12:00Z",
        "title": "Nightly payout batch failed twice on a single malformed merchant record",
        "detected_by": "Airflow task failure",
        "alert_text": (
            "[WARN] payout-worker batch_nightly task failed attempt=2\n"
            "  service: payout-worker   env: production\n"
            "  error: KeyError: 'settlement_account' on merchant MER-88213\n"
            "  batch_progress: 41%% of 2,918 merchants"
        ),
        "timeline": [
            ("02:40", "First attempt fails at 41% on MER-88213."),
            ("02:58", "Marcus finds the merchant predates the settlement_account field."),
            ("03:12", "Runbook RB-05: skip and quarantine the record, batch completes."),
        ],
        "log_excerpt": (
            "2026-08-13T02:40:11.004Z ERROR [payout-worker] batch - KeyError: "
            "'settlement_account' merchant=MER-88213 created=2019-04-02\n"
            "2026-08-13T02:58:33.900Z INFO [payout-worker] batch - quarantined 1 record, "
            "resuming from offset 1196"
        ),
        "root_cause": (
            "One merchant record from 2019 predates the settlement_account field, and the "
            "batch task had no per-record isolation, so a single bad record failed the whole "
            "run. The failure was deterministic and had been happening quietly at 0.4% of "
            "batches before the merchant moved to the top of the payout order."
        ),
        "resolution": "Quarantined the record, completed the batch, and added a per-record try/except.",
        "runbook": "RB-05",
        "customer_impact": "31-minute delay to nightly payouts. One merchant paid late.",
        "mttr_minutes": 31,
        "action_items": [
            _action("marcus", "Add a schema-version check before the batch touches a legacy record.", status="open", note="Never started."),
        ],
        "tags": ["batch", "legacy-data", "quarantine", "airflow", "merchant"],
    },
    {
        "id": "INC-1234",
        "service": "webhooks-relay",
        "severity": "SEV3",
        "status": "resolved",
        "opened": "2026-08-20T10:15:00Z",
        "resolved": "2026-08-20T11:30:00Z",
        "title": "Silent webhook delivery loss during a relay restart",
        "detected_by": "Partner reported missing events",
        "alert_text": (
            "[WARN] webhooks-relay in_flight=0 queue_depth=0 but sent_last_hour=0\n"
            "  service: webhooks-relay   env: production\n"
            "  restart: 2026-08-20T10:11Z reason=deploy\n"
            "  note: metrics looked healthy because the queue was empty"
        ),
        "timeline": [
            ("10:15", "A partner reports missing order events for 4 minutes."),
            ("10:38", "Tomás finds the relay holds deliveries in memory only, not on disk."),
            ("11:05", "Runbook RB-05: replay from the partner's event ids."),
            ("11:30", "All 6,204 events replayed and verified."),
        ],
        "log_excerpt": (
            "2026-08-20T10:11:02.001Z INFO [webhooks-relay] shutdown - graceful, "
            "draining in_flight=0\n"
            "2026-08-20T10:11:04.500Z INFO [webhooks-relay] shutdown - 6,204 buffered "
            "deliveries discarded, not persisted"
        ),
        "root_cause": (
            "The relay buffered deliveries in memory and discarded them on shutdown. Its "
            "health metrics were derived from the queue, which was empty, so the deploy "
            "looked clean. The only signal that anything was lost came from an external "
            "partner noticing a gap, which is a four-minute detection delay that no metric "
            "would have caught."
        ),
        "resolution": "Replayed from partner event ids and began persisting the buffer to disk.",
        "runbook": "RB-05",
        "customer_impact": "6,204 partner webhooks delayed by 4 minutes and replayed.",
        "mttr_minutes": 75,
        "action_items": [
            _action("tomas", "Persist the outbox to disk before acknowledging a delivery as accepted.", status="open", note="Design agreed, not implemented."),
        ],
        "tags": ["webhook", "data-loss", "restart", "outbox", "observability", "silent-failure"],
    },
]


def incident_count() -> int:
    return len(INCIDENTS)


def open_action_items() -> list[dict[str, str]]:
    """Every postmortem action that was written down and never closed.

    This is the backlog Faultline exists to reason over. Several are the same
    action written for the third time.
    """
    out: list[dict[str, str]] = []
    for inc in INCIDENTS:
        for act in inc["action_items"]:
            if act["status"] == "open":
                out.append(
                    {
                        "incident_id": inc["id"],
                        "service": inc["service"],
                        "owner": act["owner"],
                        "text": act["text"],
                        "note": act["note"],
                        "opened": inc["opened"],
                    }
                )
    return out


def by_id(incident_id: str) -> dict[str, Any] | None:
    for inc in INCIDENTS:
        if inc["id"] == incident_id:
            return inc
    return None


# The alert used in the live demo. It is deliberately a *different* service and a
# *different* symptom from INC-1042 and INC-1188, so matching it requires joining
# the IAM thread across three incidents rather than matching on a string.
LIVE_ALERT = {
    "alert_id": "ALR-4471",
    "received": "2026-09-28T09:14:22Z",
    "service": "payout-worker",
    "severity": "SEV2",
    "source": "Prometheus / kube-prometheus",
    "title": "payout-worker auth failures climbing, no deploy in 30 days",
    "alert_text": (
        "[HIGH] payout-worker auth_failure_rate=0.44 over 10m window\n"
        "  service: payout-worker   env: production   region: eu-west-1\n"
        "  error: AccessDenied - not authorized to perform: sts:AssumeRole on "
        "resource arn:aws:iam::9182:role/nw-merchant-ledger\n"
        "  successful_payouts_last_30d: 1289401\n"
        "  last_deploy: 2026-08-29T14:02:00Z (30 days ago)\n"
        "  iam:role_trust_policy_last_modified: 2026-05-30T02:11:00Z\n"
        "  iam:CredentialLastRotated=2026-09-17T02:00:00Z\n"
        "  on_call: Rahul Menon (Core Money)"
    ),
    "raw_evidence": [
        "2026-09-28T09:14:19.004Z ERROR [payout-worker] aws.creds - assumeRole failed: "
        "AccessDeniedException: not authorized to perform: sts:AssumeRole on "
        "arn:aws:iam::9182:role/nw-merchant-ledger",
        "2026-09-28T09:14:19.005Z INFO [payout-worker] aws.creds - last successful "
        "assumeRole=2026-09-17T02:00:04Z (11 days ago)",
        "2026-09-28T09:14:22.000Z ERROR [payout-worker] batch - 41 of 2918 merchants "
        "queued, blocked on settlement auth",
    ],
    "note": (
        "Ships with no deploy in 30 days and 11 days since the last successful "
        "credential use, so a code change cannot explain it. That gap is the tell."
    ),
}

# Applied after the operator resolves the live incident. Retaining this is what
# makes the fingerprint stronger, so the same alert next month matches harder.
LIVE_RESOLUTION = {
    "root_cause": (
        "The wildcard trust policy was still in place on the payout-worker role because the "
        "sweep action written after INC-1042 in March and again after INC-1188 in June was "
        "never completed. The 11-day-old successful assumeRole was a cached token; the "
        "underlying trust had been wrong since May 30, and the service only noticed when the "
        "token needed to be used again."
    ),
    "resolution": (
        "Applied runbook RB-07 and replaced the wildcard Principal with an explicit allow-list. "
        "Then, for the first time, actually ran the sweep across inventory-sync and "
        "webhooks-relay, both of which still carried the wildcard."
    ),
    "runbook": "RB-07",
    "action_items": [
        {
            "owner": "Jonas Weber",
            "text": "Change terraform/modules/service-role so the wildcard is never the default.",
            "status": "open",
            "note": "Fourth time written. This time flagged as a release blocker.",
        },
        {
            "owner": "Rahul Menon",
            "text": "Add a synthetic sts:AssumeRole probe every 10 minutes so a cached token cannot mask a broken trust policy.",
            "status": "open",
            "note": "New action, derived directly from the 11-day blind window.",
        },
    ],
}
