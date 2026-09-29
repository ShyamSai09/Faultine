# How Hindsight memory is used in Faultline

This is the document the judges asked for. It explains what is stored, why each
piece of Hindsight is used where it is, and what would break if you removed it.

---

## 1. What is stored

Two memory banks, and the split is deliberate rather than cosmetic.

| Bank | Holds |
| --- | --- |
| `faultline-incidents` | 19 incident records (alert as fired, timeline, log excerpt, root cause, resolution, runbook, customer impact, postmortem actions) and 4 latent-infrastructure-state records |
| `faultline-team` | The 19 postmortem action items that were never completed, each with its owner, the incident that raised it, and the date |

Hindsight isolates banks strictly. That is what lets Faultline prove the split
matters: a query about *what broke* is never diluted by chatter about *who owes
what*, and the team bank can be reasoned about as a commitment ledger on its own.

A third bank, `faultline-control-empty`, is deliberately never written to. It
exists so the before/after comparison runs the identical query through the
identical model and retrieval stack with zero memories. See §6.

## 2. Retain — the write path

Each incident is written as one structured record, not as a free-form blob:

```
INCIDENT INC-1042 — Card authorisation returning 503 for 41 minutes
Service: payments-api  Severity: SEV1  Status: resolved
Opened: 2026-03-14T09:12:00Z  Resolved: 2026-03-14T09:53:00Z  Time to resolve: 41 minutes
Detected by: Datadog monitor: payments.auth.error_rate > 2% for 5m

ALERT AS IT FIRED:
[HIGH] payments-api auth_error_rate=0.37 over 5m window
  error: AccessDenied - User: arn:aws:sts::9182:assumed-role/svc-payments/rotator ...

TIMELINE: ...
LOG EXCERPT: ...
ROOT CAUSE: ...
RUNBOOK USED: RB-07
POSTMORTEM ACTION ITEMS:
  [NEVER COMPLETED] Sweep every service for the wildcard Principal={"AWS": "*"} ... (owner: Jonas Weber)
```

Three things make this work:

- **`retain_mission` tells the extractor what to keep.** The incident bank's
  retain mission asks for services, exact dates, symptoms, root cause, runbook,
  impact, and each action with its owner and completion status, and asks that
  incident ids be kept as entities so records can be linked. Without that
  instruction the extractor produces prose and the ids stop being joinable.
- **`timestamp` is passed explicitly.** The incident's real `opened` time, not
  the time it was ingested. Temporal retrieval is one of Hindsight's four recall
  arms, and it is only correct if the stored timestamps are the historical ones.
- **`metadata` and `tags` carry the structured fields** (`incident_id`,
  `service`, `severity`, `kind`) so the UI and the measurement can filter
  without asking an LLM.

## 3. Observations — the reason this is memory and not search

This is the part that does the actual work.

Hindsight consolidates retained facts into **observations**: deduplicated,
evidence-backed beliefs with a proof count, refined rather than overwritten as
new evidence arrives. The incident bank's `observations_mission` asks for
exactly the thing Faultline needs:

> Consolidate incident facts into beliefs about how this organisation fails.
> Group incidents that share a root cause. Track remediation actions across
> incidents so that an action raised once and never completed stays visible.
> Preserve history: when a fact changes, keep the earlier fact and mark the
> change rather than overwriting it.

The live triage surfaces a consolidated observation verbatim in the right-hand
pane:

> **OBSERVATION** — Services payout-worker, inventory-sync, and webhooks-relay
> are currently identified as carrying the insecure IAM role trust policy.

That single sentence is the product. It is not a retrieved document; it is a
belief the bank formed across four separate records, and it will be rewritten —
not appended to — the next time the evidence changes.

A vector search cannot produce it, because it requires noticing that four
documents describing four different services are all describing one condition.

## 4. Recall — four arms, not one

```python
res = client.recall(
    bank_id=BANK_INCIDENTS,
    query=_triage_query(alert),
    budget="high",
    max_tokens=4096,
    prefer_observations=True,
)
```

The query is the alert plus the question, so no arm is wasted:

- **Semantic** finds the March IAM incident from today's error text.
- **BM25** is what actually pins `sts:AssumeRole` and `RB-07`; those exact
  strings are rare and high-signal.
- **Graph** is what links `payout-worker` → `nw-merchant-ledger` → the trust
  policy → the Terraform module → the two services that never got patched.
- **Temporal** is what lets it say *this happened in March and again in June*,
  which is the difference between a pattern and a coincidence.

`prefer_observations=True` puts the consolidated beliefs at the top of the
result set, ahead of raw facts.

## 5. Directives — shaping the reflection, not the retrieval

Directives are scoped to `reflect` and are how the agent is made *careful*:

