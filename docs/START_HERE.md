# Start here

If you have never seen this project before, read this page and nothing else. Ten minutes.

---

## The one-sentence version

Faultline is a fake company with a real problem. It is an AI agent that reads past outage reports
so it can tell an on-call engineer "you have been here before, here is what fixed it, and by the
way two other services are still broken in the same way and nobody knows yet."

## The story, with no jargon

A company has a bug that breaks one service. They fix it. In the write-up of the fix, somebody
writes down: "also check the other services for this same bug."

Nobody does that.

Months later, a completely different service breaks. Different-looking bug, same actual cause.
Nobody connects them, because connecting them means reading two old write-ups side by side and
having someone remember to do it.

Then a third service breaks. Same cause again.

Faultline is software that always does the connecting, because it never forgets.

## Why you cannot just use a normal search box

This is the part people get wrong, so here it is carefully.

If you put a normal search engine on top of your old outage write-ups, you can find the March
write-up. It mentions similar words. That is genuinely useful.

But the three things Faultline produces, a search box cannot produce:

1. **"Two other services are still broken the same way."** To say this, the system must notice that
   four separate documents, written about four different services, are all describing one shared
   underlying problem. Search finds documents that look alike. It does not form beliefs.

2. **"That fix was written down twice and never done."** To say this, the system must link an
   incident record to a to-do item, and then notice that the same to-do item was also created after
   a different incident three months earlier. That is a link between two things in two different
   places, not a similarity.

3. **"This will probably break again here."** To say this, the system must remember that a service
   has the same broken setting today that broke a different service last year, which it only knows
   because the to-do item that would have cleaned it up was left open.

If you only remember one thing from this project, remember that. It is not a prettier search. It is
a different kind of memory.

## What is Hindsight

Hindsight is the memory system this project is built on. Think of it as the filing cabinet. You
hand it raw information (an outage report, an alert), and over time it:

- pulls out the individual facts ("this broke on 14 March", "the owner was Jonas", "the fix was
  runbook RB-07")
- groups those facts into **observations**, which are beliefs it has formed, with evidence attached
- links the facts together into a graph, so "this service" and "this setting" and "this incident"
  become connected things
- keeps **mental models**, which are written answers to standing questions, rewritten in the
  background as new information arrives

Faultline uses all four. That is why it can do things a search box cannot.

There is a longer explanation in [HINDSIGHT_PLAIN.md](HINDSIGHT_PLAIN.md) if you want the details
without the jargon.

## How to see it work

You need the app running. See [RUNNING_IT.md](RUNNING_IT.md) if you get stuck, it is written for
someone who has never opened a terminal.

Once it is running, open the console and press the one button that says "Triage alert". Then
watch three things happen:

1. A big percentage appears. It is usually 100%. That means "we recognise this, we have seen it".
2. A list of old incidents appears. Those are real outages from months ago that share the cause.
3. A red section appears saying other services are still exposed, plus a list of fixes that were
   promised and never completed. **That last part is the whole point of the project.**

Then flip the "Memory" switch off and press the button again. Same alert, same AI model, but with
no memory. You will get `MATCH: 0`, `INCIDENTS: none`, `RUNBOOK: none`. That contrast is the
argument, and it is honest because both runs go through exactly the same system.

## Is the data real?

No, and this matters. The company (Northwind Commerce), the services, the engineers and all
nineteen outages are **invented**.

But the failures are real. Every one of them is lifted from something that actually happened at a
real company: a database that filled up and took out the alerts you needed to debug it, a feature
flag accidentally rolled out to everyone at once, a certificate that expired on a Saturday.

The reason to invent the data rather than scrape real incidents is that the *interesting* part is
the pattern across many incidents and many months, and that has to be constructed on purpose. See
[DATA.md](DATA.md).

## Where to go next

| You want to | Read |
| --- | --- |
| Understand the problem properly | [WHAT_IS_THIS.md](WHAT_IS_THIS.md) |
| Understand how the agent actually works | [HOW_IT_WORKS.md](HOW_IT_WORKS.md) |
| Know what every single file is for | [FOLDER_MAP.md](FOLDER_MAP.md) |
| Get it running | [RUNNING_IT.md](RUNNING_IT.md) |
| Know what each screen is showing | [SCREENS.md](SCREENS.md) |
| Understand the numbers | [THE_NUMBERS.md](THE_NUMBERS.md) |
| Understand the Hindsight design choices | [HINDSIGHT_PLAIN.md](HINDSIGHT_PLAIN.md) |
| Call it from your own code | [API.md](API.md) |
| Fix an error | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| Look up a word | [GLOSSARY.md](GLOSSARY.md) |
| Demo it to someone | [DEMO_SCRIPT.md](DEMO_SCRIPT.md) |
