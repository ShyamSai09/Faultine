# Changelog

All notable changes to Faultline. Dates are 2026, the day the change was made.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/): grouped by change type,
with the reason given where the reason is not obvious from the diff.

---

## 2026-09-28

Project created and shipped in one day, against a 29 September submission deadline.

### Added: the memory layer

- **Two Hindsight banks.** `faultline-incidents` holds 19 incident records plus 4 latent
  infrastructure state records. `faultline-team` holds the 19 postmortem actions that were never
  completed. The split exists to make one specific cross-bank join possible, documented in
  [ARCHITECTURE.md](docs/ARCHITECTURE.md).
- **A third bank, `faultline-control-empty`**, created once and never written to. It is the control
  for the before-and-after comparison: the identical query, the identical model, the identical
  four-way retrieval, zero memories. Included because comparing a good prompt to a weak one proves
  nothing.
- **Four directives** shaping `reflect`: `no-invention` at priority 20, plus `cite-evidence`,
  `prefer-recent` and `surface-unclosed-work`. The last one is why the agent reports unclosed
  remediation at all.
- **Three mental models** with `trigger={"mode": "delta", "refresh_after_consolidation": true}`:
  `failure-fingerprints`, `recurrence-risk`, `open-remediation`. Reading one is a database read
  rather than a model call, which is what makes them affordable on every request.
- **`retain` passes original incident timestamps.** A deliberate decision: temporal retrieval is one
  of four recall arms and is only correct if the stored times are historical rather than ingestion
  times.
- **`retain` passes an explicit `retain_mission`** asking the extractor to keep incident ids as
  entities. Without it the extractor writes prose, ids stop being joinable, and the cross-bank link
  fails silently with no error.

### Added: the agent

- **`triage()`** in `app/memory.py`: recall, then reflect, then read the mental models, then
  ground. About four seconds warm.
- **A deterministic grounding step.** The model reports which latent condition matches; the code
  builds the list of exposed services from the recorded state and uses the model's prose as the
  explanation. See [DECISIONS.md D6](docs/DECISIONS.md).
- **A no-memory baseline** running the identical query against the empty control bank.
- **A close-the-loop endpoint.** `POST /api/resolve` retains the outcome and refreshes the
  fingerprints. Pressing it makes the next triage sharper and usually surfaces a new action derived
  from what the incident exposed.

### Added: the dataset

- **Ten services, nineteen incidents, nineteen unclosed actions, four latent conditions.** The
  spine is one underlying mistake causing three incidents across five months and three services,
  with the sweep that would have prevented it written twice and closed never. Constructed on
  purpose so the cross-month, cross-service join is required rather than optional.
- **Every failure mode is real**, lifted from an actual postmortem, including a log volume outage
  that silently disabled the alerting pipeline needed to diagnose it. The company, services and
  people are invented.
- **`app/analysis.py`**, scoring recall against a hand-written answer key of seven clusters. This
  is the only figure in the project produced by scoring against known truth rather than asking the
  system to rate itself.

### Added: the interface

- **A three-column console** at `/console`: the alert, the answer, the memory. Four tabs, Console,
  Learning curve, Memory, Corpus.
- **A landing page** at `/`, built on four pieces of evidence rather than adjectives: the verbatim
  alert, the two runs side by side, real screenshots, the measurement with its miss.
- **Designed empty, loading and error states** on the answer panel. The previous error was a toast
  that vanished after five seconds, which is the worst possible behaviour during an outage.
- **`?autotriage=1`** runs the demo without a click, for projecting and for screenshots.
- **Real tab semantics.** `role="tablist"`, `aria-selected`, arrow-key navigation, and one global
  focus-visible rule covering every focusable element.

### Added: documentation

- **Twenty documentation files.** `START_HERE` for newcomers with no jargon, `WHAT_IS_THIS` for the
  problem, `HOW_IT_WORKS` for the mechanism, `ARCHITECTURE` and `DEVELOPER_GUIDE` for the code,
  `USER_GUIDE` for using it, `FOLDER_MAP` file by file, `RUNNING_IT` written for someone who has
  never opened a terminal, `SCREENS` screen by screen, `THE_NUMBERS` with the provenance of every
  figure, `DATA` on the dataset, `HINDSIGHT_PLAIN` and `WHY_HINDSIGHT` on the memory design,
  `API`, `TROUBLESHOOTING`, `GLOSSARY`, `DECISIONS`, `ROADMAP` and `DEMO_SCRIPT`.
- **Documentation served at `/guide`**, so the links on the landing page resolve. `/docs` remains
  FastAPI's generated API reference.
- **`DESIGN.md`**, with a one-line reason for every colour, typeface and layout decision, the three
  dials, the rejected alternatives, and the author's own caveat that an agent-chosen aesthetic
  skews toward the default taste the anti-slop rules exist to filter.
