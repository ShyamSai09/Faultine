# We wrote an agent that finds outages you haven't had yet

The postmortem was filed on 14 March. It contained a remediation action: sweep every service for the wildcard IAM trust policy that had just cost us 41 minutes of failed card authorisations. Nobody did it.

On 2 June a different service broke with a different symptom — checkouts returning 401 instead of 503s — and the same root cause. A second postmortem was filed. It contained the same sweep, rewritten, in slightly different words. Nobody did that one either.

On 28 September a third service woke up with `AccessDenied` on `sts:AssumeRole`. Nobody was paged for the other two. They were just waiting for their turn.

The interesting part is not that the outage happened. It's that the evidence needed to predict it existed in three separate documents and was never joined. Vector search over your postmortems finds the *document* that looks similar. It does not tell you that the bullet point in March is still open, and that two other services are running the same broken configuration right now.

That's the thing [Hindsight](https://github.com/vectorize-io/hindsight) turned out to do better than I expected, and it's what the rest of this is about.

## What we built

An on-call triage agent. An alert fires, and the agent answers five questions:

1. Have we seen this before?
2. Which prior incidents share the root cause?
3. Which runbook fixed them?
4. **Which other services are still carrying the same fault, and have not broken yet?**
5. **Which postmortem actions for this failure mode were written down and never completed?**

Questions 4 and 5 are the product. Everything else is table stakes.

## The memory layout

Two Hindsight banks, and the split is load-bearing rather than tidy:

| Bank | Holds |
| --- | --- |
| `faultline-incidents` | 19 incident records, plus 4 latent-infrastructure-state records |
| `faultline-team` | The 19 postmortem actions that were never completed, with owners and dates |

Hindsight isolates banks strictly. That isolation is what lets a query about *what broke* avoid being diluted by chatter about *who owes what*, and it's what makes the fifth question answerable at all: the join runs from an incident in one bank to an action item in the other.

Writes go in as structured records with the historical timestamp, not ingestion time, because temporal retrieval is one of Hindsight's four recall arms and it's only correct if the stored times are real:

```python
self.client.retain(
    bank_id=BANK_INCIDENTS,
    content=incident_record,          # alert as fired, timeline, log, cause, actions
    context=f"postmortem {inc['id']} ({inc['service']}, {inc['severity']})",
    timestamp=_parse_ts(inc["opened"]),  # 2026-03-14, not today
    metadata={"incident_id": inc["id"], "service": inc["service"], "kind": "postmortem"},
    tags=inc["tags"],
)
```

The bank's `retain_mission` matters more than it looks. Left to itself the extractor writes prose, and then incident ids stop being joinable entities. Asking it explicitly to extract owners, runbooks and completion status, and to keep incident ids as entities, is what makes the graph traversable.

## Where observations do the work

This is the part I didn't expect to be the whole ballgame.

Hindsight consolidates retained facts into **observations**: deduplicated, evidence-backed beliefs with a proof count, refined rather than overwritten as new evidence arrives. We set the incident bank's `observations_mission` to ask for exactly what we needed:

> Consolidate incident facts into beliefs about how this organisation fails. Group incidents that share a root cause. Track remediation actions across incidents so that an action raised once and never completed stays visible. Preserve history: when a fact changes, keep the earlier fact and mark the change rather than overwriting it.

During a live triage, this comes back as a single sentence in the side panel:

> **OBSERVATION** — Services `payout-worker`, `inventory-sync`, and `webhooks-relay` are currently identified as carrying the insecure IAM role trust policy.

Four documents, describing four different services, in four different months, collapsed into one belief. And it gets *rewritten* — not appended to — when the evidence changes. A retrieval system cannot do that, because the artefact that answers the question was never in any of the source documents.

The recurring-model mental model, which Hindsight maintains in the background, is blunter:

> The following services have been identified as carrying known failure modes that have previously resulted in production outages. These conditions remain in place due to uncompleted remediation work from past incidents.

## The part where the model was wrong, and I stopped asking it

Early version, the agent listed every service mentioned in the incidents it had just cited as still exposed. Its reasoning was defensible — all of them are built from the same vulnerable Terraform module. It was also wrong, because two of them had already been patched by hand.

