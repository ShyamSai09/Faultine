# Demo script — 3 minutes, 40 seconds

Target length 2–5 minutes. Read the narration, don't memorise it. Every screen
cue is a real URL and a real click.

Set up before you record:

```bash
cd ~/Desktop/hacakthons/faultline
./run.sh            # http://localhost:8000
```

Open `http://localhost:8000/?autotriage=1` in one window (it triages on load) and
`http://localhost:8000` in another (for the memory-off toggle). Bump the browser
zoom to 125% and the terminal font to 18px so the alert text is readable on a
projector. Close Slack.

---

## 0:00 — The hook (0:00–0:25)

> "This is a SEV2 alert. It fired on a service called `payout-worker` this
> morning, and the on-call engineer has never seen it before.
>
> Except they have. Twice. And both times, the postmortem said we'd fix it."

**Screen:** the console, alert on the left, empty response in the middle. Don't
click yet — let the emptiness sit for a beat.

---

## 0:25 — The problem (0:25–0:55)

> "To be clear about what a normal assistant does here: it reads the error,
> guesses it looks like an IAM problem, and tells you to go look at your trust
> policy. That's a reasonable answer. It's also the same answer it would give if
> this were the first IAM problem this company ever had."

**Screen:** point at the alert. Call out the two lines that matter:

- `last_deploy: 2026-08-29 (30 days ago)` — nothing shipped
- `last successful assumeRole=2026-09-17 (11 days ago)`

> "No deploy in thirty days, and no successful credential use in eleven. So this
> isn't new. Something's been broken behind a cached token and nobody noticed."

---

## 0:55 — The demo, part one (0:55–1:40)

Click **Triage alert**.

> "Nineteen incidents, ten services, eighteen months. That's all in memory
> before this alert even arrives."

**Screen:** the response pane fills. Point at the gauge.

> "Hundred percent match. It named the failure mode — IAM authorisation denials
> from a wildcard trust policy — and it cited two prior incidents:
> INC-1042, `payments-api`, March fourteenth. And INC-1188, `checkout-web`, June
> second. Different services, different symptoms — one was returning 503s, one
> was rejecting checkouts with 401s — same root cause, three months apart.
>
> And it gave me the runbook. RB-07. That's the one that worked both times."

**Screen:** right pane. Scroll the recalled memories.

> "On the right, those green `OBSERVATION` labels. That's not a search result. The
> bank consolidated four separate documents into a belief: *these three services
> are currently carrying the insecure trust policy.* It wrote that itself, and
> it rewrites it whenever the evidence changes."

---

## 1:40 — The demo, part two, the payoff (1:40–2:25)

Scroll to **STILL EXPOSED ELSEWHERE**.

> "Here's the part I actually care about. Two other services are carrying the
> same broken trust policy right now and have not gone down yet —
> `inventory-sync` and `webhooks-relay`. Nobody gets paged for those. They just
> wait for their turn."

Scroll to **REMEDIATION THAT WAS NEVER COMPLETED**.

> "And this. 'Conduct a fleet-wide sweep for wildcard trust policies.' Written
> 2×. It was written after the March incident, and again after the June one.
> Nobody closed it. That bullet point in a postmortem is the entire reason we're
> having this conversation at eleven in the morning on a Tuesday."

> "The agent didn't find that because it's similar to the alert. It found it
> because the March incident is *linked* to an action item that was never
> closed."

---

## 2:25 — The before/after (2:25–2:55)

Toggle **Memory** off. Triage again.

> "Same model. Same query. Zero memories."

**Screen:** the baseline panel. Land on the fields.

> "Match: zero. Incidents: none. Runbook: none. Open remediation: none.
>
> And notice it still guessed IAM correctly — from the error string alone. The
> model isn't the problem. The missing memory is."

Toggle memory back on.

---

## 2:55 — The proof, and the close (2:55–3:30)

Click **Learning curve**.

> "I didn't want to just assert that memory helps, so I scored it. Nineteen
> incidents, hand-labelled into clusters of shared root cause. For each one, ask
> Hindsight to recall the failure mode and check which true siblings come back.
> No LLM calls — it's just retrieval."

> "Eighty-three percent. Five of six. And one genuine miss, which I'm showing
> because it should be: a thread pool starved by an HTTP call with no timeout,
> and a webhook relay that burned its quota retrying 429s with no backoff. Same
> anti-pattern, almost no shared vocabulary. That's the real shape of retrieval."

Back to the console. Click **Record resolution**.

> "When this one's closed, retaining the outcome is what makes the fingerprint
> stronger. Next time this alert fires, the match is sharper.
>
> Faultline is an on-call agent that remembers every outage your company has
> ever had — and, more usefully, tells you which one is about to happen again."

---

## The 20-second version, if you get cut off

> "An alert fires with no deploy in thirty days. The agent matches it to two
> prior incidents from a shared root cause, names the runbook, flags two other
> services still carrying the same broken config, and points at the postmortem
> action that would have prevented all three — written twice, closed never. Turn
> the memory off and it gets all of it wrong."

---

## If a judge asks

**"Isn't this just RAG over your postmortems?"**
No. Retrieval finds documents that look similar. The claim that
`inventory-sync` is exposed comes from a consolidated observation formed across
four documents describing four different services, joined by the entity graph
and a condition record. And the "written 2×" count comes from linking an
incident to action items in a *different* bank. Neither is a similarity search.

**"How do you know it's actually learning?"**
`app/analysis.py`. A hand-written answer key, 83% recovery, one miss shown
publicly. I also cut the key from ten clusters to seven when I realised three
pairs shared a theme but not a root cause — the number was flattering because
the key was wrong.

**"What if the model makes something up?"**
It did, and I stopped trusting it. Asked which services were exposed, it named
ones an engineer had already patched, because they appeared in the incidents it
had just cited. So the model now only says *which* condition matches, and the
code builds the list from the recorded state. There's a `no-invention` directive
and a priority-20 one telling it to admit ignorance rather than guess.

**"What's this worth?"**
Nineteen incidents, nineteen remediation actions never completed. Three of them
are the same action written for the third time. Every one of those is a future
outage someone already paid for once.
