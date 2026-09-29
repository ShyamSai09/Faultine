# Decisions

Every non-obvious choice in this project, with the alternative that was rejected and what it would
have cost. Numbered so they can be referenced and reversed individually.

Status is one of: **Accepted**, **Reversed**, **Revisit**.

---

## D1. Two memory banks, not one

**Accepted**

**Context.** Faultline needs to join an incident to the to-do item it produced, and to notice when
the same to-do item appears after a different incident three months later. It also needs "which
services are still exposed", which comes from infrastructure state, not incidents.

**Decision.** `faultline-incidents` for the technical corpus, `faultline-team` for ownership and
commitments. Strict isolation between them, as Hindsight provides.

**Rejected.** One bank with everything. Simpler, and metadata filtering would have been good enough
for most queries.

**Consequence.** The cross-bank join works and is the reason the "promised 2x" badge can exist. The
cost is that cross-bank reasoning needs two stores kept coherent, and the team bank has to be
populated deliberately at seed time, which is easy to forget when adding data.

**How to reverse.** Merge into one bank and filter by `metadata.kind`. You lose the join.

---

## D2. The empty control bank, instead of a weaker prompt

**Accepted**

**Context.** Demonstrating that memory helps is the whole project. The obvious demonstration is a
good prompt versus a deliberately bad one, which proves nothing, because the obvious objection is
that the bad one was rigged.

**Decision.** A third bank, `faultline-control-empty`, created once and never written to. The
no-memory run uses the **identical** query, model, directives and retrieval stack.

**Rejected.** Writing a separate "stateless agent" prompt, which would be easier to read and much
weaker evidence.

**Consequence.** The comparison cannot be accused of rigging, and it produced a better result than
expected: the no-memory run *still* correctly identifies an identity permission problem from the
error text. The finding is that the model is not the weak link, which is more interesting and more
honest than "the model was useless".

**Cost.** One extra bank and a slightly odd piece of infrastructure whose only purpose is to be
empty. It needs a comment, which it has.

---

## D3. Deterministic output, not a JSON schema

**Accepted**

**Context.** `reflect` accepts a `response_schema`. Passing one and getting prose back breaks the
UI.

**Decision.** Pass the schema anyway, *and* carry a plain-text format contract in the prompt, with
a deterministic parser in `_parse_triage`.

**Rejected.** Relying on the schema alone, which does not work on Hindsight Cloud. Relying on prose
alone, which is fragile and unrenderable.

**Consequence.** Works today and degrades gracefully. The cost is two coupled pieces with nothing
tying them together, so changing the contract without the parser fails **silently**. That is the
most dangerous property in the codebase and is why it is first on the test list in
[ROADMAP.md](ROADMAP.md).

**Revisit when.** Hindsight Cloud starts honouring `response_schema`. Re-test each release. If it
works, delete the prompt contract and the parser.

---

## D4. One dedicated thread for all memory access

**Accepted**

**Context.** Hindsight's Python client is synchronous and wraps an async client. It calls
`asyncio.get_event_loop().run_until_complete(...)`, and its aiohttp pool is bound to the first loop
that used it. Called from a second thread it raises
`Timeout context manager should be used inside a task`. `asyncio.to_thread` makes it worse,
because anyio attaches the parent running loop to its worker threads.

**Decision.** `_LoopThread` in `app/memory.py`: a queue, one worker thread, one private event loop
that is never `run_forever`. Every memory call serialises onto it, through `run_blocking` for
threads and `memory.call` for async routes.

**Rejected.** `asyncio.to_thread`, which appeared reasonable and failed in a more confusing way.
`asyncio.run_coroutine_threadsafe`, which would mean rewriting the client usage against its async
API throughout.

**Consequence.** Correct, and the error mode is gone. Three costs: it depends on an implementation
detail of the client, so a fix upstream makes it dead weight; all calls serialise, so concurrent
triages queue; and there is one obvious way to do this, so the rule is easy to break by accident.

**How to reverse.** When the client stops mishandling loops, delete `_LoopThread` and call the
client directly. The fix is isolated in one class.

---