That matters more than it sounds. Telling on-call to chase a service you already fixed costs real minutes during an outage, and it destroys trust in a tool whose whole value proposition is being right about the past.

So I stopped asking. The model now returns only *which* latent condition matches:

```
STATE: iam_role_trust_policy
```

and code builds the exposed set from the recorded state, using the model's prose as the explanation. The set is ground truth; the judgement is the model's.

**Let the model do the judgement and the code do the bookkeeping.** That was the single most useful design correction in the project, and I'd reach for it again on any agent that mixes inferred reasoning with recorded state.

## Proving it, instead of asserting it

"Memory makes the agent better" is not something anyone should take on trust, so I scored it. Every incident is in a hand-labelled cluster of shared root cause; for each one, ask Hindsight to `recall` the failure mode and check which true siblings come back. No LLM call involved — `recall` ranks locally with BM25, the entity graph, temporal filters and a cross-encoder.

```
overall recall: 83%    5/6 sibling incidents recovered    5 incidents measured    7 clusters
```

One genuine miss, which I'd rather show than hide. `INC-1219` was 32 sync threads blocked on an HTTP call with no timeout. `INC-1211` was a webhook relay burning its entire daily quota retrying 429s with no backoff. Identical anti-pattern, almost no shared vocabulary. That's the real shape of retrieval, and it's why the number is 83% and not 100%.

I also cut the answer key from ten clusters to seven after realising three pairs shared a *theme* but not a *root cause* — a feature flag ramped to 100% and a forward-only migration left behind by a rollback are different faults. The number had been flattering because the key was wrong. A smaller honest key beats a larger flattering one.

## The before/after, built to be unarguable

Most demos of "memory helps" compare a good prompt against a deliberately weak one. That's a strawman, and judges know it.

So the control is another Hindsight bank that is created once and **never written to**. The identical query runs against it — same model, same retrieval stack, same prompt, zero memories retained. Memory is the only variable.

```
memory on    MATCH: 100   INCIDENTS: INC-1042, INC-1188   RUNBOOK: RB-07   OPEN_ACTION: written 2x
memory off   MATCH: 0     INCIDENTS: none                 RUNBOOK: none    OPEN_ACTION: none
```

Worth noting what the memory-off run *does* get right: it correctly identifies an IAM trust-policy problem, from the error string alone. The model isn't bad. The absence of memory is what costs you the prior incidents, the runbook, the still-exposed services, and the knowledge that the fix was written down twice.

## Three things that will bite anyone building on Hindsight

**The sync Python client binds its connection pool to the first event loop that uses it.** Call it from a second thread and aiohttp raises `Timeout context manager should be used inside a task`, which is a spectacularly unhelpful error for what is actually a loop-ownership bug. Worse, `asyncio.to_thread` doesn't fix it: anyio attaches the parent (running) loop to its worker threads. Every call has to be serialised onto one dedicated thread with a private, never-running loop.

**`reflect` accepts a `response_schema` and Hindsight Cloud ignores it**, returning prose regardless. We pass one anyway; it works against other deployments. The contract that actually holds is a format spec in the prompt plus a deterministic parser, with the parser degrading to partial output rather than raising — a partial answer is still worth showing mid-incident.

**Don't trust your own evaluation set.** Half my initial recall misses were a wrong answer key, not a weak memory. I found them by reading each miss and asking whether a competent engineer would agree the pair shared a root cause. Three of them I would not.

## What I'd want next

The obvious extension is closing the loop the other way: when the agent flags an exposed service, open a ticket against the owner, then watch whether that ticket is ever closed the way the other nineteen weren't. The failure mode this whole project is about is a human process failure — a checkbox that nobody ticks. An agent that can *see* the unticked boxes is most of the way there. An agent that can nag about them is the rest.

---

The code is here: **[Faultline on GitHub](REPO_URL)**

Built with [Hindsight](https://hindsight.vectorize.io/) by Vectorize — the [source](https://github.com/vectorize-io/hindsight), the [docs](https://hindsight.vectorize.io/), and background on [what agent memory is and why it's hard](https://vectorize.io/what-is-agent-memory).

*The incident corpus is synthetic: a fictional company, fictional services, fictional people. But every failure mode in it is lifted from a real postmortem — including the one where a debug log statement filled the collector's disk and silently took out the alerting pipeline you would have used to diagnose it.*
