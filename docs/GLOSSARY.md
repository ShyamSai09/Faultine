# Glossary

Every term used in this project, defined. Skim this if something in the docs sounded like a word
you did not want to stop and look up.

---

## The domain

**Alert**
A machine-generated message saying something is wrong. Usually from a monitoring tool. In this
project the alert text is the input the agent reasons about, and it is always shown verbatim rather
than summarised.

**Incident**
One occurrence of something breaking, with a start time, an end time, a cause, and a write-up. The
unit of history.

**Postmortem**
The document written after an incident. Usually contains a timeline, a root cause, an impact
assessment, and a list of actions to prevent a repeat. This project is named Faultline because the
interesting content in a postmortem is the part that never gets acted on.

**Remediation action**
One of those "to do" items in a postmortem. Has an owner and a status. Nineteen of them in this
corpus were never completed.

**Runbook**
The written procedure for handling a specific class of problem, identified by a code like `RB-07`.
The single most valuable thing a postmortem can hand you, because it removes the need to think.

**On-call**
The rotating responsibility to be available when something breaks, and to handle it. Often outside
working hours. The audience for this entire product.

**Service**
One deployable piece of a system. The corpus has ten, from `payments-api` (tier 1, breaks revenue)
to `reporting-etl` (tier 3, breaks a morning meeting).

**Tier 1 service**
A service whose failure directly loses money or blocks customers. Three of the ten. Where the
consequences of being wrong are highest.

**MTTR**
Mean Time To Restore. Average minutes from an incident starting to service coming back. The number
an on-call team is judged on, and the one this project exists to reduce.

**Recurrence**
The same underlying cause causing a new incident. The thing that makes a single incident worth
writing down: it teaches you something that can prevent a second one.

**SLO**
Service Level Objective. The reliability target a team commits to, such as 99.95% uptime. Used here
to explain which services matter most.

---

## The memory system

**Hindsight**
The memory system this project is built on, by Vectorize. Open source. Documentation at
hindsight.vectorize.io.

**Bank**
An isolated memory store. One "brain" for one user, agent or project. No content leaks between
banks. This project uses three.

**Retain**
The write operation. You hand Hindsight raw material and it extracts structured facts, builds
search indexes, and links entities.

**Recall**
The search operation. Runs four retrieval strategies in parallel and merges them. Returns memories.
**No language model is involved.**

**Reflect**
The reasoning operation. Runs a loop where a model searches, expands, searches again, and only then
answers. Returns a written answer rather than a list of memories.

**Observation**
A consolidated belief formed from many retained facts, carrying its evidence and a proof count.
Observations are refined rather than overwritten as new evidence arrives, so history is preserved.
This is what makes Hindsight memory rather than a filing cabinet.

**Mental model**
A standing answer to a standing question, rewritten in the background as evidence accumulates.
Reading one is a database read, not a model call, which is what makes them cheap enough to use on
every request.

**Knowledge page**
A mental model with the machinery hidden: a living document the bank writes about itself,
organisable like a wiki. Not used in this project yet.

**Mission**
A natural-language description of what a bank is for, which shapes extraction and consolidation.
Set in `app/memory.py`.

**Directive**
A hard rule attached to a bank, applied during `reflect` only. This project uses four, including
"never invent" and "surface unclosed work". The second one is the reason the product exists.

**Disposition**
Soft traits that shape reasoning style: skepticism, literalism, empathy, each 1 to 5. Not used
here; explicit directives do the job more precisely.

**Consolidation**
The background process that turns raw facts into observations. Asynchronous, which is why a fresh
seed has no mental models for a minute or two.

**Cross-encoder**
A small model that reads a query and a candidate memory together and scores how well they match.
Used to re-rank recall results. Runs on your machine, not in the cloud.

**Embedding**
A list of numbers representing the meaning of a piece of text, so that similar meanings land near
each other. What "semantic search" is built on.

**BM25**
A classic keyword scoring algorithm. Better than embeddings for rare exact strings like
`sts:AssumeRole` or `RB-07`, which is why Hindsight runs it alongside vector search rather than
instead of it.

**TEMPR**
Hindsight's name for its four parallel retrieval strategies: semantic, keyword, graph, temporal.

