# The data, and why it is invented

The dataset is the single most important thing in this project. This page explains what is in it,
where each piece came from, and why the measurements on it mean what they mean.

---

## The short answer

The company, the people and the incidents are **made up**. Every failure mode is **real**, lifted
from something that actually happened in a real production system.

Both halves matter. The first means nobody's bad afternoon is being retold. The second means the
agent is being tested on failures that genuinely occur, not toy problems.

---

## The company

**Northwind Commerce.** A mid-sized commerce platform. Ten services across four teams, roughly 130
service instances, an SLO of 99.95% on the payments path.

| Service | Team | What it does | Why it matters |
| --- | --- | --- | --- |
| `payments-api` | Core Money | Card authorisation and capture | Tier 1. Customers cannot buy if this is down |
| `payout-worker` | Core Money | Nightly merchant payouts | Tier 1. Merchants go unpaid |
| `checkout-web` | Storefront | Cart and checkout | Tier 1. The whole point of the shop |
| `identity-gateway` | Platform | Logins and token checks | Tier 1. Nothing works without it |
| `ledger-svc` | Core Money | Double-entry accounting | Tier 1. Must be exactly right |
| `fraud-scoring` | Risk | Real-time risk score | 120ms budget |
| `inventory-sync` | Fulfilment | Warehouse stock | Wrong stock means wrong promises |
| `webhooks-relay` | Platform | Outbound partner notifications | Partners notice gaps |
| `search-indexer` | Storefront | Product catalogue search | Annoying, not fatal |
| `reporting-etl` | Data | Nightly finance reporting | Misses a morning standup |

Ten engineers with names, owning the remediation actions. They are fictional people. The names are
internationally varied on purpose, so nothing reads as a stereotype.

---

## The spine: one mistake, three incidents

The dataset is built so that the most interesting behaviour is *forced* by its structure. One
underlying mistake runs through three incidents, across three services, across five months, in three
different services that have nothing visibly in common.

### Act one. March 14. `payments-api`. SEV1.

A wildcard identity setting. An automated credential rotation exposes it. 41 minutes of failed
card payments. 1,204 orders retried, 87 abandoned.

The postmortem contains three actions:

| Action | Status | Note |
| --- | --- | --- |
| Sweep every service for the wildcard trust policy | **never done** | "Never started" |
| Add a synthetic check every 10 minutes | done | |
| Change the shared Terraform module so the wildcard is not the default | **never done** | "Module never updated; still the default today" |

### Act two. June 2. `checkout-web`. SEV2.

The same setting, three months later, in a different service, presenting completely differently.
The on-call engineer spends 17 minutes investigating a deploy from four days earlier, because the
error mentions a token.

44 minutes of failed checkouts. An estimated 214,000 EUR in lost carts.

The postmortem contains:

| Action | Status | Note |
| --- | --- | --- |
| Re-run the wildcard trust sweep across all remaining services | **never done** | "Third time this action has been written. Still not done." |

### Act three. September 28. `payout-worker`. SEV2. The live demo.

Third service, same setting. And the cleverest version: the service has **no deploy in 30 days** and
**no successful credential use in 11 days**. So the fault has been wrong since May, and a cached
token hid it for nearly two weeks. A code change cannot explain it. That gap is the tell.

This is the alert you see in the demo. Faultline connects all three, reads the two unclosed sweeps,
and reports that `inventory-sync` and `webhooks-relay` are still exposed.

**Why this shape matters.** An agent cannot get this right from the alert text alone. It has to hold
three incidents in a relationship, plus two separate to-do items, plus the current state of two
other services, and join them. That is the capability being demonstrated, and the data is built to
require it.

---

## The other eighteen incidents

Every one is a failure mode taken from a real postmortem. The most interesting ones:

| Incident | What really happened |
| --- | --- |
| `INC-1190` | A debug log statement printed one line per row. It filled the logging collector's disk, which silenced the alerting pipeline, so the team lost the ability to see any incident for 18 minutes. Found out because a data engineer noticed an empty dashboard |
| `INC-1122` | A feature flag was edited from 5% to 100% in the same deploy that introduced it. No kill switch existed, so reverting needed a full deploy. Failed for every customer in 3 of 11 supported currencies |
| `INC-1164` | A blue/green rollback left a database migration applied that the older code did not expect. 87 minutes with all ledger writes rejected |
| `INC-1155` | A 30-day internal certificate expired. The auto-renewal job had been failing silently for 14 days because it pointed at a certificate authority that had been migrated away. The renewal request was in the logs the entire time and nobody alerted on it |
| `INC-1107` | A nightly job held a long transaction, which blocked database vacuum, which slowed the job, which made it hold the transaction longer. Table bloat reached 61% |
| `INC-1224` | A commit replaced a joined query with a lazy load, turning 1 database call into 47. The connection pool absorbed it, so there were no errors, only latency. It shipped because the performance test suite had no assertion on query count, which was itself an unclosed action from an earlier incident |
| `INC-1219` | An outbound API call with no timeout blocked all 32 worker threads. The database was completely healthy. The service was nonetheless fully stalled |
| `INC-1231` | A topic was widened from 6 to 24 partitions. The consumer was hardcoded to 6. Rebalances every 2 minutes for four hours, rewriting all offsets each time |

