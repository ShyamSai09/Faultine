# Faultline — plain English brief

For someone who has never heard of this project and does not want to read any code.
Everything below is explained without jargon.

---

## The problem

A company runs a lot of software. When something breaks, someone gets woken up and has to fix it.

After they fix it, they write a report. In that report they usually write something like:

> "Also check the other 9 services for this same problem, so it never happens again."

That line is almost never done. There is no system that reminds anybody.

So three months later, a different service breaks in exactly the same way. The person on call
does not connect them, because connecting them means reading two old reports next to each other
and having somebody remember to.

Then it happens a third time.

**Meanwhile, other services are already broken the same way. Nobody knows, because they have not
broken yet. Nobody gets woken up for them. They are just waiting their turn.**

That is the whole problem. The information exists. Nobody joins it up.

---

## What we built

A program that never forgets. It reads all the old incident reports and holds on to them
permanently.

When a new alert comes in, before a human has finished reading it, the program answers five
questions:

1. **Have we seen this before?**
   Yes. We call it "IAM authorization failures."

2. **Which past incidents had the same cause?**
   One in March, one in June. Different services, different symptoms, same actual bug.

3. **What fixed it last time?**
   Runbook RB-07. A written procedure somebody already wrote down.

4. **What else is still broken this way?**
   Two other services have the exact same broken setting right now. They have never gone down, so
   nobody was told.

5. **Did we ever say we would fix it?**
   Yes. Somebody wrote "sweep all services" in March, wrote it again in June, and never did it
   either time.

**Question 4 is the entire point.** Those two services are fine today and broken tomorrow, and this
is the only way you find out while there is still time to act.

---

## What you see when you press the button

The alert sits on the left. The middle of the screen fills in about 4 seconds:

```
100% MATCH
Have we seen this before: yes, IAM authorization failures

BEFORE:  INC-1042   payments-api    14 March   503 errors for 41 minutes
         INC-1188   checkout-web     2 June     401 errors for 44 minutes

CAUSE:   Wildcard trust policy in the shared Terraform module

DO FIRST:
  1. Replace the wildcard with an explicit list      runbook RB-07
  2. Force a credential refresh                     runbook RB-07

STILL EXPOSED ELSEWHERE:
  !  inventory-sync    SEV2
  !  webhooks-relay    SEV2

NEVER COMPLETED:
  x  Conduct a fleet-wide sweep    promised 2 times    Marcus Feld, Jonas Weber
```

Then you flip a switch labelled **Memory** to off and press the button again, and the same alert
gets answered by the same AI with no memory at all. That contrast is the demonstration.

---

## "Isn't that just a search box?"

A fair question, and the answer is no. Here is the difference using one example.

A search box finds the March report because it mentions similar words. That is genuinely useful. But
it will **never** tell you that two unrelated services are both carrying the same broken setting,
because that conclusion is not written in any of the reports. You would have to read all of them
yourself and work it out.

The program works it out. It forms the conclusion itself, and rewrites that conclusion when the facts
change.

It also does one thing a search box definitely cannot: it goes from "this alert" to "two other
services nobody was told about." That is a link between two separate pieces of information, not a
sentence that happens to look similar.

---

## How do we know it actually works?

Two ways. The second one is the important one.

### 1. We scored it

There are 19 incidents in our data. A person grouped them by hand into sets of "these really are the
same bug underneath."

We asked the program to find the matches. It got 5 out of 6 right. That is **83%**.

The one it got wrong is shown on screen in red, not hidden. It missed two incidents that share the
same underlying mistake: one where 32 worker threads got stuck on a network call that had no
timeout, and one where a webhook sender wasted its entire daily allowance retrying failed requests
with no wait between attempts. Same mistake, almost no words in common, which is exactly why a
search-like lookup misses them.

### 2. We turned the memory off and asked the identical question

Same AI model, same everything, just nothing stored in memory:

```
Memory ON:    match 100  |  past incidents: INC-1042, INC-1188  |  runbook RB-07  |  promised 2 times
Memory OFF:   match 0    |  past incidents: none               |  runbook none    |  none
```

Most demonstrations of this cheat. They compare a good question against a deliberately bad one,
which proves nothing, because the obvious objection is that the bad one was rigged. We did not do
that. We compared against an **empty memory** using the exact same machinery, so the only thing
that changed is whether the program remembers things.

**Worth knowing:** even with memory switched off, the program still worked out that this was an
identity permissions problem, just by reading the error message. The AI is not the weak part. The
forgetting is what costs you.

---

## The data is made up. On purpose.

The company (Northwind Commerce), the ten services, the engineers and all nineteen incidents are
invented.

Every **bug** is real. They are taken from actual outages that genuinely happened, including one
where a leftover debug log filled up the disk and silently broke the very alerting system you would
have used to diagnose it. Also in there: a database that got slow, a certificate that expired on a
weekend, and a feature flag accidentally switched on for 100% of customers within four minutes.

**Why invent the data?** Because the interesting part is the pattern across 19 incidents over six
months, and you have to build that on purpose. If we used real scraped data, the best we could show
is "finds similar documents", and that is not the interesting claim.

---

## What is honest about it

**It reads what is exposed. It does not go and find out.**

Question 4 above, "what else is still broken", is answered from a file we wrote that describes each
service's current settings. The program does not go and ask Terraform or Kubernetes what is really
configured right now.

That is the gap between a working demonstration and an actual product. It is written on the website
under "what this is not", and it is first on the list of what to build next.

Everything else genuinely works.

---

## What still has to happen

1. **Push to GitHub.** Five commits are ready. Your Hindsight API key has been confirmed as not
   present in any of them.
2. **Put your GitHub link** into the article and the two social posts, where they say `REPO_URL`.
3. **Record a 3 minute video.** The script is already written out word for word in
   `docs/DEMO_SCRIPT.md`.
4. **Publish the article** on Medium, Dev.to or your own blog.
5. **Post it on LinkedIn.** Two versions are prepared, one long and one under 800 characters.
6. **Fill in the two forms.** The profile review form for every member of your team, then the final
   submission form.

The programming and the writing are finished. The video, the publishing and the forms are what is
left, and those are the slow parts, not the code.

---

## If someone asks why this is worth building

Nineteen incidents in our sample data. Nineteen promises to fix something after an outage. Every
single one of them was never completed. Three of them are the same promise, written three separate
times, by different people, on different dates.

Every one of those is a future outage that somebody has already paid for once.

That is the whole argument. A program that can see the unclosed promises is worth more than a
program that can write a better explanation of the error message.

---

## Where everything is

| If you want to | Open |
| --- | --- |
| Run it yourself | `docs/RUNNING_IT.md` |
| Ten minute introduction | `docs/START_HERE.md` |
| How it works, in plain words | `docs/HOW_IT_WORKS.md` |
| How to use it during an incident | `docs/USER_GUIDE.md` |
| Why every number is what it is | `docs/THE_NUMBERS.md` |
| Word for word demo script | `docs/DEMO_SCRIPT.md` |
| Every document, listed | `docs/README.md` |
| If you want to change the code | `docs/DEVELOPER_GUIDE.md` |
