# Hindsight, explained for someone new

You do not need to know anything about Hindsight to use Faultline. This page is here in case you
want to understand the machinery, and in case you are evaluating the project and want to know which
parts are doing the real work.

---

## What it is

Hindsight is a memory system for AI agents, built by Vectorize. Open source, MIT licensed.

The problem it solves: an AI assistant talks to you, then forgets. Next conversation, zero memory.
You have explained yourself again. It has forgotten the thing you told it twenty minutes ago.

Hindsight is a filing cabinet with some unusual properties, which are the point.

---

## The three operations

Everything is built on three verbs. If you learn only these three, you can reason about the whole
system.

### `retain` (write)

You hand it raw material: a document, a conversation, a log, an incident report. It does not just
store the text. It calls a language model to pull structured facts out of it.

Hand it a paragraph and it extracts, roughly:

> - payments-api returned HTTP 503 for 41 minutes
> - when: 2026-03-14
> - why: stale IAM role after credential rotation
> - fixed by: runbook RB-07
> - owner of the follow-up: Jonas Weber

It also builds several indexes over that content so the facts can be found later from any angle:
vectors (meaning), full text (exact words), an entity graph (what is connected to what), and dates.

**Things to know about it:**

- It costs a language model call per chunk. This is why Hindsight needs a real model with a large
  output budget, and why the free tier of some providers does not work. A single retain can emit tens
  of thousands of tokens.
- The model is configurable: 25+ providers, any OpenAI-compatible endpoint, or a model running on
  your own machine.
- The two embedding models (search and ranking) download from Hugging Face on first run and then
  work offline.

### `recall` (search)

You give it a question. It does **not** do one search. It runs four in parallel:

| Strategy | Matches on | Example question it answers |
| --- | --- | --- |
| Semantic | meaning | "when was authorisation broken?" |
| Keyword (BM25) | exact words | "which runbook mentions `sts:AssumeRole`?" |
| Graph | connected entities | "what else is related to this role?" |
| Temporal | dates | "what broke in March?" |

The four ranked lists are merged with reciprocal rank fusion, re-ranked by a small cross-encoder
that reads the query and each candidate together, and trimmed to a token budget.

This is why it answers "what did Alice do last spring" (temporal) as well as "where does Alice
work" (graph plus semantic, joined from two separate facts). A vector search answers the second
one reasonably and the first one badly.

**No language model is involved in `recall`.** It ranks locally. That matters for cost and for
repeatability.

### `reflect` (reason)

This is the one that is different from a normal search. `reflect` runs a loop:

1. The model looks at what it has
2. It decides it needs more, and searches again
3. It expands what it found, pulling in connected material
4. Repeats until it has enough
5. Only then writes an answer

So `recall` gives you documents and `reflect` gives you an answer that used them. The difference in
quality is substantial, and it is the difference between "here are ten things that might be
relevant" and "here is what happened and what to do".

---

## The part that makes it memory rather than a database

### Observations

Raw retained facts are a mess. Duplicates pile up. Facts contradict each other. Nothing is
summarised.

Hindsight consolidates facts into **observations**: deduplicated beliefs that carry their evidence,
with a proof count, and quotes of the exact source text that supported them.

The important behaviour is that observations are **refined, not overwritten**. When new evidence
contradicts a belief, the belief is updated and the history is kept. So the system can say "this was
true in March, this is true now" rather than losing either.

In Faultline, one observation does the headline work:

> Services `payout-worker`, `inventory-sync`, and `webhooks-relay` are currently identified as
> carrying the insecure IAM role trust policy.

That sentence was formed by reading four separate records about four different services. It is not
in any of them. It is a conclusion the memory arrived at, and it is the sentence that makes
"you are exposed" possible.

### Mental models

A mental model is a standing answer to a standing question. You define the question once and
Hindsight writes the answer, stores it, and rewrites it in the background whenever new memories have
been consolidated.

The property that makes them usable: **reading one is a database read, not a model call.** So an
agent can read its consolidated expertise on every single request at effectively zero cost.

Faultline installs three. You can read them live in the console under "Fingerprints".

### Knowledge pages

A mental model with the machinery hidden: a living document the bank writes about itself,
organised like a wiki, projectable onto disk as plain markdown files. Faultline does not use these
yet. It is the obvious next step for a team that wants to read their own institutional memory as
ordinary documents.

