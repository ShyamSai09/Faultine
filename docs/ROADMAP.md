# Roadmap

Honest about what this is, what it is not, and what would have to happen to make it a real tool.
Ordered by how much it would change the product, not by how easy it is.

---

## Where it actually is

A working system with a measured claim, built in a day against a deadline. The claim is narrow and
the evidence supports it:

- Given an alert, it identifies the failure mode, cites the prior incidents sharing the cause,
  names the runbook, flags services still carrying the fault, and reports the remediation that was
  promised and never done. **Verified working end to end.**
- Retrieval recovers 5 of 6 correctly related incidents against a hand-written key. **Measured, with
  the miss documented.**
- The no-memory comparison is a control bank, so the difference is attributable to memory. **By
  construction, not by assertion.**

What is not true yet:

- It does not touch real infrastructure. The exposed-services list is a file read.
- It is unauthenticated and single-tenant.
- It is untested.
- The numbers are on a constructed corpus, and that bounds what they can mean.

---

## Next, in the order I would do it

### 1. A test suite

**The largest gap in the project, and the one I am least comfortable shipping without.** See
[DECISIONS.md D12](DECISIONS.md).

Three functions first, because they carry the risk:

| Function | Why it needs a test |
| --- | --- |
| `_parse_triage` | The prompt contract and the parser are coupled with **nothing** tying them together. Change the format without the parser and it fails silently, which is the worst failure mode in a codebase |
| `_exposure_from_corpus` | The correctness guard for the grounding step. If it regresses, the agent starts telling on-call to chase patched services and nobody notices for weeks |
| `analysis.measure` | The reported number depends on it. A silent change would move a published figure |

Then corpus invariants: unique incident ids, valid service references, well-formed timestamps. Two
syntax-level bugs during the build would have been caught by those alone.

### 2. Real infrastructure integration

**This is the difference between a demonstration and a product.**

Today the exposed-services list is read from a static record in `app/corpus.py`. The honest version
queries the thing itself: Terraform state, Kubernetes config, whatever actually holds the setting.
Then the list is a fact about the world rather than a fact about a file, and the system stops being
told what is broken and starts finding out.

This is the single change that would make the claim on the landing page true in a real environment.
It is also the change that would most change the shape of the project, which is why it is not a
weekend job.

### 3. Ingest incidents from somewhere real

Right now the corpus is a Python literal. Useful and honest, but it means the only way to add history
is to edit code.

Worth having, in order of value:

- A PagerDuty or incident.io export, so postmortems land without a deploy
- A Slack or email thread, because the useful context is often in the channel and never in the
  postmortem
- A Jira or Linear view of action items, so the "promised Nx" count comes from the tracker rather
  than from a postmortem nobody opened

The third is the most valuable per unit of effort, because the count is the most persuasive number
on the screen and it is currently computed from static data.

### 4. Close the loop, not just measure it

Faultline knows an action has been promised four times. It does not do anything about it.

The obvious extension: when an exposed service is flagged, open a ticket against the owner, then
watch whether it gets closed the way the other nineteen were not. The failure this whole project is
about is a human process failure, a checkbox nobody ticks. An agent that can *see* unticked boxes is
most of the way there. One that can nag about them is the rest.

### 5. Incident ingestion from the other direction

Every alert currently arrives pre-selected. The live demo alert is a fixed record.

Worth having: a webhook that takes a real Prometheus or Datadog payload, so the system sees the
shape of alerts nobody chose. That will surface failure modes the hand-written corpus never
anticipated, which is a genuine test of whether the fingerprinting generalises.

### 6. Knowledge pages for the institutional memory

Hindsight supports knowledge pages: living documents a bank writes about itself, projectable onto
disk as ordinary markdown. Faultline does not use them.

For a team that wants to *read* their own institutional memory rather than query it, this is the
feature. `/docs/Architecture.md` would become something the bank maintains.

### 7. The 500-token query limit

Not a feature, a ceiling. The alert plus the output contract sits at about 450 of 500 tokens. A
longer alert or a richer contract hits the wall.

The likely fix is moving the format contract into `reflect`'s `context` parameter, which may not
share the limit. **Untested.** Worth ten minutes with a long alert to find out.

---

## Would not do

Stated so the omissions read as decisions rather than oversights.

| Not doing | Why |
| --- | --- |
| A plugin system | One integration exists. A plugin API for it is architecture for a customer who does not exist |
| Multi-tenancy | One user. It would be a permissions system in search of a threat model |
| Streaming triage | `reflect` is one call. Streaming complicates the output contract for no user-visible gain |
| Caching answers | Would undermine the before-and-after comparison, which is the project's central evidence |
| A job queue for seeding | Seeding is a startup task. A queue for it is unjustified |
| Social sentiment, anomaly detection | Genuinely useful, genuinely orthogonal. It would be a different product |
| Editing cluster state automatically | Tempting, and exactly how you get a tool that quietly changes production to match its own belief. A recommendation plus a human decision is the right shape |
| Fine-tuning on incidents | The memory system is the right layer. A fine-tune would bake in a snapshot and lose the ability to be corrected by new evidence |

---

## Known issues

| Issue | Impact | Status |
| --- | --- | --- |
| No tests | Silent regressions in the parser and the grounding step | Open, top of the list |
| Exposed list is a file read | The central claim is bounded by this | Open, needs real integration |
| All memory calls serialised | Concurrent triages queue at about 4s each | By design, see [DECISIONS.md D4](DECISIONS.md) |
| Cold seed 2 to 4 min | 24 retains run serially; `retain_batch` would fix it | Open, easy |
| Answer key hand-maintained | The weakest link in the measurement | Open, and circular to automate |
| Output contract and parser uncoupled | A contract change fails silently | Open, highest risk per line |
| 500-token query ceiling | Limits contract richness | Open, fix likely known |
| `_LoopThread` depends on client internals | Dead weight if upstream fixes it | Harmless, isolated |
| `response_schema` ignored on Cloud | Forced the prompt contract | Documented, worth re-testing |
| No auth, no multi-tenancy | Not deployable to a shared environment | Out of scope by decision |
| Markdown stripped from mental models in the UI | Headings become plain lines | Cosmetic, deliberate: it is a terminal, not a document viewer |

---

## If I had another week

In order:

1. Tests for `_parse_triage`, `_exposure_from_corpus` and `analysis.measure`, plus corpus invariants
2. A read-only Terraform state query behind a feature flag, so the exposed list is real
3. Postmortem ingestion from a PagerDuty export
4. The ticket-opening loop for unclosed actions
5. A second, structurally different failure mode in the demo, so the corpus is not a single thread
   that could be overfitted

Number 5 is the one I would worry about. Nineteen incidents, but the headline capability is
demonstrated on one causal thread. A second thread with a different shape, where the
cross-service join is harder, would test whether the fingerprinting is real or whether the dataset
was built to fit the answer.

---

## The honest summary

This is a demonstration with a measured claim and a documented gap, built in a day.

The gap is specific and nameable: **Faultline reads what is exposed rather than discovering it.**
Every other part, the cross-bank join, the consolidation, the mental models, the control-group
comparison, the grounded exposure list, is working and verified.

Close that one gap and it is a tool. Until then it is a very well evidenced argument for a tool,
which is still worth having.
