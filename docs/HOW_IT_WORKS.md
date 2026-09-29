# How it actually works

This walks through the whole path, from an alert appearing to an answer being written. Every step
says which Hindsight feature does the work and why that feature and not another.

---

## The shape of the system

```
   alert arrives
        |
        v
   [ recall ]   pull relevant memories out of the bank
        |
        v
   [ reflect ]  the model reasons over those memories
        |
        v
   [ read ]     mental models, which cost nothing to read
        |
        v
   [ ground ]   code overrides anything the model got wrong
        |
        v
   answer on screen
```

Five steps. Four of them are Hindsight. The fifth exists because step three was occasionally wrong.

---

## Step 0: what is in memory, before anything happens

Two memory stores, called **banks** in Hindsight. They are fully separate, with no way for content
in one to leak into the other. That separation is not tidiness, it is load-bearing, and
[HOW_IT_WORKS.md](#step-4-the-join-that-makes-this-work) explains why.

| Bank | What goes in |
| --- | --- |
| `faultline-incidents` | 19 full incident records, plus 4 records describing the current state of shared infrastructure settings |
| `faultline-team` | The 19 postmortem to-do items that were never completed, each with an owner and a date |

There is a third bank, `faultline-control-empty`, which is created once and never written to. It
exists purely so the "what if there were no memory" comparison can be run fairly. More on that in
[the before and after](#the-before-and-after).

Each incident record looks like a real postmortem, not a summary of one:

```
INCIDENT INC-1042 - Card authorisation returning 503 for 41 minutes
Service: payments-api  Severity: SEV1  Status: resolved
Opened: 2026-03-14T09:12:00Z  Resolved: 2026-03-14T09:53:00Z
Time to resolve: 41 minutes
Detected by: Datadog monitor: payments.auth.error_rate > 2% for 5m

ALERT AS IT FIRED:
[HIGH] payments-api auth_error_rate=0.37 over 5m window
  error: AccessDenied - User: arn:aws:sts::9182:assumed-role/... is not
  authorized to perform: sts:AssumeRole

TIMELINE:
  09:12  Datadog pages Core Money on-call. Ack within 3m.
  09:27  Escalated to Platform after no obvious application rollback.
  09:41  Applied runbook RB-07.

LOG EXCERPT:
  2026-03-14T09:12:04.221Z ERROR [payments-api] StsClient - assumeRole failed ...

ROOT CAUSE: An automated IAM credential rotation replaced the assumed role...
RUNBOOK USED: RB-07

POSTMORTEM ACTION ITEMS:
  [NEVER COMPLETED] Sweep every service for the wildcard trust policy (owner: Jonas Weber)
  [COMPLETED]         Add a synthetic check every 10 minutes (owner: Rahul Menon)
```

**Why keep the whole thing instead of a tidy summary?** Because the useful signals are the
specific strings. "Runbook RB-07" and "sts:AssumeRole" are rare, and they are what lets the system
connect this record to another one later.

**Why pass the original incident date rather than today's date?** Because Hindsight can filter and
rank by time. If everything is stamped "written today", the system can no longer say "this also
happened in March", which is the entire value of the exercise.

## Step 1: recall, which is four searches at once

When an alert arrives, Faultline calls `recall` with the alert text plus the question.

Hindsight does not do one search. It runs four in parallel and merges the results:

| Search | Finds things by | Needed for this alert because |
| --- | --- | --- |
| Semantic | meaning | "AccessDenied on role assumption" is close in meaning to the March incident's error |
| Keyword (BM25) | exact words | `sts:AssumeRole` and `RB-07` are rare and exact. Meaning alone is fuzzy here |
| Graph | connected entities | links `payout-worker` to the role, to the trust policy, to the Terraform module, to the two unpatched services |
| Temporal | dates | lets it say "March and June", turning two coincidences into a pattern |

Then it merges the four ranked lists, applies a cross-encoder to re-rank, and returns the top few
within a token budget.

The graph arm is the one people underestimate. It is why the system can go from an alert on
`payout-worker` to `inventory-sync`, a service that has never appeared in the same document.

## Step 2: reflect, which is the model reasoning over the memories

`reflect` is Hindsight's agentic read. Where `recall` returns memories, `reflect` runs a loop: the
model asks for more memory, searches again, expands what it found, and only then writes an answer.

Four **directives** shape how it reasons. Directives are hard instructions attached to the bank:

| Directive | What it says | Why |
| --- | --- | --- |
| `no-invention` | If the memory does not contain it, say so. Never guess | A confidently wrong root cause costs hours during an outage. An honest "I do not know" is cheaper |
| `cite-evidence` | Every claim needs an incident id and a date | Makes the answer checkable |
| `prefer-recent` | When two memories disagree, the newer one is right | Facts change. A service fixed in June is not still broken in September |
| `surface-unclosed-work` | If this failure mode has a remediation that was never completed, say so and name the owner | This is the sentence the whole product exists to produce |

The last one is the reason the directives exist. Without it the model gives a competent technical
answer and stops. With it, it tells you the fix was promised twice and never done.

## Step 3: reading the mental models

Hindsight also keeps three **mental models**: standing answers to standing questions, rewritten in
the background as evidence accumulates.

| Model | The question it answers |
| --- | --- |
| `failure-fingerprints` | What failure modes does this organisation have, what do they look like, which services, which runbook, how many times each |
| `recurrence-risk` | Which services are currently carrying a failure mode that has already caused an outage somewhere else |
| `open-remediation` | Which actions were never completed, grouped by underlying problem, and how many times each has now been promised |

The important property is cost: **reading a mental model is a database read, not a model
generation.** That is why Faultline can consult one on every single alert. If reading it required a
model call, it would be too slow to use interactively and would cost money on every page load.

You can watch one being rewritten by opening the console and clicking "Fingerprints".

## Step 4: the join that makes this work

Here is the specific trick, and it is the reason for the two-bank split. The recurrence check works
like this:

1. The alert arrives. Recall finds memories about the identity trust problem.
2. The model identifies the failure mode and reports it as a state key, such as
   `iam_role_trust_policy`.
3. Code looks up the recorded infrastructure state for that key. That record says which services
   are still carrying the condition and which were fixed.
4. Separately, the **team** bank is asked which actions about this failure mode were never
   completed, and how many incidents raised each one.

Step 4 is a link between an incident in one bank and a to-do item in another. Nothing about that
is similarity. It is a traversal, and it is why the "written 2x" badge appears.

The one you should remember: **the same failure mode, described in three incidents across five
months and three different services, connected into one belief.**

## Step 5: grounding, the step where I stopped trusting the model

This is the most useful thing I learned building it, so it gets its own section.

The first version asked the model to list the services still exposed to the failure. It reliably
listed services that appeared in the incidents it had just cited, including two that engineers had
already fixed by hand.

The model's reasoning was not stupid. It noted that all those services are built from the same
Terraform module, which still has the unsafe default, so all of them are technically at risk. That
is a defensible argument. It is also the wrong answer, and telling an on-call engineer to go check
a service that was patched six weeks ago costs real minutes while customers are affected.

So the code stopped asking. The model now reports only *which* condition matches:

```
STATE: iam_role_trust_policy
```

and the code builds the list of affected services from the recorded state, using the model's prose
only as the explanation underneath.

**Let the model do the judgement and the code do the bookkeeping.**

## The before and after, built to be fair

Most demos of "memory helps" compare a good prompt to a deliberately bad one. That is a strawman.

Here, the comparison runs the **identical query** through Hindsight against a bank that was
created once and never written to. Same model, same four-search retrieval, same directives, same
prompt. The only difference is that one bank has nineteen incidents in it and the other has none.

```
memory on    MATCH: 100   INCIDENTS: INC-1042, INC-1188   RUNBOOK: RB-07   OPEN_ACTION: written 2x
memory off   MATCH: 0     INCIDENTS: none                 RUNBOOK: none    OPEN_ACTION: none
```

Worth noticing what the memory-off run still gets right: it correctly identifies an identity
permission problem, purely from the error text. The model is not the weak link. Missing memory is.

That is a more interesting result than "the model was useless without memory", and it is the honest
one.

## Closing the loop

When the operator records the resolution, Faultline retains the new incident and refreshes the
mental models. After doing so, the same alert run again reports the Terraform action as promised
**four** times instead of three, and a brand new action appears: add a synthetic check, because the
eleven-day window where a cached credential masked the fault is exactly the gap a periodic probe
would have closed.

The system got a new lesson from its own experience. That is the whole thesis.

Next: [FOLDER_MAP.md](FOLDER_MAP.md)
