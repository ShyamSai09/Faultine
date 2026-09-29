# Every screen, and what to look at

Two pages: the landing page and the console. This walks through both.

---

# The landing page

At `http://localhost:8000/`, the root. Its only job is to explain the thing in about ninety seconds of
reading and get you to the console.

It is built around four pieces of evidence rather than adjectives, in this order:

1. **The alert.** The actual production alert, verbatim, in a block styled like a clipping cut from
   a postmortem. It is the real string the agent matches against.
2. **The same alert with memory on, then with memory off.** The two outputs side by side. This is
   the argument, and the two runs go through the identical system with memory as the only
   difference, so the comparison is not rigged.
3. **The real screenshots.** Captured from the running console, not mocked up.
4. **The measurement.** 83%, with the one miss named.

Everything numeric on that page is measured on the corpus and labelled. There is no user count, no
uptime claim, no testimonial, because there is nothing to point at.

Two buttons, and both do something real: open the console, or open it with the demo already
running (`?autotriage=1`, which presses the triage button for you on load).

---

# The console

At `http://localhost:8000/console`. Four tabs, with a back link to the landing page in the masthead.

---

## Tab one: Console

The live view. Three columns on a wide screen, stacked on a narrow one.

### Left column: the alert

**Incoming alert.** The SEV2 that fires at 09:14 on 28 September. Shown the way it arrives, as a
clipped block of raw alert text, not summarised. The point of showing it verbatim is that this exact
text is what the agent matches against. Paraphrasing it would misrepresent the task.

**Raw evidence.** Three log lines from the failing service, again verbatim.

**The italic note underneath.** A hint planted in the data: no deploy in 30 days, no successful
credential use in 11 days. That gap is the clue that this is not new. A good demo does not hand the
answer over immediately, and this line is what the on-call engineer is meant to notice first.

**Memory switch.** On or off. Off runs the identical query against a bank that has never been
written to. This is the control group, and it is the single most convincing thing in the project.

**Triage alert button.** Press it. First run takes about four seconds.

### Middle column: the answer

**Before you press it:** a dashed empty state saying an alert is waiting. Not an error, not a
spinner. A designed empty state.

**While it runs:** the button shows a spinner and the label changes to say what is happening.

**On success**, five blocks appear in order of importance.

**1. The match percentage.** A large number in a ring. How confident the agent is that this is a
failure mode it has seen. Read this as a communication device, not a measurement, and see
[THE_NUMBERS.md](THE_NUMBERS.md) for the 83% that is a real one.

**2. The verdict, in prose.** One or two sentences, set in the reading face rather than the
monospace face. That typographic split is deliberate: if it is set in mono, a machine wrote it, and
the verdict is the agent's own words.

**3. Prior incidents with the same root cause.** Each one shows its id, title, service, severity and
date, pulled from the corpus so the detail is exact rather than generated. In the demo these are
INC-1042 (March, `payments-api`) and INC-1188 (June, `checkout-web`). Then the cause, summarised,
under a distinct marker.

**What to look for:** these two incidents look nothing alike at a glance. One was 503s on payments.
One was 401s at checkout. They share only a cause.

**4. What to do first.** Two or three numbered steps, each naming the runbook that worked before.
In the demo both cite RB-07.

**5. Still exposed elsewhere.** The most important block on the page, and the reason the project
exists. It lists services that carry the same broken configuration right now and have not failed
yet. In the demo, `inventory-sync` and `webhooks-relay`.

**6. Remediation that was never completed.** The to-do items for this failure mode that were written
down and never closed, each with its owner, the incident that raised it, and a count when that
count is above one. The demo shows the wildcard trust sweep, promised **2 times**.

**Below the answer:** if you have already run the no-memory comparison, its output appears here too,
so the two can be read in one place.

**On failure:** a red bordered panel with the actual error text. Not a toast that disappears.

### Right column: the memory

**Two counters.** How many memories were recalled, and how many mental models were available.

