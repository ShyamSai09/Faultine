# Documentation index

Written to be read in order if you are new, and dipped into if you are not.

---

## Start here

**If you only read one file in this repository, read [../BRIEF.md](../BRIEF.md).** The whole
project in plain English, no jargon: the problem, what we built, why it is not a search box, how
we know it works, and what is still to be done.

Then, if you want more:

1. **[START_HERE.md](START_HERE.md)** - ten minutes, no jargon, and the only page you need if you
   just want to know what this is
2. **[WHAT_IS_THIS.md](WHAT_IS_THIS.md)** - the problem, in plain words, including why a search box
   cannot solve it
3. **[HOW_IT_WORKS.md](HOW_IT_WORKS.md)** - every step of the mechanism, naming the Hindsight
   feature that does each one
4. **[RUNNING_IT.md](RUNNING_IT.md)** - get it running, written for someone who has never opened a
   terminal

## If you want to use it

| You want to | Read |
| --- | --- |
| Use it during an incident | **[USER_GUIDE.md](USER_GUIDE.md)** - what every field on the answer means, and the first five minutes |
| Know what every screen shows | [SCREENS.md](SCREENS.md) |
| Put your own incident data in it | [DATA.md](DATA.md) |
| Call it from your own code | [API.md](API.md) |
| Fix an error | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| Look up a word | [GLOSSARY.md](GLOSSARY.md) |
| Demo it to someone | [DEMO_SCRIPT.md](DEMO_SCRIPT.md) |

## If you want to change it

| You want to | Read |
| --- | --- |
| Change the code safely | **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - the two rules that will bite you, and the module boundaries |
| Understand the system design | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Know why a choice was made | [DECISIONS.md](DECISIONS.md) - 13 decisions, each with the alternative and what it would have cost |
| Know what every file is | [FOLDER_MAP.md](FOLDER_MAP.md) |
| Know what happens next | [ROADMAP.md](ROADMAP.md) - including what I would not do, and why |
| Contribute | [../CONTRIBUTING.md](../CONTRIBUTING.md) |
| Know what changed, and when | [../CHANGELOG.md](../CHANGELOG.md) |

## If you want to check a claim

| You want to | Read |
| --- | --- |
| Check whether a number is real | [THE_NUMBERS.md](THE_NUMBERS.md) - the provenance of every figure, including which ones are not measurements |
| Answer "is the data just hardcoded?" | [VALIDATION.md](VALIDATION.md) - the holdout experiment, what it measured, and what it could not settle |
| Check the memory design choices | [WHY_HINDSIGHT.md](WHY_HINDSIGHT.md) and [HINDSIGHT_PLAIN.md](HINDSIGHT_PLAIN.md) |
| Check the interface rules | [../DESIGN.md](../DESIGN.md) and [../anti-slop/audit-001-2026-09-28.md](../anti-slop/audit-001-2026-09-28.md) |
| Check the security posture | [../SECURITY.md](../SECURITY.md) |

---

## Not documentation

| File | What |
| --- | --- |
| `../README.md` | Repository front door |
| `../DESIGN.md` | Why the site looks the way it does, with a reason for every decision |
| `../CHANGELOG.md` | What changed, when, and why |
| `../SECURITY.md` | Key handling and what the app does not have |
| `../CONTRIBUTING.md` | Conventions and the two rules that will bite you |
| `../article.md` | The long-form write-up, for publication |
| `../linkedin.txt` | Social post, long form |
| `../linkedin-short.txt` | Social post, under 800 characters |
| `img/` | Screenshots used across the docs |
| `../web/img/` | The live screenshots used on the landing page |

---

## If you only read one thing

> An alert fires on a service with no deploy in thirty days. The agent links it to two outages from
> March and June that share a root cause, names the runbook that fixed both, flags two other
> services still carrying the same broken configuration, and points at the postmortem action that
> would have prevented all three, written twice and closed never. Turn its memory off and it gets
> every one of those wrong.

That is the entire project, and the last sentence is the part that matters: the contrast is real,
not staged, because both runs go through the same system and differ only in whether memory exists.