- **`SECURITY.md`**, documenting key handling.
- **`anti-slop/audit-001-2026-09-28.md`**: 16 findings against 38 rules, all closed, each with its
  evidence.

### Changed: the interface was rebuilt

The first build was the default answer for a developer tool and did not survive the audit. Full
findings in `anti-slop/audit-001-2026-09-28.md`; the substance:

- **Direction chosen:** the console is a postmortem being written while the incident is still
  happening. That gave the layout its structure: a ruled gutter carrying ids, dates and owners, and
  log output on a sunken surface because it is evidence cut from somewhere else.
- **Fonts:** Inter and JetBrains Mono replaced with Newsreader and IBM Plex Mono, with a division of
  labour enforced in the markup rather than suggested in a comment. If it is set in mono, a machine
  wrote it. That typographic split is the product's thesis rendered as a font decision.
- **Palette rebuilt from contrast ratios backwards.** The previous second-most-used colour measured
  3.18 to 3.69:1 across four surfaces, all failing AA. Fifteen pairings now pass, worst case 5.38:1.
- **Removed:** background grid, three glows, capsule badges, a red left stripe on every card, five
  accent colours, and all fifteen em dashes. Zero gradients, shadows and glass remain.
- **Dark to paper.** Dark has a real argument for a 3am on-call console. It lost because the product
  argues that reading matters more than alerting, and paper wins on contrast. Recorded as a
  revisitable trade, not a settled call.

### Fixed

- **Hindsight's sync client binds its connection pool to the first event loop that uses it.**
  Calling it from a second thread raised `Timeout context manager should be used inside a task`,
  which sounds nothing like what it was. `asyncio.to_thread` made it worse, because anyio attaches
  the parent running loop to its worker threads. Fixed with `_LoopThread`: a queue, one worker
  thread, one private never-running loop, and every memory call serialised onto it.
- **`reflect` rejects queries over 500 tokens.** The alert plus the output contract initially came
  to 618 and was rejected with an opaque error. The contract was compressed to about 450 tokens, and
  `HINDSIGHT_PLAIN.md` documents the ceiling, the token-density estimate, and the untested fix of
  moving the contract into `reflect`'s `context` parameter.
- **`response_schema` is accepted by `reflect` and ignored by Hindsight Cloud**, which returns prose
  regardless. Verified with a minimal schema at three budget levels. The schema is still passed,
  because it works elsewhere; the contract that actually holds is a format spec in the prompt plus
  a deterministic parser that degrades to partial output rather than raising.
- **Setup was not idempotent**, so a second run failed with a 409 on an existing mental model, and
  memory re-seeding would have duplicated the corpus. Banks are now created or updated depending on
  existence, mental-model conflicts are swallowed on purpose (re-creating one would discard a
  version that has learned something), and seeding is skipped when memories already exist.
- **The answer key was wrong.** Three clusters grouped incidents sharing a theme but not a root
  cause. Cutting them moved the reported score from 55% to 83% with no change to the system. The
  honest number is lower and the miss is shown in the UI.
- **The learning-curve heading contradicted its own chart.** Titled "the memory gets better,
  measurably" above a curve that visibly dips. Retitled to what it measures, with the dip and the
  answer-key correction written into the caption.
- **A latent-state record was missing a field** the renderer assumed, breaking seeding at 18 of 19
  incidents. The renderer is now tolerant of missing fields rather than assuming them.

### Known issues

Recorded rather than hidden. Full list in [ROADMAP.md](docs/ROADMAP.md).

- No test suite. The largest gap. The structure makes `_parse_triage`, `_exposure_from_corpus` and
  `analysis.measure` easy to test, and none are tested.
- The exposed-services list is read from static corpus state, not discovered. Deterministic and
  honest, but it is a file read rather than an infrastructure query.
- All Hindsight calls are serialised, which is the price of the threading correctness. A triage
  concurrency limit is absent, so many simultaneous users would queue.
- Cold seeding takes 2 to 4 minutes because 24 retains run serially. `retain_batch` would fix it
  and is unimplemented.
- The answer key is hand-maintained, which is the weakest link in the measurement. Deriving it from
  the consolidated observations would be better and circular.
- No authentication, no multi-tenancy, no audit trail.

### Notes on process

Two things I got wrong and recorded rather than quietly corrected:

- **Mobile was reported as a hard failure and it was not.** Headless Chrome enforces a minimum
  window width, so a 390px screenshot was a crop of a wider render. Re-tested in a true 390px
  viewport: zero overflowing elements. The one real defect, tabs wrapping to a second row, was
  fixed.
- **A security check was broken and raised a false alarm.** `git grep ... | head` returns head's
  exit status, so the conditional always passed. Re-run correctly: the API key is in no commit and
  exists only in the gitignored `.env`.
