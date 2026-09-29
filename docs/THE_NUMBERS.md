# The numbers, and where each one comes from

Everything numeric in this project, what it means, and how honestly it was produced. If you are
judging this and want to check a claim, this is the page.

---

## The headline figures

| Figure | Value | What it actually is |
| --- | --- | --- |
| Fingerprint match | 100% | The model's own confidence that this alert matches a known failure mode, asked for in the output format. A judgement, not a measurement |
| Sibling incidents recovered | 5 of 6 | A measurement. See below |
| Overall recall | 83% | 5 divided by 6, against a hand-written answer key |
| Incidents in memory | 19 | Real count of the corpus |
| Services exposed | 2 | Read from the recorded infrastructure state, not guessed |
| Times an action was promised | 2, then 4 | Counted from the corpus across incidents |
| Time to resolve a live alert | about 4 seconds | Measured, on Hindsight Cloud |

---

## The one real measurement: 83%

This is the only number in the project produced by scoring the system against a known answer
rather than by asking the system to rate itself.

### How it works

`app/analysis.py`. The process:

1. **A human wrote down which incidents share a root cause.** This is the answer key. Seven
   clusters, twelve incidents:

   | Cluster | Incidents |
   | --- | --- |
   | Wildcard identity trust policy | INC-1042, INC-1188 |
   | Connection pool exhaustion / N+1 query | INC-1099, INC-1203, INC-1224 |
   | Outbound call with no backoff or timeout | INC-1211, INC-1219 |
   | Certificate expiry and clock drift | INC-1155, INC-1140 |
   | Kafka consumer rebalance storm | INC-1231 |
   | Redis stampede from flat TTLs | INC-1130 |
   | Database bloat from autovacuum starvation | INC-1107 |

2. **For each incident, ask Hindsight to recall its failure mode.** The query is the alert line plus
   a description of the mechanism, the way an engineer would actually ask.

3. **Check which of the true siblings come back** in the top ten results. Only siblings that had
   already happened before that incident count, so the test is not trivially easy.

4. **Report the cumulative share.**

```
overall recall: 83%    5 of 6 sibling incidents recovered    5 incidents measured
```

### No model is involved

`recall` does not generate text. It ranks locally using BM25 keyword search, vector similarity, the
entity graph, temporal filters, and a small cross-encoder that runs on your machine. So the
measurement is cheap, repeatable, and not subject to the model having a good day.

### The one miss, and why it is a real miss

`INC-1219` versus `INC-1211`:

| | INC-1219 | INC-1211 |
| --- | --- | --- |
| What broke | 32 sync threads all blocked on one outbound HTTP call with no timeout | A webhook relay retried 429s with no delay and burned its whole daily quota |
| Symptom in the alert | `sync_threads_active=32 pool_max=32` | `delivery_failure_rate=0.38` |
| Words in common | almost none | almost none |

Identical underlying anti-pattern (an outbound call with no backoff and no timeout), completely
different surface. Retrieval found the pool cluster easily and the cache cluster easily, but missed
this one.

**It is shown in the interface, not hidden.** A system that reports 100% and has an answer key
tuned to produce 100% is telling you nothing.

### The answer key was wrong first, and I cut it

The first version had ten clusters. It scored 55%. Half the misses turned out to be my own
labelling errors, not the memory's failures:

| I had grouped | Why it was wrong |
| --- | --- |
| A feature flag rolled out to 100% with a forward-only migration left by a rollback | Different faults. One is a rollout control failure, one is a schema change problem |
| An out-of-memory kill in a backfill with a bad record failing a batch job | Different faults. One is unbounded memory, one is data validation |
| A silent webhook loss with a log volume outage | Different faults. One is lost data, one is lost visibility |

Cutting to seven defensible clusters took the score from 55% to 83% without improving the system
by a single line. **The number was flattering because the key was wrong.** A smaller honest key
beats a larger flattering one.

### What this number does not claim

It does not claim anything about real incident histories, anyone's actual on-call quality, or how
the system would perform on your data. It is a measurement on nineteen constructed incidents with
twelve of them labelled. That is the honest ceiling of what it can tell you.

---

## Figures that are not measurements

### "100% match"

The model is asked, in its output format, for a `MATCH` field from 0 to 100. It returns 100. It is
a self-assessment, and a model asked for a confidence number will usually produce a high one.

It is shown as a headline because it is a useful *communication* device, not because it is
rigorous. The 83% above is the number to trust. Treat them differently.

### "Two services exposed"

Not a guess. The model returns which infrastructure condition matches the alert:

```
STATE: iam_role_trust_policy
```

and the code looks up the recorded state for that key, which lists which services still carry the
condition. The list is a fact in the dataset.

This exists because the model, asked directly, listed services that had already been fixed. See
"HOW_IT_WORKS.md, step 5".

### "Written 2x" and "4x"

Counted across the corpus. The sweep action appears in the postmortems of INC-1042 (March),
INC-1188 (June), and the live incident, plus the action raised by the live resolution. Four
promises, one never done.

The badge appears only when the count is above one. A promise made once does not need a badge; a
promise made three times is a process failure, not a to-do item.

### "41 minutes", "44 minutes", "87 minutes"

Time to resolve, taken from each synthetic incident's own open and close times. Realistic, not
measured.

### Latency figures

Real, measured on Hindsight Cloud during development:

| Operation | Time |
| --- | --- |
| `retain` (one incident) | about 2.5 seconds |
| `recall` | about 0.4 seconds |
| `reflect` (the full triage) | about 4 seconds |
| `retain` x 19, first run | 2 to 4 minutes |

These are a snapshot from one region and will vary.

---

## The numbers on the landing page

Every figure shown there is one of the above, and each is labelled with where it came from. There
are no invented statistics anywhere in this project, which is why there is no "10,000 teams" or
"99.99% uptime" claim. There is nothing to point at.

Specifically absent, and why:

| Not shown | Reason |
| --- | --- |
| User or team counts | There are no users |
| Uptime or performance claims | Nothing has been load tested |
| Compliance badges | Nothing has been audited |
| Testimonials | Nobody has used it but me |
| Comparison charts against named tools | I have not benchmarked against them |

Next: [DATA.md](DATA.md)