**Recalled for this alert.** The actual memories `recall` returned, with their type and relevance
score. Anything labelled `observation` is a consolidated belief, not a raw fact. Read those first,
because they are the thing a search engine cannot produce.

**Fingerprints.** The three mental models, as tabs. Read them as an appendix. The
`recurrence-risk` one is the bluntest statement of the whole problem:

> The following services have been identified as carrying known failure modes that have previously
> resulted in production outages. These conditions remain in place due to uncompleted remediation
> work from past incidents.

**Record resolution.** Disabled until you have triaged once, then live. Pressing it retains the
incident outcome and asks Hindsight to rewrite the fingerprints.

This is the loop closing, and it is worth doing live in a demo. Press it, then triage again, and the
count on the Terraform action goes from 3 to **4**, and a new action appears: add a synthetic
credential check, derived from the eleven-day window where a cached token hid the fault. The system
learned a new lesson from its own experience.

### The demo shortcut

`http://localhost:8000/console?autotriage=1` presses the button for you. Useful when presenting on a
projector where you do not want to be hunting for a control.

---

## Tab two: Learning curve

The answer to "how do you know it is actually learning?".

**The method, stated at the top.** Every incident sits in a hand-labelled cluster of failures that
share a root cause. For each one, Hindsight is asked to recall the failure mode, and we check which
of its true siblings come back. Only `recall`, so no model generation and no cost.

**Four numbers across the top.** The recovery rate, the raw count, how many incidents were measured,
how many clusters exist.

**The chart.** Cumulative recovery in the order the incidents happened.

**Read the line honestly.** It goes up, dips, and comes back up. The dip is real: a harder pair
enters the denominator when it is reached. The note underneath the chart explains this in full,
including naming the miss. A curve that only went up would be a sign the key had been tuned to the
system rather than the other way round.

**The table.** Every incident measured, what it was expected to find, what it actually found, and
the percentage. The miss is in the table in red, next to the four that worked.

**Also on this tab:** a note recording that the answer key was cut from ten clusters to seven
because three pairs shared a theme but not a root cause. The score went from 55% to 83% without
changing the system. That is worth admitting.

---

## Tab three: Memory

For when someone wants to see that the memories are real rather than rendered.

**Search** runs a live `recall` against the bank and shows what comes back, with types and scores.
Try: `wildcard trust policy`, `Hikari pool`, `TTL jitter`, `what did we never finish`.

**Browse** lists stored memories directly.

Above the controls, the two banks and why they are separate.

---

## Tab four: Corpus

The raw data, so nothing is hidden.

**Four counts** across the top: services, incidents, actions never completed, latent conditions.

**The incident table.** All nineteen, with id, service, severity, date, title, time to resolve, and
runbook. The time-to-resolve column is where you can see the expensive ones: 87 minutes for the
migration rollback, 76 for the webhook quota burn.

**The unclosed actions table.** All nineteen, with the incident that raised each, the owner, and
the reviewer note. Read the notes column. "Third time this action has been written. Still not done."
is in there, and so is "Module never updated; still the default today".

This tab is the answer to "where did this data come from", and it is the tab to have open when
someone asks whether the scenario was staged to flatter the system. It was, deliberately, and the
table is the evidence.

---

# States you might see

| State | What it looks like |
| --- | --- |
| Connecting | Full-page progress. First run shows which stage it is at, with a count like `12/19` |
| Seeding failed | The stage name, the error, and a red panel. Usually a bad key or no credit |
| Nothing triaged yet | A dashed empty box saying an alert is waiting |
| Triaging | Spinner in the button, label changes to name the current step |
| Triaged, memory off | The baseline output, and a note that memory was not consulted |
| Triage failed | A red panel with the real error, not a disappearing toast |
| Mental models empty | Says so, and explains they are written in the background after consolidation |
| Learning curve not yet computed | Says no measurement yet, and to seed the memory first |

Next: [API.md](API.md)
