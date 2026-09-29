# Developer guide

For anyone changing this codebase. If you are trying to *use* it, read
[USER_GUIDE.md](USER_GUIDE.md) instead. If you are evaluating the design, read
[ARCHITECTURE.md](ARCHITECTURE.md).

---

## The one thing to know before you touch anything

Hindsight's Python client is synchronous, and its underlying aiohttp connection pool is bound to
the event loop that first used it. Call it from a second thread and aiohttp raises:

```
RuntimeError: Timeout context manager should be used inside a task
```

That message has nothing to do with timeouts. It is a loop-ownership bug wearing a disguise.

**`asyncio.to_thread` makes it worse, not better**, because anyio attaches the parent (running)
loop to its worker threads.

The fix is `run_blocking` in `app/memory.py`: a queue, one dedicated worker thread, and a private
event loop on it that is never `run_forever`. Every memory call is serialised onto that thread, so
`get_event_loop()` always returns the same loop and the pool is only ever used from it.

```python
# In an async route. Correct.
result = await memory.call(engine.triage, corpus.LIVE_ALERT, True)

# In a background thread. Also correct.
report = run_blocking(engine.seed, progress)

# Never. Breaks, or breaks confusingly.
result = engine.triage(corpus.LIVE_ALERT, True)     # from async code
result = engine.client.recall(...)                   # from a new thread
```

If you add a route that touches memory, route it through `memory.call`. If you add a background
job, route it through `run_blocking`. There is no third option.

---

## Module map

| File | Lines | Responsibility | Must not |
| --- | --- | --- | --- |
| `app/corpus.py` | 1134 | The dataset. Ten services, nineteen incidents, latent state, the live alert | Contain any logic. It is data plus two functions over it |
| `app/memory.py` | 985 | The only module that talks to Hindsight | Know anything about HTTP or the DOM |
| `app/main.py` | 387 | Routing, input validation, JSON | Reason, retrieve, or decide anything |
| `app/analysis.py` | 180 | Scoring recall against the hand-written answer key | Be needed for the app to run |
| `app/config.py` | 51 | Settings, and loading `.env` before the client imports | Contain feature flags |
| `web/app.js` | 557 | Fetching, rendering, tabs, states | Know why an answer looks the way it does |
| `web/index.html` | 279 | Console structure | Contain a click handler |
| `web/base.css` | 331 | Tokens and primitives | Contain layout |
| `web/console.css` | 346 | Console layout and breakpoints | Redefine a token |

The dividing line is strict: `app/` never touches the screen, `web/` never makes a decision. If
business logic appears in `web/app.js`, something has gone wrong.

---

