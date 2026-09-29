# What this project is, in plain words

This page explains the problem being solved. It assumes you know what a web service is, and
nothing more.

---

## The situation

Almost every company that runs its own software has a small team responsible for keeping it
running. When something breaks, that team gets woken up. They are called "on-call".

Here is what that job actually feels like from the inside.

You are woken at 2am. A service you have never heard of is throwing errors. You look at the alert.
It says something about a permission problem with a role. You do not know that role. You do not know
what this service does. You certainly do not know what broke last time, because nobody has looked
at last time.

You search. You find old documents. Old documents are a mess. They are written by whoever was on
call that night, under pressure, for an audience of themselves. Half of them describe symptoms
rather than causes. Some of them are contradicted by newer ones.

Two hours later you have fixed it, or escalated it, or guessed something that turned out to be
right. Then you write it up. The write-up includes a list of things to do so it does not happen
again.

That list is the part that matters, and it is the part that almost never gets done.

## The three failures

### Failure one: the fix list is write-only

Postmortems are write-only documents. They get filed, linked in a channel, and never read again.
Nobody has a system that reminds them that there are nineteen open items, that three of them are
the same item, and that the one about permissions was first written six months ago and has been
open since.

This is not because anyone is lazy. It is because there is no mechanism. A bullet point in a
document does not chase anyone.

### Failure two: the same bug arrives wearing a different hat

This is the one that surprises people. The same underlying mistake shows up again and again, but
each time it looks completely different, so nobody recognises it.

The real example in this project's data. A company has an identity setting written as "trust
everyone". It causes an outage on the payments service, which shows up as customers getting errors
at checkout. Fixed by hand. The write-up says "check the other nine services for the same thing".

Three months later, a different service fails. The on-call engineer spends 26 minutes looking at a
deploy from four days earlier, because the error message mentions a token, and tokens are usually
about deploys. It is actually the same identity setting. Nobody finds the March write-up.

A third time, on a third service, it presents differently again: the service works fine for
eleven days, then quietly breaks, because a cached credential hid the problem the whole time.

Three incidents. Three services. Five months. One cause. And the thing that would have caught it
was a to-do item from the first one.

### Failure three: the failing thing is not the broken thing

The service that pages you is rarely the one at fault. The payments service goes down because an
identity setting is wrong somewhere else. The checkout service slows down because a database
connection pool is too small, and it was too small because a config default was never changed in
that service, and it was never changed because a similar change was made by hand in one other
service and everyone assumed it was everywhere.

Engineers spend most of an incident working out *where* the problem actually is. That work is
completely different from the work of reading an error message, and it depends almost entirely on
knowing how the system has broken before.

## What Faultline does about it

An alert arrives. Before the on-call engineer has finished reading it, Faultline has already
answered three questions that normally take the first hour of an incident:

1. **Have we seen this before?** And if so, where, and when?
2. **What actually fixed it then?** Runbook, command, change.
3. **What else is still broken this way?** Which other services carry the same bad configuration
   right now and have simply not failed yet.

And two more that nobody usually asks:

4. **Did we already promise to fix this, and did we?** If the March postmortem has an open action
   about this exact failure, that is the most useful sentence anyone could read at 2am.
5. **How many times has this same promise been made?** When it is the third time, the problem is
   no longer an engineering task. It is a process problem, and the tool should say so.

## Who this is actually for

Not for a hobby project or a demo of "look, AI is clever". Specifically for the engineer at 2am
who would rather spend their time on the fix than on the search, and for the engineering manager
who wants to know that the organisation keeps re-learning the same lesson.

The value is not clever answers. The value is not having to start from zero.

## Why this is not just RAG

People ask this, so here is the honest version.

RAG means: break documents into chunks, embed each chunk, and when a question comes in, find the
chunks that look most similar. It is good at "find me the document about this".

Faultline needs three things RAG structurally cannot do:

**Forming a belief from several documents.** To say "inventory-sync and webhooks-relay are both
carrying the insecure trust policy", the system has to read four separate records about four
different services and conclude they share a property that is written down in none of them. A
retrieval system returns documents. It does not return a conclusion that is not in any document.

**Joining across separate collections.** "That fix was written down twice and never completed"
requires linking an incident record in one memory store to a to-do item in a different store, then
to a *third* item raised after a different incident three months later. That is a graph traversal.
Similarity is not a traversal.

**Remembering what was true before, alongside what is true now.** Hindsight keeps history rather
than overwriting it, so it can say "this broke in March, was fixed by hand in June, and the
underlying default was never changed".

## What this project is not

Being honest about the edges, because a tool you trust too much is worse than no tool.

- **It only knows what was retained into it.** If an outage was never written up, Faultline does not
  know it happened. There is no magic.
- **It is a demonstration, not a production service.** The data is synthetic. It has no
  authentication, no multi-tenancy, and no audit trail. Do not point it at real infrastructure.
- **The numbers are measured on this synthetic corpus.** They are honest measurements of a
  constructed dataset. They are not a claim about anyone's real incident history. See
  [THE_NUMBERS.md](THE_NUMBERS.md).
- **It gets things wrong.** One pair of related incidents out of six is not recovered by retrieval.
  That is shown rather than hidden.

Next: [HOW_IT_WORKS.md](HOW_IT_WORKS.md)