| Directive | Priority | Why it exists |
| --- | --- | --- |
| `no-invention` | 20 | If the memory does not contain it, say so. A wrong root cause during an outage costs hours, so an admission beats a confident guess. |
| `cite-evidence` | 10 | Every claim must carry an incident id and a date. |
| `prefer-recent` | 10 | When two memories conflict, the newer one is right and the older one describes how things used to be. |
| `surface-unclosed-work` | 10 | If a failure mode being reasoned about has remediation that was never completed, name it and name the owner. |

`surface-unclosed-work` is the directive that makes the project what it is. It
turns "here is what broke" into "here is what broke, and the fix for it was
written down twice and never done".

## 6. Reflect — and an honest control group

The triage question asks for the failure mode, the prior incidents sharing the
root cause, the runbook, which other services still carry the fault, and which
remediation was never completed.

`reflect` accepts a `response_schema`, and Faultline passes one. **Hindsight
Cloud ignores it and returns prose** — a real finding, documented in
`app/memory.py`. So the contract is carried in the prompt instead and parsed
deterministically by `_parse_triage`. Parsing degrades rather than raising: a
partial answer is still worth showing mid-incident.

The before/after comparison runs the *same* query against `faultline-control-empty`:

```
memory on    MATCH: 100   INCIDENTS: INC-1042, INC-1188   RUNBOOK: RB-07   OPEN_ACTION: written 2×
memory off   MATCH: 0     INCIDENTS: none                 RUNBOOK: none    OPEN_ACTION: none
```

Note that the memory-off run still correctly guesses "IAM trust policy" from the
error string. That is the honest version of the argument: the model is not
stupid. What it cannot do without memory is know that this has happened twice
before, which runbook fixed it, and that the sweep which would have prevented
it is still open.

## 7. Mental models — cheap, always-current expertise

Three mental models are installed on the incident bank with
`trigger={"mode": "delta", "refresh_after_consolidation": True}`, so Hindsight
rewrites them in the background as evidence accumulates:

| Id | What it answers |
| --- | --- |
| `failure-fingerprints` | What failure modes exist, their symptoms, affected services, dates, root cause, runbook, and how many incidents each has caused |
| `recurrence-risk` | Which services are currently exposed to a failure mode that has already caused an outage elsewhere |
| `open-remediation` | Which action items were never completed, grouped by underlying problem, with how many times each has now been written down |

Reading one is a **database read, not an LLM call**. That is what makes it
affordable to consult on every request, and it is why the right-hand pane can
show live, consolidated expertise rather than a cached string.

## 8. Deterministic grounding — where I stopped trusting the model

The model reliably identified the failure mode, the two prior incidents and the
runbook. It did **not** reliably know which services were still exposed: asked to
list them, it named whichever services appeared in the incidents it had just
cited — including `payments-api` and `checkout-web`, which an engineer had
already patched.

Its reasoning was defensible. It was also wrong, and sending on-call after a
fixed service costs time during an outage.

So Faultline does not ask. The model returns which latent condition the alert
matches:

```
STATE: iam_role_trust_policy
```

and `_exposure_from_corpus` builds the exposed-services list from the recorded
latent state, using the model's prose only as the explanation. The set is ground
truth; the reasoning is the model's. This is the most useful thing I learned
building it: **let the model do the judgement and the code do the bookkeeping.**

## 9. The measured result

`app/analysis.py` scores recall against a hand-written answer key
(`CLUSTERS`), because "the agent gets better" is not a claim anyone should take
on trust.

```
overall recall: 83%   found 5/6 sibling incidents   5 incidents measured   7 clusters
```

One genuine miss: **INC-1219** (32 sync threads blocked on an HTTP call with no
timeout) versus **INC-1211** (webhook relay burning a daily quota retrying 429s
with no backoff). Same anti-pattern, almost no shared vocabulary. The miss is
shown in the UI rather than hidden, and the answer key was itself cut from 10
clusters to 7 after three pairs turned out to share a theme but not a root
cause. A smaller honest key beats a larger flattering one.

The measurement costs no LLM calls, because `recall` ranks locally.

## 10. What would break without Hindsight

- **Observation consolidation** — the "still exposed elsewhere" panel is
  impossible. Cross-document belief formation is the product.
- **Temporal retention** — an incident retained today but stamped today cannot
  support "this also happened in March".
- **Bank isolation** — the two-bank design and the control group both depend on
  strict isolation.
- **Mental models** — reading consolidated expertise for free is what makes it
  usable on every request instead of a background job.
- **Directives** — `no-invention` is what stops the agent inventing a plausible
  root cause, which during an outage is worse than silence.

## Links

- [Hindsight repository](https://github.com/vectorize-io/hindsight)
- [Hindsight documentation](https://hindsight.vectorize.io/)
- [What is agent memory](https://vectorize.io/what-is-agent-memory)