---

## The things you can configure

| Setting | What it does | What Faultline sets |
| --- | --- | --- |
| **Mission** | Natural-language identity for the bank. What this bank is for | "You are the memory of Northwind Commerce's reliability engineering organisation" |
| **Retain mission** | Instructions for the extraction step | Extract services, dates, symptoms, cause, runbook, impact, and each action with its owner and completion status. Keep incident ids as entities |
| **Observations mission** | Instructions for consolidation | Group incidents sharing a root cause. Track actions across incidents so an unclosed one stays visible. Preserve history |
| **Directives** | Hard rules applied during `reflect` | Four: cite evidence, prefer recent, surface unclosed work, never invent |
| **Disposition** | Soft traits: skepticism, literalism, empathy, 1 to 5 | Not set. Faultline relies on explicit directives instead |

**Mission and directives only affect `reflect`.** They do not change what is stored or what `recall`
returns. That is worth knowing if you are debugging: a bad directive changes the tone of answers,
not the underlying memory.

---

## Banks, and why isolation matters

A bank is an isolated memory store. Strictly, one "brain" for one user, agent or project. No
cross-bank leakage, and you can attach different missions to each.

Faultline uses two, and the split is the design:

| Bank | Holds | Why separate |
| --- | --- | --- |
| `faultline-incidents` | Incidents and infrastructure state | Technical questions stay technical |
| `faultline-team` | Unclosed actions and owners | "Who owes what" can be reasoned about as its own ledger |

The payoff is a cross-bank join. To say "that fix was written down twice and never completed", the
system has to start from an incident in one bank, follow it to an action item in another, and then
notice that a second action item with the same meaning was created after a different incident three
months earlier. That is graph traversal across two stores, and it is not something a search
returns.

There is also a third bank, `faultline-control-empty`, created once and never written to, used as
the control for the before-and-after comparison.

---

## Things that will surprise you if you do not know them

**The query length limit.** `reflect` rejects queries over 500 tokens with
`Query too long: 618 tokens exceeds maximum of 500`. This is easy to hit, because the alert text
plus a careful output format contract adds up fast. Character counts are not token counts; assume
roughly 2.7 characters per token and leave headroom.

**`response_schema` may be ignored.** Faultline passes one to `reflect`. Against Hindsight Cloud it
returned prose anyway. Faultline's contract is therefore carried in the prompt and parsed
deterministically. The schema is still passed, because it works elsewhere.

**The synchronous Python client binds its connection pool to the first event loop that uses it.**
Call it from a second thread and aiohttp raises
`Timeout context manager should be used inside a task`, which sounds nothing like what it is.
Worse, `asyncio.to_thread` makes it worse rather than better, because the thread pool attaches the
parent (running) loop to its worker threads. Faultline's fix is `run_blocking` in `app/memory.py`,
which serialises every call onto one dedicated thread with a private, never-running event loop.

**Groq's free tier cannot drive it.** Hindsight's own documentation says so: the free tier allows
8,000 tokens per minute and a single retain can emit around 64,000. You need a paid tier, a
different provider, or Hindsight Cloud.

**Mental models take time to appear.** They are written after consolidation, which is asynchronous.
A model you just installed may be empty for a minute or two. The console handles this by showing
what is available and saying so when there is nothing.

**Recall is cheap, reflect is not.** If you are building something on this, use `recall` wherever
you only need to show or filter memories, and save `reflect` for the answer itself.

---

## Running it yourself

Any Hindsight bank can be poked at directly:

```python
from hindsight_client import Hindsight

client = Hindsight(base_url="https://api.hindsight.vectorize.io", api_key="hsk_...")

client.retain(bank_id="scratch", content="payments-api broke on 2026-03-14 for 41 minutes")
print(client.recall(bank_id="scratch", query="when did payments break?"))
print(client.reflect(bank_id="scratch", query="what broke and how was it fixed?"))
```

If that works, Faultline works. That is what `scripts/smoke_test.py` checks.

- Documentation: https://hindsight.vectorize.io/
- Source: https://github.com/vectorize-io/hindsight
- Background: https://vectorize.io/what-is-agent-memory

For the project-specific design decisions, see [WHY_HINDSIGHT.md](WHY_HINDSIGHT.md).

Next: [API.md](API.md)