## D5. Let the model judge, the code keep records

**Accepted**

**Context.** Asked which services were still exposed, the model listed whichever services appeared
in the incidents it had just cited, including two patched by hand. Its reasoning was defensible:
those services share a Terraform module that still has the unsafe default, so all are technically
at risk. It was also the wrong answer, and sending on-call after a fixed service costs minutes
while customers are affected.

**Decision.** The model returns one token, `STATE: iam_role_trust_policy`, and the code builds the
exposed list from the latent-state record, using the model's prose as the explanation. The
"promised Nx" counts are counted in code too.

**Rejected.** Prompt engineering until the model stopped doing it. Three attempts, and each time it
produced a different plausible answer. Also rejected: dropping the feature, since "what else is
broken this way" is the most valuable thing on the screen.

**Consequence.** The exposed list is a fact, not an inference, and it is honest about provenance
because the evidence line says which state record it came from and when it was last audited. The
cost is that the model no longer discovers exposure, it names it, and the code supplies the list.
That is a real limitation and it is stated in [ARCHITECTURE.md](ARCHITECTURE.md).

**The generalisable lesson.** Any agent that mixes inferred reasoning with recorded state needs this
split. The model is good at judgement and bad at bookkeeping; conflating them produces answers that
are defensible and wrong.

---

## D6. The answer key was cut, and the score went down

**Accepted**

**Context.** The first measurement scored 55%. Half the misses turned out to be my own labelling
errors: three clusters grouped incidents sharing a theme but not a root cause. A feature flag ramped
to 100% and a forward-only migration left by a rollback are different faults. An OOM in a backfill
and a bad record failing a batch job are different faults. A silent data loss and a log volume
outage are different faults.

**Decision.** Cut the key from ten clusters to seven, keeping only pairs that genuinely share a
cause. Reported 83% rather than 55%, and made the correction visible in the UI caption.

**Rejected.** Keeping the generous key and reporting 55%, which is honest about the number and
dishonest about the labels. Also rejected: tuning the queries until the score looked better, which
would have made the measurement meaningless.

**Consequence.** The number is defensible and the misses are real. The lesson is written into the
UI so nobody reads 83% as "the system is right 83% of the time".

**Note.** The score rose because the key got stricter, which is the opposite of what a vanity
metric wants. A measurement that improves when you make the test harder is worth something.

---

## D7. The exposed list is grounded, not discovered

**Accepted**

