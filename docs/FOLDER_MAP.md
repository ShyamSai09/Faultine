# Every file, and what it does

A map of the whole repository. If you are wondering "what is this file for", the answer is here.

---

## The shape of it

```
faultline/
  app/          the brain. Python. No HTML here.
  web/          the face. HTML, CSS, JavaScript. No business logic here.
  docs/         what you are reading
  scripts/      things you run by hand
  data/         created at runtime, not in version control
```

The dividing line is strict on purpose. `app/` never touches the screen, `web/` never makes a
decision. If you find business logic in `web/app.js`, something has gone wrong.

---

## Root files

### `README.md`

The front door. What the project is, how to run it, the layout, the API. Start here if you already
know what you are looking at.

### `DESIGN.md`

Why the site looks the way it does. Every colour, typeface and layout choice with a one-line
reason attached, plus a list of what was rejected and why. Read this before changing any styling.

### `requirements.txt`

The Python packages to install. The only ones that matter are `hindsight-all` (the memory system)
and `fastapi` (the web server).

### `run.sh`

Starts the web server. Checks that `.env` and `.venv` exist first and tells you what to do if not,
so it fails with instructions rather than a stack trace.

### `.env`

Your secrets. **Never committed to version control.** Contains either a Hindsight Cloud key or the
settings for a local memory engine.

### `.env.example`

The same file with the secrets blanked out and comments explaining each option. Copy it to `.env`
and fill it in. This one *is* committed.

### `.gitignore`

The list of things never committed: `.env`, the virtual environment, the local memory database, log
files, and macOS junk.

### `DESIGN.md`

Why the site looks the way it does: the idea, every colour and typeface with a one-line reason
attached, the dials, what was rejected, and the rules being held. Read this before changing any
styling. It also carries the author's own caveat that an agent-chosen aesthetic skews toward the
default taste these rules exist to filter.

### `article.md`

The long-form write-up, written for publication. No mention of any competition, on purpose, because
the rules require it.

### `linkedin.txt` and `linkedin-short.txt`

The social posts. Two versions because the brief asked for under 800 characters and the longer one
is more persuasive. Pick based on what you want.

---

## `app/`, the brain

### `app/config.py`

Reads `.env` and exposes settings. Also has a job that is easy to miss: it loads `.env` into the
process environment *before* anything imports the memory client, because Hindsight reads its own
configuration from environment variables and there is no way to pass it in directly.

It also names the two banks and the empty control bank.

### `app/corpus.py`  (the biggest file, and the most important one)

The entire dataset, as Python data. Ten services, nineteen incidents, nineteen unclosed actions,
four infrastructure conditions, and the live alert used in the demo.

Every incident has: an id, a service, a severity, open and close times, how it was detected, the
alert text as it actually fired, a minute-by-minute timeline, a log excerpt, a root cause, a
resolution, the runbook used, the customer impact in euros and minutes, and its postmortem actions
with owners and completion status.

**The corpus is the product.** The interesting behaviour comes from the shape of this data, not
from the code. The spine of it is a single thread that runs through three incidents across five
months: a wildcard identity setting breaks payments, then checkout, then payout-worker, and the
to-do item that would have stopped it is written twice and never closed.

Two functions matter beyond the data itself:

- `open_action_items()` flattens every never-completed action across all incidents into one list.
  This is the backlog the agent reasons over.
- `SERVICE_STATE` describes four shared settings that are currently wrong somewhere. This is what
  lets the system say "these two services are exposed" as a fact rather than a guess.

### `app/memory.py`  (the only file that talks to Hindsight)

Everything Hindsight-related lives here so the rest of the app never has to think about it.

The parts worth reading:

| Part | What it does |
| --- | --- |
| `_LoopThread` | Runs every memory call on one dedicated thread. See the long comment: the client binds its connection pool to the first event loop that touches it, and this is the workaround |
| `MemoryEngine.start()` | Connects to Hindsight Cloud if configured, otherwise starts a local engine. Returns which mode, so the UI can show it |
| `ensure_banks()` | Creates both banks with their missions, directives and observation instructions. Idempotent, so running setup twice is safe |
| `install_mental_models()` | Installs the three standing questions |
| `seed()` | Loads the corpus. Passes original timestamps, structured metadata and tags |
| `triage()` | The main event. Recall, then reflect, then read the mental models, then ground the result |
| `_exposure_from_corpus()` | The override. Builds the list of exposed services from recorded state instead of trusting the model |
| `_parse_triage()` | Turns the model's formatted reply into the shape the UI renders. Degrades to partial output rather than raising |
| `_baseline_answer()` | The no-memory comparison. Runs the same query against the empty control bank |

Also here: the missions, the directives, the three mental model definitions, and the output format
contract the model is asked to follow.

### `app/main.py`

The web server. About ten routes. Thin on purpose: it validates input, calls into `memory.py`, and
returns JSON. No reasoning lives here.

