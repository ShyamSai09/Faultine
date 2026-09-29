# Architecture

The technical shape of the system, and why each part is where it is. For the conceptual version in
plain language see [HOW_IT_WORKS.md](HOW_IT_WORKS.md); for the memory-specific design see
[WHY_HINDSIGHT.md](WHY_HINDSIGHT.md).

---

## Components

```
┌──────────────────────────────────────────────────────────────────┐
│  browser                                                          │
│  landing.html + landing.js      index.html + app.js               │
│  base.css  console.css  landing.css                              │
└───────────────────────────┬──────────────────────────────────────┘
                            │  fetch, JSON only
┌───────────────────────────▼──────────────────────────────────────┐
│  app/main.py       FastAPI. 10 routes. async. Validates, delegates│
└───────────────────────────┬──────────────────────────────────────┘
                            │  await memory.call(fn, ...)   ← only legal path
┌───────────────────────────▼──────────────────────────────────────┐
│  app/memory.py                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ _LoopThread    1 queue, 1 worker thread, 1 private loop    │  │
│  │ run_blocking() the only way to touch the Hindsight client  │  │
│  └────────────────────────────────────────────────────────────┘  │
│  MemoryEngine                                                    │
│    triage()          recall → reflect → mental models → ground   │
│    _baseline_answer() same query, empty control bank             │
│    _exposure_from_corpus()  code overrides the model            │
│    _parse_triage()          format contract → JSON              │
│  MENTAL_MODELS / DIRECTIVES / MISSIONS / TRIAGE_FORMAT          │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│  Hindsight  (Cloud, or embedded engine)                          │
│    faultline-incidents   faultline-team   faultline-control-empty│
└──────────────────────────────────────────────────────────────────┘

  app/corpus.py      the dataset, no logic beyond two functions
  app/analysis.py    scoring, off to the side, not on the request path
```

---

## The request path, in order

A triage takes about four seconds and touches Hindsight three times.

| # | Call | Cost | What it is for |
| --- | --- | --- | --- |
| 1 | `recall` | ~0.4s | 8 memories, four retrieval arms fused and reranked locally. No model call |
| 2 | `get_mental_model` ×3 | ~0.2s each | A database read each, not a generation. This is what makes them usable per request |
| 3 | `reflect` | ~4s | The one expensive call. Runs an agentic search loop, then synthesises |

Then two things happen locally and instantly: the answer is parsed into the shape the UI renders,
and the exposed-services list is replaced with the corpus ground truth.

### Why `recall` runs before `reflect` and not only inside it

`reflect` already searches. Calling `recall` separately looks redundant, and is: the recalled
memories are not fed to `reflect`.

It exists so the right-hand column can show *what came back*, with types and scores, rather than
only the synthesised answer. That is a transparency requirement, not a retrieval one. It costs
0.4 seconds and one extra call.

---

## Data flow for one incident

```
seed()
  │
  ├─► retain(bank_incidents, incident_record, timestamp=opened, metadata, tags)
  │     └─ Hindsight extracts facts, builds vectors + BM25 + entity graph + dates
  │
  └─► retain(bank_team, action_item, timestamp=opened, metadata)
        └─ same, into the other bank

      ... later, in the background ...

  └─► observations consolidate across incidents
  └─► mental models rewrite on delta
```

Two details that are easy to get wrong and expensive to debug:

**`timestamp` must be the incident's real `opened` time.** If everything is stamped at ingestion
time, the temporal recall arm becomes useless and the agent can no longer say "this also happened
in March". That sentence is most of the value.

**The `retain_mission` asks for incident ids to be kept as entities.** Without that instruction the
extractor writes prose, ids stop being joinable, and the cross-bank link between an incident and
its unclosed action silently stops working. No error. Just a worse product.

---

## The two memory banks, and the join

| Bank | Contents | Cardinality |
| --- | --- | --- |
| `faultline-incidents` | 19 incident records, 4 latent state records, the live incident once resolved | 24 |
| `faultline-team` | 19 unclosed action items | 19 |
| `faultline-control-empty` | nothing, ever | 0 |

Isolation is strict in Hindsight, and the split earns its keep in exactly one place. To report a
fix that was promised twice and never done, the system must:

1. Start from an incident in `faultline-incidents`
2. Follow the failure mode to the state record, for the exposed list
3. Cross to `faultline-team` for the action items
4. Notice a second item with the same meaning, raised after a *different* incident three months
   earlier

Step 4 is a traversal across two isolated stores. No amount of retrieval similarity produces it.

### The control bank

Created once, never written to. The no-memory comparison runs the **identical** query against it:
same model, same four-way retrieval, same directives, same prompt. Memory is the only variable.

This matters more than it sounds. Most demonstrations of "memory helps" compare a good prompt
against a deliberately weak one, which proves nothing, because the obvious objection is that the
weak prompt was rigged. A control bank cannot be accused of that.

---

## The grounding step

