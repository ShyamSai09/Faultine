# Contributing

One day, one author, so these are conventions rather than a process. They exist so a second person
can change something without breaking the two rules that matter most.

---

## Before you start

Read these two, in this order. They contain the knowledge that took the longest to acquire:

1. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), for the shape of the system
2. [docs/DECISIONS.md](docs/DECISIONS.md), for why each non-obvious choice was made and what it
   would have cost to do otherwise

Then run the smoke test before you change anything:

```bash
.venv/bin/python scripts/smoke_test.py
```

If it fails, the problem is credentials, credit or provider capacity. Nothing in this codebase can
help, and every confusing bug I hit in this project was really this.

## The two rules

**1. Route every memory access through `memory.call` or `run_blocking`.**

Hindsight's client binds its connection pool to the first event loop that uses it, and
`asyncio.to_thread` makes the failure worse rather than better. The full explanation is at the top
of [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md). In short:

```python
# async route
result = await memory.call(engine.thing)
# background thread
report = run_blocking(engine.seed, progress)
# never
result = engine.client.recall(...)   # from a new thread or from async code
```

**2. If you change the output contract, change the parser in the same commit.**

`TRIAGE_FORMAT` and `_parse_triage` are one contract split across two functions with nothing tying
them together. Change one without the other and it fails **silently**: the UI renders a partial
answer and nobody notices. This is the highest-risk property in the codebase and there is no test
for it yet.

## Where things belong

| Layer | May import | May not |
| --- | --- | --- |
| `web/` | nothing | Anything from `app/`. It knows JSON shapes and nothing else |
| `app/main.py` | `app.memory`, `app.analysis`, `app.config`, `app.corpus` | `hindsight_client` directly |
| `app/memory.py` | `app.corpus`, `app.config` | FastAPI, anything web |
| `app/analysis.py` | `app.corpus`, `app.config` | `app.memory` internals |
| `app/corpus.py` | nothing | Anything |

Business logic in `web/app.js` means something is wrong. A comment that would still be true after
you delete the line it sits on should be deleted.

## Style

- **Comments explain why, not what.** The valuable ones here record a decision and its alternative.
  Everything else is noise.
- **No em dashes in interface text.** Zero permitted; check with grep.
- **No new colour tokens without a reason** added to `DESIGN.md`. The palette is 2 neutrals and 1
  accent, and it is not drifting.
- **Contrast is measured, not eyeballed.** If you touch a colour, recompute the ratios. Currently
  15 pairings pass, worst case 5.38:1.
- **No fabricated data.** No invented statistics, testimonials, or user counts. Every figure on the
  landing page is measured on this corpus, and the measurement's one miss is shown in the UI rather
  than hidden. If you add a number, say where it came from.

## Adding data

Append to `INCIDENTS` in `app/corpus.py`. The required fields, and what breaks if you skip each one,
are in [docs/DATA.md](docs/DATA.md). Two mistakes that will quietly degrade the demo:

- **Paraphrasing `alert_text`.** The verbatim string is the retrieval surface.
- **Using today's timestamp instead of the incident's real `opened` time.** Temporal retrieval is
  one of four recall arms and becomes useless if everything is stamped at ingestion.

Then update `CLUSTERS` and `CLUSTER_QUERY` in `app/analysis.py` and re-seed with force:

```bash
curl -X POST "localhost:8000/api/setup?force=true"
```

## Verifying

| Check | Command |
| --- | --- |
| Memory layer | `.venv/bin/python scripts/smoke_test.py` |
| Everything | Open `/console?autotriage=1` |
| Retrieval quality | `curl -s localhost:8000/api/learning-curve` |
| Grounding still works | Read `recurrence_risk` in a triage response |
| No horizontal overflow | Load `/console` in a 390px viewport, check `document.documentElement.scrollWidth` |
| No em dashes in the UI | `grep -o '—' web/*.html web/*.js \| wc -l` |
| No slop techniques crept back | `grep -cE 'linear-gradient\|backdrop-filter\|box-shadow' web/*.css` |

**On testing screenshots:** headless Chrome enforces a minimum window width, so
`--window-size=390,...` produces a crop of a wider render, not a 390px layout. I reported a mobile
failure that was entirely this artifact. Load the page in an iframe of the target width and measure
element bounding boxes instead.

## Commit messages

Describe the reason, not the diff. The convention in this repository:

```
<what changed, in one line>

<why, and what the alternative was. Include a measurement where one exists.>
```

The second paragraph is the part that matters in six months. Several messages here record that a
number moved because the *measurement* got stricter rather than because the system got better, and
that is not visible from the diff.

## Pull requests

There is no template and no review process. If you want one proposed, that is a reasonable PR.

The two things worth asking a reviewer about: whether the change breaks either of the two rules
above, and whether it adds a number without a source.