**Context.** See [D5](#d5-let-the-model-judge-the-code-keep-records). There is a second, larger
question hiding underneath.

**Decision.** The exposed-services list comes from a static corpus record of each service's current
configuration state. It is a file read.

**Rejected.** A real integration that queries infrastructure. Out of scope for the time available,
and any half-working version would have been dishonest in a demo.

**Consequence.** The demonstration is sound and the claim is bounded: Faultline reads state, it does
not discover it. This is the gap between the demonstration and the product, and it is the top item
on the roadmap. It is stated on the landing page under "what this is not".

---

## D8. Two fonts, and a rule for which is which

**Accepted**

**Context.** The first build used Inter and JetBrains Mono, the two typefaces a model reaches for
by default, chosen for no reason. The second is a developer tool, so a monospace face felt
appropriate, but a postmortem is a document.

**Decision.** Newsreader, a transitional serif, for anything a person wrote. IBM Plex Mono, drawn by
IBM for technical documentation, for anything a machine wrote. Enforced in the markup: agent prose is
serif, the alert and logs are mono.

**Rejected.** A single family in two weights, which loses the boundary. All mono, which loses the
documents. A third accent face, which is decoration.

**Consequence.** The interface says what it is before you read a word, and the typographic split
*is* the product's thesis rendered as a font decision rather than a comment. Cost: two web fonts
instead of one.

---

## D9. The console is a document, not a dashboard

**Accepted**

**Context.** Dark, glow and a background grid were the default first answer for an ops tool, and the
product argues that reading matters more than alerting. Dark also has a real argument: an on-call
console is used at 3am.

**Decision.** Warm off-white, warm near-black, a ruled gutter carrying ids and dates, and log output
on a sunken surface because it is evidence cut from somewhere else. One accent colour, and it means
exactly one thing: this finding is still open.

**Rejected.** Dark. A gradient. Green for resolved states. Cards with icons. A bento grid.

**Consequence.** Better contrast for free, which fixed an AA failure across four surfaces, and the
design is far from the developer-tool default. The cost is real: paper at 3am is a legitimate
complaint that this design does not solve, and the deepest grief in the first audit was R-21, which
exists to stop exactly this kind of unargued default. The reason is written down in `DESIGN.md` and
the decision is marked revisitable.

**Revisit when.** Anyone uses it at night and says it is wrong. That is the test.

---

## D10. Facts about the system, and no numbers that are not measured

**Accepted**

**Context.** The brief asked for real data and a demonstrable story. Landing pages for AI projects
usually carry invented figures: user counts, uptime claims, testimonials from nobody.

**Decision.** Every figure on the landing page is measured on this corpus and labelled with its
provenance. The 83% is scored against a hand-written key. The one miss is shown. The
no-memory comparison is a control bank, not a weak prompt. There is no testimonials section, no user
count, no compliance badge, and no comparison against tools I have not benchmarked.

**Rejected.** Softening the copy. Omitting the 100% match, which is the model's self-assessment and
the least rigorous number on the page, on the grounds that it is less impressive. Omitting the
single miss, which would have produced a clean table.

**Consequence.** The landing page has fewer numbers than a competitor's and each one survives being
asked about. The 100% match stays, with a caption pointing at the measured figure, because removing
it would be hiding information rather than correcting it.

---

## D11. `retain` original timestamps, and an explicit extraction mission

**Accepted**

**Context.** Two easy mistakes, neither of which errors, both of which quietly halve the product.

**Decision.** Pass each incident's real `opened` time, not the ingestion time. And pass a
`retain_mission` that asks for services, dates, symptoms, cause, runbook, impact, and each action
with its owner and status, and asks for incident ids to be kept as entities.

**Rejected.** The default behaviour, which stamps ingestion time and writes prose.

**Consequence.** Temporal recall is one of four arms and works, so the agent can say "March and
June", which is what turns two coincidences into a pattern. Incident ids stay joinable, so the
cross-bank link works. Both are invisible when broken, which is why they are called out here.

---

## D12. No test suite, and saying so

**Accepted, reluctantly**

**Context.** There is no test suite. The deadline was 29 September and the time went into a working
system, real data, a real measurement and documentation.

**Decision.** Ship without, document the gap, and name the three functions that should be tested
first: `_parse_triage`, because the prompt contract and the parser are coupled with nothing tying
them together, so a change to one fails silently; `_exposure_from_corpus`, because it is the
correctness guard for the grounding step; and `analysis.measure`, because the reported number depends
on it.

**Rejected.** Writing tests first. Writing them at the end. Pretending there are tests.

**Consequence.** A reviewer has to read the code to trust the parser, and a refactor of the output
contract is genuinely dangerous. This is the largest gap in the project and it is the first item on
the roadmap. Recording the decision is better than leaving a silent hole.

---

## D13. Original code, researched patterns

**Accepted**

**Context.** The instruction was to reuse existing solutions from GitHub.

**Decision.** Researched the landscape, and built original. The research mattered:
`vectorize-io/self-driving-agents` already ships SRE and incident-response agent templates, so the
differentiation was pushed to a capability those templates do not have, which is predicting
recurrence in a service that has not failed yet. `hindsight-pi`, `hindsight-lite` and
`hermes-memory-*` are MIT and were read for architecture, notably the mental-model bank template
pattern and the per-entity bank id scheme.

**Rejected.** Wholesale copying. `self-driving-agents` carries an MIT badge but has **no LICENSE
file**, so its status is legally ambiguous and it is reference-only. Vendoring an MIT project to
save a day would have made the submission about the vendored project rather than this one.

**Consequence.** Everything is original and licence-clean, and the submission is defensible on its
own terms. The cost is that a day of work that copying would have avoided went into the corpus, the
measurement and the docs, which is where the judging value actually is.
