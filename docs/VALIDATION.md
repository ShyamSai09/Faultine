# Validation: what is measured, what is not, and what failed

Written because "is this just hardcoded data?" is the first question a judge asks, and
answering it badly loses the round. This page is the honest answer, including the parts
that did not work.

Run it yourself: `.venv/bin/python scripts/validate.py --holdout 5 --seed 7`

---

## The short answer to "is it hardcoded?"

**The corpus is a Python literal. The agent is not.**

`app/corpus.py` is nineteen hand-written incident records. That is a true statement and it is
stated on the landing page under "what this is not".

What is also true, and is the thing worth showing:

1. **The agent does not know the corpus is fixed.** It gets one alert and searches memory. There
   is no branch anywhere in `app/memory.py` that says "if this is the demo alert, return this
   answer".
2. **You can paste any alert into the console** and it runs the identical pipeline. There is a
   button for it. A judge can type an alert from their own company into it.
3. **It gets things wrong on data it has seen**, which a rigged demo would not.

Point 3 is the strongest one, and it is the reason the next two sections exist.

---

## What you can prove in front of a judge, live, in 30 seconds

Open the console, click **Triage a different alert instead**, and paste an alert nobody prepared.
For example, a Postgres deadlock the memory has never seen:

```
service: checkout-web
[CRITICAL] checkout-web checkout_error_rate=0.38 over 5m window
  env: production  region: eu-west-1
  error: Postgres ERROR: deadlock detected on ledger_entries
  waits: 214  deadlocks: 37 in 5m
  autovacuum: last run 15 days ago
```

The agent comes back with `state_key: none`, no exposed services, and cites **INC-1107**, the
autovacuum starvation incident in the corpus. Two things a judge can check immediately:

- **It found a genuinely related incident from an alert nobody wrote for the demo.**
- **It refused to invent exposure.** There is no deadlock condition in the recorded state, so the
  exposed list is empty. A system that always produces a confident list would have invented two
  services here. This one returns nothing, and that is the correct behaviour.

If the judge pastes something genuinely alien, the correct answer is "I have not seen this". That
is also a good outcome, and it is what the `no-invention` directive is for.

---

## What the holdout validator does, and what it found

`scripts/validate.py` runs a real holdout experiment:

1. Withhold N incidents.
2. Seed a **separate** bank from the remaining incidents only.
3. Hand the agent nothing but each withheld incident's alert text, exactly as a new alert arrives.
4. Score whether it names an incident sharing the real root cause.

The demo banks are never touched, and the training bank is deleted afterwards.

### What it found, and it is not a clean pass

Running with 5 incidents withheld:

| Withheld | Expected | Cited | Verdict |
| --- | --- | --- | --- |
| INC-1099 | INC-1203 | INC-1099, INC-1224 | miss |
| INC-1224 | INC-1203 | INC-1099, INC-1203, INC-1224 | hit |

**0 of 2 by the strict scoring.** Reported as measured, not as 100%.

### Why the test is inconclusive rather than simply failing

Three separate reasons, and they are worth understanding because two of them are interesting:

**1. Withholding an incident does not hide it.** A retained postmortem can name an earlier incident
in its root cause. `INC-1203` says *"Identical pool exhaustion to INC-1099"*. Withhold `INC-1099`
and its id is still in memory, embedded in another record, and the agent can follow that link. So
the agent citing `INC-1099` is partly the system **working**: it traversed a real cross-reference.

This means the holdout test is a floor on what recall can do, not a clean measurement of an unseen
incident. On a 19-record corpus with incidents that reference each other in prose, the two are not
separable.

**2. The corpus is too small for the test to mean much.** Two scoreable incidents is a sample of
two. Even a real 100% on two items is not evidence of anything.

**3. The model identifies the failure mode correctly in words and is unreliable on incident ids.**
Every answer in the run named the right failure mode, connection pool exhaustion. The unreliable
part is citing a specific `INC-` number. That distinction is the finding, and the strict scoring
does not capture it because it only grades the id.

### The bug this found, and the fix

The first version of the validator reported 5 of 5, or 100%. That was wrong twice over:

- It listed the withheld incident as its own expected answer, so the model citing an id that was
  never retained scored as a success.
- It did not distinguish a fabricated id from one legitimately reached through a cross-reference.

Both were scoring bugs, and both would have made the number flattering. The same first run also
showed the model citing `INC-1099` and `INC-1224` in a bank that had never seen them, which turned
out to be the cross-reference case above.

**The fix that did hold** is in `app/memory.py`: `_filter_cited_ids` checks every cited incident id
against the text `recall` actually returned, drops any that is not there, records them in
`dropped_ids`, and halves the stated confidence when it drops any. A confidence figure that rests
partly on invention is not a confidence figure.

Verified: given a cited list of `["INC-1107", "INC-9999"]` and a memory set mentioning only
`INC-1107`, the guard keeps one and drops the other.

That guard is the honest answer to "what happens when the model makes something up": the directive
reduces it, the code check catches it, and the UI shows the reduced confidence rather than hiding
the problem.

### What would make this test actually good

- A corpus of 200 or more incidents, so withholding one removes it cleanly.
- Incident records written **without** naming earlier incident ids, so a withheld incident is
  genuinely invisible. That makes the test valid and the number meaningful.
- Scoring the failure mode and the id citation separately, since they are separately reliable.

The third is cheap and should be done before submission. The first two are not.

---

## The measurements that do hold

| Claim | How it was produced | Honest scope |
| --- | --- | --- |
| 83% related-incident recovery (5 of 6) | `recall` scored against a hand-written key of 7 clusters | Measured on 19 constructed incidents, 12 labelled. The one miss is shown in the UI |
| 100% versus 0% on the memory toggle | Identical query against a never-written bank | A comparison, not a performance claim. The no-memory run still gets the failure mode category right from the error text |
| Triage latency about 4 seconds | Timed on Hindsight Cloud | One region, one provider, warm cache |
| No fabricated incident ids in the demo | `_filter_cited_ids` plus a verified test | Holds for the shipped bank. The holdout run shows the underlying behaviour is not perfect |

---

## What a judge should be told, in order

1. **"Is it hardcoded?"** The data is invented. The agent is not. Here, paste it an alert nobody
   prepared.
2. **"How do you know memory is doing the work?"** Turn memory off. Same model, same query, empty
   bank. Watch it lose the prior incidents, the runbook, and the unclosed remediation.
3. **"How do you know you did not tune the test?"** The answer key was cut from 10 clusters to 7,
   which moved the score from 55% to 83% by making the test harder. The one remaining miss is on
   screen in red.
4. **"What happens when the model is wrong?"** It was. It named two already-patched services as
   exposed, so the code stopped asking and reads the record instead. It invented an incident id
   during holdout testing, so ids are now checked against what recall returned and the confidence
   is halved when one is dropped.

Point 4 is the strongest thing in this file. Every team has a "we handled errors gracefully" line.
Having the actual bug, the actual consequence, and the actual fix is worth more.
