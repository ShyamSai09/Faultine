# Faultline

**An on-call agent that remembers every outage your organisation has ever had — and tells you which one is about to happen again.**

Faultline is built on [Hindsight](https://github.com/vectorize-io/hindsight), the agent memory
system from [Vectorize](https://vectorize.io/what-is-agent-memory). It is not a runbook search
engine. It keeps a running model of *how this organisation fails*, and when an alert fires it
tells you whether you have been here before, what fixed it, and — the part that matters — which
service is still carrying the same fault and has not gone down yet.

```
alert fires ──▶ recall()   4-way retrieval over every incident this org has ever had
            ──▶ reflect()  reason over the consolidated observations
            ──▶ read       mental models written in the background after consolidation
            ──▶ answer     prior incidents · runbook · recurrence risk · unclosed remediation
```

---

## The problem

Postmortems are written, filed, and never read again. The remediation action that would have
prevented the next outage exists as a bullet point in a document nobody opens. So the same root
cause lands three times across three different services, and each time the on-call engineer starts
from zero.

In the seeded corpus this is not hypothetical. Nineteen incidents, ten services, and **nineteen
remediation actions that were written down and never completed** — including the same action
written for the third and fourth time.

## What makes it memory, not retrieval

A vector search over past incident documents can tell you *something similar happened*. It cannot
tell you that the thing that broke in March is still misconfigured in a service that has never
been touched. That requires joining four things that live in different places and different
times:

| Requirement | Hindsight feature |
| --- | --- |
| "we have seen this before" across 19 incidents | `recall()` with TEMPR — semantic, BM25 keyword, entity graph and temporal arms in parallel, fused by RRF and reranked |
| "these two incidents share a root cause despite looking unrelated" | observation consolidation — facts merge into evidence-backed beliefs with a proof count |
| "the sweep that would have prevented this was never finished" | cross-bank entity graph linking the incident to its unclosed action item |
| "the agent is getting better, and I can read that for free" | mental models — Hindsight rewrites them in the background after consolidation; reading one is a database read, not an LLM call |

## The demo

A live SEV2 alert fires on `payout-worker` with an `sts:AssumeRole` `AccessDenied`. On its face
this is a new problem: wrong service, different symptom from the March `payments-api` outage.

Faultline connects it to the March incident, and then to the June incident, and then reads the
open action items from both. It reports that the March and June sweeps were never completed, that
`inventory-sync` and `webhooks-relay` still carry the wildcard trust policy, and that
`payout-worker`'s last successful credential use was 11 days ago — so the underlying fault has
been wrong since May, hidden by a cached token.

Flip the **Memory** switch off and triage the identical alert: the same model, the same prompt, no
memory at all. That contrast is the whole argument.

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # add your Hindsight key, see below
./run.sh
```

Then open:

| URL | What |
| --- | --- |
| `http://localhost:8000/` | The landing page: the problem, the before and after, the evidence |
| `http://localhost:8000/console` | The console, the live triage |
| `http://localhost:8000/console?autotriage=1` | The console with the demo already running |

First load seeds the memory, which takes two to four minutes. Progress is shown in the boot screen.
Docs start at [docs/START_HERE.md](docs/START_HERE.md).

### LLM configuration

Hindsight runs fact extraction on every `retain()`, so it needs a model with a large output budget.
Two working configurations:

- **Hindsight Cloud** — set `HINDSIGHT_API_BASE_URL` and `HINDSIGHT_API_KEY`. LLM included, no
  local setup. (This is what the demo used.)
- **Local llama.cpp** — `HINDSIGHT_API_LLM_PROVIDER=llamacpp`. No API key, no network, no cost.
  The model is downloaded once. Slower, but the project runs on a plane.

> The free Groq tier cannot drive Hindsight: it allows 8k tokens per minute, and a single retain
> call can emit around 64k.

## Documentation

Twenty-four files. Start here and you will not need the rest.

| | |
| --- | --- |
| [**BRIEF.md**](BRIEF.md) | **The whole project in plain English.** The problem, what it does, how we know it works, and what is left to do |
| [docs/START_HERE.md](docs/START_HERE.md) | Ten minutes, no jargon, with a bit more detail than the brief |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | How to use it during an incident, and what every field means |
| [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | How to change it, and the two rules that will bite you |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | The system design, with a diagram and the cost of each choice |
| [docs/DECISIONS.md](docs/DECISIONS.md) | 13 decisions, each with the alternative rejected and what it would have cost |
| [docs/THE_NUMBERS.md](docs/THE_NUMBERS.md) | The provenance of every figure, including which ones are not measurements |
| [docs/VALIDATION.md](docs/VALIDATION.md) | The holdout experiment, and the honest answer to "is the data just hardcoded?" |
| [docs/ROADMAP.md](docs/ROADMAP.md) | What happens next, what I would not do, and the known issues |
| [CHANGELOG.md](CHANGELOG.md) | What changed and why |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Conventions |
| [SECURITY.md](SECURITY.md) | Key handling, and what this does not have |
| [DESIGN.md](DESIGN.md) | Why the interface looks the way it does |
| [anti-slop/audit-001-2026-09-28.md](anti-slop/audit-001-2026-09-28.md) | 16 interface findings against 38 rules, all closed |

The full index, including the Hindsight explainer, the API reference, the data notes, the glossary
and the demo script, is at [docs/README.md](docs/README.md).

## Layout

```
app/
  corpus.py      the Northwind Commerce incident corpus — the data is the product here
  memory.py      the only module that talks to Hindsight
  analysis.py    measures the learning curve against a hand-labelled answer key
  main.py        FastAPI surface
web/             the console. No framework, no build step.
scripts/
  smoke_test.py  proves retain/recall/reflect work against the configured provider
  local_model.py same, on a local model
docs/            22 files. See docs/README.md for the index
```

## API

| Route | Purpose |
| --- | --- |
| `GET /api/state` | connection mode, seed status, corpus counts |
| `POST /api/setup` | create banks, install mental models, seed the corpus |
| `GET /api/corpus` | incidents, services, latent state, the live alert |
| `POST /api/triage` | triage the live alert; `with_memory: false` gives the baseline |
| `POST /api/resolve` | retain the resolution, refresh the fingerprints |
| `GET /api/learning-curve` | the measured recall curve |
| `GET /api/memories` | inspect raw memory, or `recall` with `?q=` |

## Licence

MIT. The incident corpus is synthetic — a fictional company, fictional people, fictional
incidents — though the failure modes are real ones from real postmortems.