Every route that calls Hindsight is `async` and hands the blocking work to `memory.call`, because
the memory client is synchronous and calling it directly from async code breaks in a confusing way.

### `app/analysis.py`

Measures whether the memory is actually any good.

It contains a hand-written answer key: a list of which incidents genuinely share a root cause.
Then for each incident it asks Hindsight to recall the failure mode and checks which of the true
siblings come back. No model generation is involved, because `recall` ranks locally and cheaply.

This is the file that turns "memory helps" into a number you can argue with. It deliberately reports
its one miss.

### `app/__init__.py`

Empty. Present so `app` is a package and the imports work.

---

## `web/`, the face

### `web/index.html`

The console. One page, three views switched by the tabs: Console, Learning curve, Memory, Corpus.
Pure structure, no behaviour.

### `web/app.js`

All the client behaviour: fetching, rendering, tab switching, the demo auto-play flag, and the
before/after toggle. Knows the shape of the data the server returns and nothing about why.

### `web/base.css`

Design tokens and shared primitives, loaded by both pages: the palette, the two typefaces, the
masthead, the ruled gutter motif, the clipping block for pasted machine output, buttons, tables,
focus rings, and the empty, loading and error states.

The one rule that runs through all of it: if a machine produced it, it is set in the monospace
face. Prose is prose, logs are logs. That typographic split is the product's thesis, so it is
enforced rather than suggested.

### `web/console.css`

Layout for the three-column console, the four tabs, and the responsive behaviour at 1240, 900 and
620 pixels.

### `web/landing.html`, `web/landing.css`, `web/landing.js`

The landing page. Mostly static. Two things the script does: fetch the alert text from the API so
it is never a stale copy, and mark which nav section you are reading with an
`IntersectionObserver` rather than a scroll handler.

### `web/favicon.svg`

One glyph, served as SVG. Invented, therefore provisional, and `DESIGN.md` says so.

### `web/img/`

Screenshots captured from the running console and landing page, used on the landing page and in the
docs.

---

## `scripts/`

### `scripts/smoke_test.py`

Proves `retain`, `recall` and `reflect` all work against whatever provider you configured. Run
this first on a new machine. If it passes, the memory layer is real and every other problem is
yours, which is a useful thing to know early.

### `scripts/validate.py`

The holdout experiment. Withholds N incidents, seeds a separate bank from the remaining ones,
replays each withheld alert, and scores the answer against the hand-written key. Writes to a
throwaway bank and leaves the demo untouched.

It is the answer to "is the data just hardcoded?", and its own result is inconclusive, which
`docs/VALIDATION.md` explains in full: on a nineteen-record corpus where postmortems name each
other in their root causes, withholding an incident does not fully hide it. It also found a real
defect, which is how the incident-id grounding in `app/memory.py` got built.

### `scripts/local_model.py`

The same test, but against a model running on your own laptop with no API key. Slow, but it means
the project can be run with no accounts and no internet.

---

## `docs/`

| File | For |
| --- | --- |
| `START_HERE.md` | Newcomers. Ten minutes, no jargon. |
| `WHAT_IS_THIS.md` | The problem, and why a search box cannot solve it |
| `HOW_IT_WORKS.md` | Every step of the mechanism, with the Hindsight feature named at each one |
| `FOLDER_MAP.md` | This file |
| `RUNNING_IT.md` | Installing, configuring, running, and what to do when it fails |
| `SCREENS.md` | What each screen shows and what to look at |
| `THE_NUMBERS.md` | What every figure means and exactly where it comes from |
| `DATA.md` | Why the data is invented and how it was built |
| `HINDSIGHT_PLAIN.md` | Hindsight explained without assuming you know it |
| `WHY_HINDSIGHT.md` | The detailed design rationale, for people reviewing the memory choices |
| `API.md` | Every endpoint, with request and response shapes |
| `VALIDATION.md` | What is measured, what is not, and what failed |
| `TROUBLESHOOTING.md` | The errors that actually happen, and their causes |
| `DEMO_SCRIPT.md` | Word-for-word demo script, and answers to likely questions |
| `GLOSSARY.md` | Every term, defined |
| `DECISIONS.md` | 13 decisions, each with the alternative rejected |
| `img/` | Screenshots used in the docs and the article |

---

## Things that are not in the repository, and why

| Missing | Reason |
| --- | --- |
| `.env` | Contains a secret. `.env.example` is the committed version. |
| `.venv/` | The virtual environment, several hundred megabytes, rebuilt by `pip install` |
| `data/hindsight/` | The local memory database, created on first run |
| Any logo or icon | `web/favicon.svg` and the wordmark's red initial are invented, therefore provisional. `DESIGN.md` says so |
| Any testimonial | There are no real customers. Making one up would be dishonest, so there is no testimonials section |