**Entity graph**
The network of what is connected to what. How a memory can go from an alert on one service to a
setting on a different service that has never been in the same document.

---

## The approach

**RAG**
Retrieval Augmented Generation. The common approach: chop documents into chunks, embed them, and
when a question comes in, feed the most similar chunks to a model. Good at "find me the document
about this". Cannot form a conclusion that is not written in any single document, and cannot follow
a link between two collections.

**RAG versus memory**
The distinction this project is built on. RAG finds documents. Memory holds beliefs, links across
documents, and remembers what used to be true. See [WHAT_IS_THIS.md](WHAT_IS_THIS.md) for the
concrete example of why the difference matters here.

**Grounding**
Making an answer depend on what is actually stored rather than on what a model would guess. The
term is used in two senses in this project: the general concept, and the specific step where code
overrides the model's answer. See [HOW_IT_WORKS.md step 5](HOW_IT_WORKS.md).

**The control group**
A bank that is created once and never written to, used to run the identical query with zero
memories. It exists so the before-and-after comparison isolates memory as the only variable rather
than comparing against a deliberately weak prompt.

**Fingerprint**
A failure mode described by its observable symptoms rather than by its cause. Two incidents with
different causes can share a fingerprint; an incident and a later one with the same cause but
different symptoms are recognised as the same fingerprint once the cause is understood.

**Cross-service recurrence prediction**
The main capability: given a failure in one service, identifying other services carrying the same
underlying condition that have not failed yet. Not possible with retrieval, because it requires
joining a past incident to present configuration state.

---

## The build

**Virtual environment (`.venv`)**
A private folder holding this project's dependencies, so they do not conflict with anything else on
your machine. Made with `python3 -m venv .venv`.

**Seed**
To load the corpus into memory for the first time. Takes two to four minutes because every record
is processed by a model. Afterwards it is instant.

**Re-seed**
To wipe the banks and load them again. Needed after changing the corpus, via
`/api/setup?force=true`. Without it, old memories linger and corrupt the measurement.

**Corpus**
The dataset. In this project it is a fictional company, its services, its people and its incidents.
The failures are real, lifted from actual postmortems.

**Ground truth / answer key**
A human-written list of which incidents genuinely share a root cause, used to score retrieval. In
`app/analysis.py`. Half the original entries were wrong and were removed.

**Recall (the measurement)**
Not the Hindsight operation. In [THE_NUMBERS.md](THE_NUMBERS.md) it means "how many of the
correctly-identified related incidents did the system find", as a percentage. Confusingly the word
is used both for the Hindsight search call and for the score. When it matters, the text says which.

**Fingerprint match**
The confidence the model reports, 0 to 100, that an alert matches a known failure mode. A
self-assessment, not a measurement. The number to trust is the 83% retrieval figure.

---

## Interface and design

**Design tokens**
The named values a design is built from: colours, type sizes, spacing. Defined at the top of
`web/base.css` and justified in `DESIGN.md`.

**The ruled gutter**
The repeated layout motif: a narrow left column carrying metadata, separated from the body by a
single hairline. Used in every screen, table and section.

**Hairline**
A one-pixel rule. Used instead of shadows to show structure, because a document has rules rather
than drop shadows.

**WCAG AA**
The accessibility standard for colour contrast: 4.5 to 1 for normal text, 3 to 1 for large text and
for meaningful non-text elements like borders. Every colour in this project was checked against it,
and the values in `DESIGN.md` are the corrected ones.

**Progressive disclosure**
Showing the detail only when someone asks for it. The console shows a match percentage first and
the full reasoning underneath.

---

## The three complaints to expect

**"Isn't this just RAG?"**
No. Covered properly in [WHAT_IS_THIS.md](WHAT_IS_THIS.md), and the one-line version is that
retrieval returns documents while this returns a conclusion that appears in none of them, plus a
link between two separate memory stores.

**"The match percentage is just the model grading itself."**
Correct, and the project says so. The real measurement is 83% against a hand-written key, and it
reports its own failure. See [THE_NUMBERS.md](THE_NUMBERS.md).

**"The data was built to make this work."**
Yes, deliberately, and the corpus tab is there to prove it. The interesting structure had to be
constructed; the individual failures are all real. See [DATA.md](DATA.md).
