# When it breaks

The errors you will actually hit, what causes them, and how to fix them. Ordered roughly by how
often they happen.

---

## Setup problems

### "No .env found"

```
No .env found. Copy .env.example to .env and add an LLM key.
```

You skipped step 6.

```bash
cp .env.example .env
```

Then open `.env` and fill in your key.

### "No .venv"

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### `ModuleNotFoundError: No module named 'fastapi'`

You installed into the wrong Python. Always use the copy inside the project:

```bash
.venv/bin/python run.sh
```

Or skip the shell script and use `.venv/bin/python -m uvicorn app.main:app --port 8000`.

On Windows the path uses backslashes: `.venv\Scripts\python -m uvicorn app.main:app --port 8000`

---

## Memory and credentials

### `Invalid API key`

The key is wrong, has a stray space, or was copied incompletely.

1. Go to the Hindsight dashboard and copy it again
2. Open `.env` and check the line has no quotes, no trailing space
3. Keys start with `hsk_`

### `429 quota exceeded` or "You exceeded your current quota"

You are out of credit, or on a free provider's rate limit.

**With Hindsight Cloud:** check your balance, and confirm you entered promo `MEMHACK99`. Without
that, a new account may have very little credit.

**With Gemini free:** you will hit this. Hindsight's own documentation says the free tier does not
work, because it allows 8,000 tokens per minute and a single `retain` can emit around 64,000. This
is not a bug you can configure around. Use Hindsight Cloud, a paid tier, or the local model.

### `Query too long: 618 tokens exceeds maximum of 500`

`reflect` has a hard 500-token limit on the query. The alert text plus the output format contract
adds up fast.

**Character counts are not token counts.** Assume roughly 2.7 characters per token, and leave
headroom. If you see this, shorten `TRIAGE_FORMAT` in `app/memory.py`, or move part of the
instructions into the `context` parameter of `reflect`.

**The lesson:** budget the query. See [HINDSIGHT_PLAIN.md](HINDSIGHT_PLAIN.md).

### `Timeout context manager should be used inside a task`

The most confusing error in the whole project, because it has nothing to do with timeouts.

**Cause:** Hindsight's Python client caches an aiohttp connection pool bound to the event loop that
first used it. Calling it from a different thread makes aiohttp refuse, with this message.

**Do not** try to fix it with `asyncio.to_thread`. That makes it worse, because the thread pool
attaches the parent (running) loop to its worker threads.

**The fix is already in the code:** `run_blocking` in `app/memory.py` serialises every memory call
onto one dedicated thread with a private, never-running event loop. Any route that calls Hindsight
must go through it:

```python
# correct
result = await memory.call(engine.triage, corpus.LIVE_ALERT, True)

# wrong, will break in confusing ways
result = engine.triage(corpus.LIVE_ALERT, True)
```

If you hit this, you have probably called `engine.client` directly from a route instead of from
inside `memory.call`.

### `This event loop is already running`

Same family of bug. The client always calls `run_until_complete`, so the loop it gets must never
already be running. A loop that is being `run_forever` on another thread will not do.

### `Mental model 'failure-fingerprints' already exists`

You ran setup twice. This is harmless and handled: `install_mental_models` catches it, because
re-creating a model would throw away a version that has already learned something. If you actually
want a clean slate, call `/api/setup?force=true`.

### `name 'root_cause' is not defined`

A refactor left a variable behind. If you see this, a function body was moved without moving its
local variables with it. Check the top of the function.

---

## Seeding problems

### The progress bar sticks at "retaining incidents 1/19"

A `retain` call is failing. The real error is usually further down the server log.

Look at the terminal where you started the server. You will find something like:

```
Fact extraction failed: 1/1 chunks failed. chunk 0: ServerError: 503 UNAVAILABLE
```

That is the model provider failing, not Faultline. Check your credit and your key.

### Seeding took ten minutes

Normal on first run with nineteen records, each needing a model call. Later runs are instant, because
the memory is already on the server. If it is slow every time, you are probably re-seeding: check
you are not calling `/api/setup?force=true` on every page load.

### `is_seeded` returns true but the console shows nothing

The banks have memories, so setup skips seeding, but the running process is a different one that
has not loaded them into its local state. Restart the server:

```
Control + C, then ./run.sh
```

---

## Interface problems

### The page is blank

JavaScript failed. Open the browser's developer console (F12 on most browsers, or right-click then
Inspect) and reload. The error will be at the top.

Most likely cause: a stale cached stylesheet or script. Hard reload with `Control` and `Shift` and
`R`.

### Text runs off the right edge on a phone

A real bug, not a setting. Check `console.css` for the breakpoint. The rules are:

- nothing may use a fixed `width`
- tables go inside `.tbl-wrap`, which scrolls horizontally
- code blocks use `overflow-wrap: anywhere`
- interactive controls are at least 44px tall

### The Memory toggle has no effect

Check the top right of the console says `Hindsight Cloud`, not `not connected`. And check
`/api/state` reports no error.

### Mental models are empty

They are written after consolidation, which is asynchronous. A fresh seed can leave them empty for
a minute or two. Wait and reload. If they stay empty, check the server log for mental model errors.

### The match percentage is low or zero

Usually means the corpus was not seeded, or the alert does not match the failure modes in the data.
Try: reseed with `?force=true`, then triage again.

### The Learning curve tab says "no measurement yet"

Same cause. The measurement runs at the end of seeding. If seeding was skipped because the banks
already existed, it runs on the first request to that tab instead.

---

## The port

### `Address already in use`

```bash
# find out what is holding it
lsof -nP -iTCP:8000 -sTCP:LISTEN

# kill it
kill -9 <the pid>

# or just use a different port
./run.sh --port 8001
```

---

## Reporting something new

If you hit an error not listed here, the two most useful things to include are:

1. The output of `curl -s localhost:8000/api/state | python3 -m json.tool`
2. The last 30 lines of the server log, from the terminal where you started it

The `trace` field in any error response also has the relevant part of the stack trace.