## Setup for development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # then add your key
./run.sh --reload
```

`--reload` restarts on file changes. Note that reloading restarts the process, so the in-process
`seeded` flag resets. That is fine, because seeding is idempotent: the banks live in Hindsight and
`is_seeded()` detects them.

### Verifying your environment before you debug anything else

```bash
.venv/bin/python scripts/smoke_test.py
```

This proves `retain`, `recall` and `reflect` work against whatever provider is configured. If it
fails, the problem is credentials, credit or provider capacity, and nothing in this codebase can
help. Fix that first. Every confusing bug I have had in this project was actually this.

For a key-free environment:

```bash
.venv/bin/python scripts/local_model.py
```

Downloads about 3.5 GB on first run. Slow, but proves the project runs with no accounts.

---

## Architecture in one diagram

```
browser
  │  fetch /api/*
  ▼
app/main.py  (FastAPI, async routes)
  │  await memory.call(...)          ← the only legal path to Hindsight
  ▼
app/memory.py  ──►  _LoopThread  ──►  hindsight_client
  │                                    │
  │  triage()                         ▼
  │    1. recall()                 Hindsight Cloud
  │    2. reflect()                  (or an embedded engine)
  │    3. read mental models
  │    4. _exposure_from_corpus()  ← code overrides the model
  ▼
JSON back to the browser, which renders and knows nothing else
```

`app/analysis.py` hangs off the same engine and is only called by `/api/learning-curve`.

---

## The output contract, and why it exists

`reflect` accepts a `response_schema` and Faultline passes one. **Hindsight Cloud ignores it and
returns prose.** This is a real, reproducible finding, documented in `HINDSIGHT_PLAIN.md`.

So the contract is carried in the prompt instead. `TRIAGE_FORMAT` in `app/memory.py` specifies a
line-per-field plain-text format, and `_parse_triage` parses it.

### If you change the contract

1. Update `TRIAGE_FORMAT` **and** `_parse_triage` together. They are one contract split across two
   functions and there is no test tying them, so a change to one without the other fails silently.
2. Watch the **500-token query limit**. `reflect` rejects anything longer with
   `Query too long: N tokens exceeds maximum of 500`. Character counts are not token counts;
   assume roughly 2.7 characters per token and leave headroom. `TRIAGE_FORMAT` plus the alert is
   currently about 450 tokens, which is tight.
3. If a new field is added, add it to `_parse_triage` returning an empty default rather than
   raising. A partial answer during an outage beats a stack trace.

### Parsing rules, and why they are lenient

- Regex extraction of `FIELD: value` lines, not a JSON parse, because the model sometimes
  wraps output in a code fence.
- A missing field yields an empty list or empty string, never an exception. The UI renders what it
  got.
- `MATCH` is coerced to 0 to 100 and anything unparseable becomes 0.
- `INCIDENTS` is filtered to `INC-[\w-]+` so a hallucinated id cannot reach the UI.

---

## Adding an incident to the corpus

Append to `INCIDENTS` in `app/corpus.py`. Required fields, and what breaks if you skip them:

| Field | Why it matters |
| --- | --- |
| `id` | The entity that links this incident to others. If it is unique, the graph can join it |
| `service` | Graph traversal depends on it |
| `opened`, `resolved` | ISO with `Z`. **Temporal retrieval is one of four recall arms and is only correct with real timestamps.** An incident stamped today cannot be found by "what broke in March" |
| `alert_text` | Verbatim. This is the retrieval surface. A paraphrase materially degrades matching |
| `root_cause` | The field that lets two incidents share a fingerprint |
| `runbook` | A high-signal rare string, found by the BM25 arm |
| `action_items` | Each needs `owner`, `text`, `status` of `open` or `done` |

Then re-seed, with `force`, or the old memories linger and corrupt the measurement:

```bash
curl -X POST "localhost:8000/api/setup?force=true"
```

### And update the answer key

If your new incident shares a root cause with an existing one, add both to `CLUSTERS` in
`app/analysis.py`. The measurement is only meaningful if the key is right, and a wrong key makes
the score flattering for the wrong reason. That happened once: three clusters shared a theme but
not a root cause, and cutting them moved the score from 55% to 83% with no code change.

`CLUSTER_QUERY` needs an entry too for any new cluster: the query the measurement uses, phrased
the way an on-call engineer would ask.

---

## Adding a route

```python
@app.get("/api/thing")
async def thing() -> dict[str, Any]:
    if not engine.connected:
        return _err(RuntimeError("memory engine not connected"), 503)
    try:
        return await memory.call(engine.thing)
    except Exception as exc:
        return _err(exc)
```

Four things, all of them load-bearing:

1. `async def`, because the memory client is synchronous.
2. `memory.call`, not `asyncio.to_thread`. See the top of this file.
3. `engine.connected` check, so the UI gets a clean 503 instead of a stack trace.
4. `_err`, which returns JSON with `error` and `trace`. Returning a bare exception would make the
   response unparseable.

**Known wart:** `setup()` and `mental_models()` can return HTTP 200 with an `error` key in the body,
because the failure happened in a background thread that could not change the status code. The
client helper in `web/app.js` checks for the key, not just the status. If you add a route, either
raise the status or keep that check.

---

## Idempotency

The banks live in Hindsight Cloud, so they outlive the process. Setup runs on every page load and
must be safe to repeat:

- `ensure_banks` checks `banks_ready()` first and calls `update_bank_config` instead of
  `create_bank` when they exist.
- `install_mental_models` swallows the "already exists" conflict on purpose. Re-creating a mental
  model would throw away a version that has already learned something. That is the opposite of
  what you want.
- `seed()` is skipped entirely when `is_seeded()` is true.

---

## Conventions

**Comments explain why, not what.** The genuinely valuable comments in this repo are the ones
recording a decision and its alternative: why `run_blocking` exists, why the exposed set is built
in code, why the answer key was cut, why `response_schema` is passed anyway. If a comment would
still be true after you delete the line it sits on, delete the comment.

**No business logic in `web/`.** If the browser needs to know something, return it from an API.

**No new tokens without a reason.** Every value in `web/base.css` is justified in `DESIGN.md`. If
you add one, add the reason there too, or the palette starts drifting and R-29 fails silently.

**No em dashes in interface text.** Checked by grep, zero permitted.

**Contrast is measured, not eyeballed.** If you touch a colour, recompute the ratios. There is a
five-line contrast function in the git history of this conversation; keep it handy. The palette
currently passes 15 pairings with a worst case of 5.38:1.

---

## Testing

There is no test suite. That is a real gap and it is on the roadmap. What exists instead:

| Check | Command | What it proves |
| --- | --- | --- |
| Memory layer | `.venv/bin/python scripts/smoke_test.py` | The provider works at all |
| Everything | Open `/console?autotriage=1` | The full path works end to end |
| Retrieval quality | `curl -s localhost:8000/api/learning-curve` | The number did not regress |
| Grounding | Read `recurrence_risk` in the triage response | The override still works |
| Mobile | Load `/console` in a 390px viewport, inspect `document.documentElement.scrollWidth` | No overflow |
| Contrast | Recompute the pairs in `web/base.css` | AA still holds |

**When testing screenshots, watch out for this:** headless Chrome enforces a minimum window width,
so `--window-size=390,...` produces a *crop* of a wider render, not a 390px layout. Load the page
in an iframe of the target width and measure element bounding boxes instead. I reported a mobile
failure that was purely this artifact.

---

## Deployment

There is none, and that is deliberate for the current stage. When you need one:

- The API is a normal ASGI app. `uvicorn app.main:app` behind any reverse proxy.
- The frontend is three static files and one page, no build step. Serve from a CDN.
- The memory is in Hindsight Cloud, so the app itself is stateless. Scale horizontally with no
  coordination.
- The only secret is the Hindsight key. See [SECURITY.md](../SECURITY.md).

---

## Where the interesting problems are

Listed in the order I would tackle them, with honest difficulty:

1. **The 500-token query limit.** The alert plus the output contract is about 450 tokens. A longer
   alert or a richer contract will hit the ceiling. The clean fix is moving the format spec into
   `reflect`'s `context` parameter, which may not share the same limit. Untested.
2. **`response_schema` is ignored on Cloud.** Faultline passes one anyway because it works elsewhere.
   Worth re-testing per release; if Cloud starts honouring it, delete the prompt contract and the
   parser.
3. **The threading workaround depends on client internals.** `run_blocking` works around a bug in
   the client's event loop handling. If a future version fixes it, this becomes unnecessary. It is
   harmless, but do not build on top of it.
4. **The exposed-services list is built from static corpus state.** Deterministic and honest, but it
   means Faultline does not *discover* exposure, it reads it. Making it query real infrastructure is
   the actual product.
5. **The answer key is hand-maintained.** It is the weakest link in the measurement. Deriving it
   from the consolidated observations instead would be better, and circular.

Next: [ARCHITECTURE.md](ARCHITECTURE.md)