Notice the recurring shape: in five of these, the real fix is a check or a guard that was itself
proposed in an earlier postmortem and never added. That is not a coincidence in the writing. It is
the argument.

---

## The unclosed actions

Nineteen in total, and they are the point of the dataset. A few of the recurring ones:

| Action | Raised in | Times | Owner |
| --- | --- | --- | --- |
| Sweep services for the wildcard trust policy | INC-1042, INC-1188 | 2, then 4 | Jonas Weber, Marcus Feld |
| Change the Terraform module default | INC-1042, and again after the live incident | 4 | Jonas Weber |
| Propagate the connection pool size through the shared module | INC-1099, INC-1203 | 2 | Aisha Bello |
| Per-request query count assertion in the performance suite | INC-1099, INC-1224 | 2 | Aisha Bello |
| Add TTL jitter to cached keys | INC-1130 | 1, incomplete | Kenji Watanabe |
| Lint rule: no outbound HTTP without a timeout | INC-1219 | 1 | Lena Kovač |

Three of these have been written twice or more. `open_action_items()` in `app/corpus.py` flattens
them into a single backlog, and that backlog is what the agent reasons over.

---

## The infrastructure state records

Four conditions are recorded as currently wrong somewhere. These are what make "you are still
exposed" a fact rather than a guess.

| Condition | Still affects | Fixed in | Why it keeps coming back |
| --- | --- | --- | --- |
| Wildcard identity trust policy | `payout-worker`, `inventory-sync`, `webhooks-relay` | `payments-api`, `checkout-web`, `ledger-svc` | The shared Terraform module still has the wildcard as its default and nobody changed it |
| Connection pool left at the default size | `inventory-sync`, `reporting-etl` | `payments-api` | The change was applied by hand to one service only |
| Consumer concurrency hardcoded below partition count | `webhooks-relay`, `fraud-scoring` | none | Manual change only, no guard against a topic being widened |
| Cache keys written with a flat TTL | `checkout-web`, `fraud-scoring` | `search-indexer` | Only one service was patched |

The agent never invents this list. It names the condition and the code reads the record.

---

## Why not use real incident data

**Because the interesting structure has to be constructed.** The capability being shown is joining
incidents across months and services, and proving the fix was never completed. Real public
postmortem data is thin, inconsistent, and almost never contains its own open action items. You
would get a demo of "finds similar documents", which is not the demo.

**Because a controlled dataset is checkable.** Because I wrote the answer key myself, I can tell you
exactly which pairs share a root cause and exactly which recall got wrong. With scraped data I could
only show a vibe.

**Because nothing real gets exposed.** Any real incident data contains customer names, revenue
figures, and details of unpatched vulnerabilities.

What is *not* invented: the failure modes. Every one is a real class of production failure, and
several are ones any on-call engineer will recognise from their own week.

---

## If you want to use your own data

Replace the contents of `INCIDENTS` in `app/corpus.py`. The structure each entry needs:

| Field | Required | Notes |
| --- | --- | --- |
| `id`, `service`, `severity`, `status` | yes | |
| `opened`, `resolved` | yes | ISO format with `Z`. These drive temporal retrieval, so keep the real values |
| `title`, `detected_by` | yes | |
| `alert_text` | yes | Verbatim. This is what the agent matches against |
| `timeline`, `log_excerpt` | yes | Verbatim is much better than summarised |
| `root_cause`, `resolution`, `runbook` | yes | The runbook id is a high-signal keyword |
| `customer_impact`, `mttr_minutes` | yes | |
| `action_items` | yes | Each needs `owner`, `text`, `status` of `open` or `done` |
| `tags` | no | Free-form, used for filtering |

Then update `CLUSTERS` in `app/analysis.py` with your own answer key, and re-seed:

```bash
curl -X POST "localhost:8000/api/setup?force=true"
```

The `force=true` deletes and rebuilds the banks, so old memories do not linger and corrupt the
measurement.

Next: [HINDSIGHT_PLAIN.md](HINDSIGHT_PLAIN.md)
