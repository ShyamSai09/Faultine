# User guide

How to actually use Faultline during an incident. This assumes you have it running; if not, start
with [RUNNING_IT.md](RUNNING_IT.md).

---

## The first five minutes

The console is at `http://localhost:8000/console`. If you are in a hurry:

1. Press **Triage alert**
2. Read the **match percentage**. Over 80% means it recognises this
3. Read **Prior incidents with the same root cause**. The ids and dates are the evidence
4. Read **Still exposed elsewhere**. This is the part that changes what you do next
5. Read **Remediation that was never completed**. This is the part that changes what you do after

Then flip **Memory** off and triage again, to see what you would have had without it.

---

## Reading the answer, field by field

### Match percentage

How confident the agent is that this is a failure mode it has seen before.

**Treat this as a communication device, not a measurement.** It is the model grading itself, and a
model asked for a confidence number will usually produce a high one. The number that is actually
measured is on the **Learning curve** tab: 83%, with its one miss shown.

What it is genuinely good for: if it is **low**, stop reading and treat this as a novel incident.
That is real signal, because it means the memory does not have a fingerprint for this.

### Verdict

The agent's own words, in the reading face rather than the monospace face. If it is set in mono, a
machine produced the line.

Skim it. It is a competent summary and it is not where the value is.

### Prior incidents with the same root cause

Each entry shows an id, the service, the severity, the date, the time to resolve, and the runbook.

**Look at whether the symptoms look alike.** They usually do not. In the demo, `INC-1042` was 503s
on payments and `INC-1188` was 401s at checkout, and they share only a cause. If the agent has
connected two incidents that do not look alike, that is the system working, not a false positive.

Then read the **cause** line underneath. That is the model's one-sentence statement of what the
shared thing is.

### What to do first

Numbered steps, each naming the runbook that worked before.

**Check the runbook id against the incidents above.** If step 1 cites `RB-07` and `INC-1042` also
used `RB-07`, you have a fix with a track record, not a guess. That is the most valuable sentence on
the screen.

### Still exposed elsewhere

Services carrying the same underlying fault right now, that have not failed yet. In the demo,
`inventory-sync` and `webhooks-relay`.

**This is the reason the product exists.** Nobody is paged for these. They are waiting for their
turn, and the runbook you are about to run has a documented mechanism for leaving them loaded.

Each entry cites the recorded state and the date it was last audited. If the audit date is old, the
service may have been fixed since. The agent tells you it was last checked, not that it is broken
now.

### Remediation that was never completed

To-do items for this failure mode that were written in a postmortem and never closed, with the
owner and the incident that raised it.

**The count is the signal.** A promise made once is a to-do item. A promise made three times is a
process failure, and the badge tells you which. If the count is climbing, escalating to the owner as
"we said we would do this" is a different and more productive conversation than filing another
ticket.

---

## The memory switch

Toggling it off runs the identical query against a bank that was created once and never written to.

Same model, same four-way retrieval, same directives, same query. The only difference is that one
bank has nineteen incidents in it and the other has none.

What to expect with it off: `MATCH: 0`, `INCIDENTS: none`, `RUNBOOK: none`, and no exposed services
and no unclosed actions. The model will still correctly identify the *category* of problem from the
error text, which is the honest and more interesting result. The model is not the weak link. The
missing memory is.

Useful for: calibrating how much the memory is actually contributing, and for showing someone who
does not believe you.

---

## The right-hand column

**Recalled for this alert.** The actual memories that came back. Anything labelled `observation` is
a consolidated belief formed across several documents, not a raw fact.

**Read those first.** They are the thing a search engine cannot produce. A retrieved document
already existed; a formed belief did not.

**Fingerprints.** Three mental models, as tabs.

| Tab | What it is for |
| --- | --- |
| Fingerprints | The full catalogue of failure modes: symptoms, affected services, dates, runbook, incident count |
| Recurrence risk | The bluntest statement of the problem: which services carry a known failure mode that has already caused an outage |
| Open remediation | The unclosed backlog, grouped by underlying problem, with how many times each has been promised |

If a tab is empty, Hindsight writes them in the background after consolidation. A fresh seed can
take a minute or two.

**Record resolution.** Retains the outcome and refreshes the fingerprints. Worth doing.

**Do it, then triage again.** The count on the repeated action goes up, and usually a **new** action
appears that was not there before, derived from what this incident exposed. In the demo, retaining
the resolution produced a new action: add a synthetic credential check, because the eleven-day
window where a cached token hid the fault is exactly the gap a periodic probe would have caught.

The system learning a new lesson from its own experience is the point. Do not skip this step and
then wonder why the demo is thin at the end.

---

## The other three tabs

### Learning curve

Whether the memory is any good, scored rather than asserted.

The line goes up, dips, and comes back up. **The dip is real.** A harder pair enters the denominator
when it is reached. The caption explains it, and the table below names the miss in red next to the
four that worked.

### Memory

Raw inspection, for when someone wants proof the memories are real. Search runs a live `recall`.
Try: `wildcard trust policy`, `Hikari pool`, `TTL jitter`, `what did we never finish`.

### Corpus

The dataset. Have this tab open when someone asks whether the scenario was staged to flatter the
system. It was, deliberately, and the table is the evidence. The reviewer notes in the last table
are worth reading: "Third time this action has been written. Still not done." and "Module never
updated; still the default today."

---

## Using your own data

Replace the contents of `INCIDENTS` in `app/corpus.py`. The field list, and what breaks if you skip
each one, is in [DATA.md](DATA.md).

Then update the answer key in `app/analysis.py`, or the measurement will be meaningless, and
re-seed with force:

```bash
curl -X POST "localhost:8000/api/setup?force=true"
```

**Two things that will make your data perform worse than the demo data:**

1. **Paraphrased alert text.** The verbatim string is the retrieval surface. This is the single
   biggest mistake available.
2. **Today's timestamps.** Temporal retrieval is one of four recall arms. Stamp incidents with
   their real dates or the system cannot say "this also happened in March", which is most of the
   value.

---

## What this will not do

Being clear, because a tool you trust too much is worse than no tool.

- It only knows what was retained. An outage nobody wrote down is an outage it never saw.
- It cannot tell you *why* a service is exposed, only that the record says it is and when that was
  last checked. It is reading a file, not probing your infrastructure.
- The match percentage is the model grading itself. Use it as a signal when it is low, and ignore
  it when it is high.
- It has no authentication, no multi-tenancy and no audit trail. Do not point it at real
  infrastructure.
- It gets things wrong. One pair in six is not recovered, and the miss is documented rather than
  hidden.

---

## Quick reference

| I want to | Do this |
| --- | --- |
| Triage an alert | **Triage alert**, then read match, prior incidents, exposed, unclosed |
| Know if it has seen this before | The match percentage, and the prior incidents list |
| Know what to run first | The steps, and the runbook id they cite |
| Know what else is broken | **Still exposed elsewhere** |
| Know what we promised and did not do | **Remediation that was never completed**, and the count |
| Prove the memory is doing the work | Toggle **Memory** off and triage again |
| Show the whole catalogue of failure modes | Fingerprints, on the right |
| Check the retrieval is not degrading | Learning curve tab |
| Prove the memories exist | Memory tab, then search |
| Check the data is not rigged | Corpus tab, last table, reviewer notes |
| Make the system sharper | **Record resolution**, then triage again |

Next: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