The only place where the system's output is not the model's.

The model reliably identified the failure mode, the two prior incidents and the runbook. It did not
reliably know which services were exposed: asked directly, it named whichever services appeared in
the incidents it had just cited, including two that had been patched by hand.

Its reasoning was defensible. All those services are built from the same Terraform module, which
still has the unsafe default, so all are technically at risk. That is a real argument and a wrong
answer, and sending on-call after a fixed service costs minutes while customers are affected.

So the division of labour became explicit:

| Concern | Owner | Why |
| --- | --- | --- |
| Which failure mode is this | model | Judgement over evidence |
| Which prior incidents share the cause | model | Judgement |
| What to do first | model | Judgement |
| Which services are still exposed | **code** | It is a recorded fact, not an inference |
| The count of times an action was promised | **code** | It is a count |

The model returns one token, `STATE: iam_role_trust_policy`, and the code builds the list from the
latent-state record, using the model's prose as the explanation underneath.

**Let the model do the judgement and the code do the bookkeeping.** This is the single most
useful design correction in the project, and it generalises to any agent that mixes inferred
reasoning with recorded state.

---

## Why one dedicated thread

The full explanation is at the top of [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md). In brief:

Hindsight's sync client does `asyncio.get_event_loop().run_until_complete(...)`, and its aiohttp
pool is bound to the first loop that used it. Two constraints follow:

1. The loop must never be *running* when a call happens, because the client always calls
   `run_until_complete` on it.
2. The loop must never *change*, because a cached pool carrying timeout handles from a dead loop
   makes aiohttp raise `Timeout context manager should be used inside a task`.

`asyncio.to_thread` satisfies neither: anyio attaches the parent (running) loop to its worker
threads, which produces both failure modes at once.

`_LoopThread` is a queue plus one worker thread that sets a private loop once and never runs it
forever. Calls serialise onto it. One thread, one loop, one pool.

A side effect: **all Hindsight calls are serialised**, so concurrent requests queue. At four
seconds per triage that is not a bottleneck here, and it is the price of correctness. It would need
revisiting for real concurrent load.

---

## Module boundaries

| Layer | May import | May not |
| --- | --- | --- |
| `web/` | nothing | Anything from `app/`. It only knows JSON shapes |
| `app/main.py` | `app.memory`, `app.analysis`, `app.config`, `app.corpus` | `hindsight_client` directly |
| `app/memory.py` | `app.corpus`, `app.config` | FastAPI, anything web |
| `app/analysis.py` | `app.corpus`, `app.config` | `app.memory` internals |
| `app/corpus.py` | nothing | Anything |

The rule that matters: **`app/main.py` must not import `hindsight_client`.** All memory access goes
through `memory.call` or `run_blocking`. Importing the client in a route is how the threading bug
gets reintroduced.

---

## Testing seams

There is no test suite, which is the largest gap. What the structure makes easy:

- **`app/analysis.py`** is pure scoring against a key, already exposed at an API route. The easiest
  candidate for a regression test.
- **`_parse_triage`** is a pure function from text to dict. Trivial to test, and the most fragile
  part of the system, because the prompt contract and the parser are coupled with nothing tying
  them together.
- **`_exposure_from_corpus`** is pure and is the correctness guard for the whole grounding step.
- **`corpus.py`** is data. A test asserting unique ids, valid service references, and well-formed
  timestamps would catch the two syntax-level bugs I hit during the build.

What the structure makes hard: anything involving the client, because it cannot be constructed
without a live event loop and a real connection.

---

## Cost and latency

| Operation | Latency | Notes |
| --- | --- | --- |
| `retain` (one incident) | ~2.5s | One model call per chunk. The single most expensive operation |
| `recall` | ~0.4s | No model call. Ranks locally |
| `reflect` | ~4s | The expensive one. An agentic search loop, then synthesis |
| `get_mental_model` | ~0.2s | A database read |
| Full triage, warm | ~4s | Three calls |
| Cold seed (24 records) | 2 to 4 min | 24 retains, serialised |
| Learning curve | ~3s | A handful of local recall calls, no model |

Serialised retains are the cold-start bottleneck. `retain_batch` would parallelise this and is the
obvious optimisation if seeding time ever matters.

---

## What the structure deliberately does not have

| Absent | Reason |
| --- | --- |
| Authentication | Nobody uses it but the author. Adding it now would be theatre |
| Persistence beyond Hindsight | The banks are the database. A second source of truth would be a bug |
| A test suite | The largest real gap. On the roadmap |
| Streaming responses | Reflect is a single call; streaming it would complicate the format contract for no user-visible gain |
| Caching | Every triage is a real reflect. Caching would undermine the before/after comparison |
| A queue for seeds | Seeding is a startup task. A job system for it is unjustified |
| Real infrastructure integration | The exposed list is read from static state. Probing real systems is the actual product, and out of scope here |

Next: [DECISIONS.md](DECISIONS.md)
