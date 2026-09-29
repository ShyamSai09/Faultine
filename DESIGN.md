# Faultline — design direction

> **Author's caveat.** I chose this direction myself rather than being given one. Agent-chosen
> aesthetic skews hard toward the default taste these rules exist to filter, so treat this file
> as a proposal to be argued with, not a fait accompli. If the paper metaphor fights the product
> during a live demo at 3am, say so and I will revisit it.

Reading this as: **an incident postmortem that writes itself while the incident is still
happening.** For on-call engineers and the people who judge their tooling. In the visual language
of a printed technical report. Dials **ENERGY 1 / RHYTHM 2 / MOTION 1**.

---

## The idea

A postmortem is a document. It has a date, a title, a timeline, a log excerpt cut and pasted into
the body, a root cause, and an action list with owners against each line. Most of it is prose, and
the prose is the only part anyone reads a year later.

So the interface is a page of paper, and **the console is the postmortem being written in real
time**. Every screen maps onto a part of a postmortem:

| Console region | Postmortem equivalent |
| --- | --- |
| Incoming alert | The alert as it fired, as a cut-and-pasted clipping |
| Raw evidence | The log excerpt block |
| Agent response | The analysis section |
| Prior incidents | Cross-references to earlier incidents |
| Still exposed elsewhere | The findings list, in the reviewer's hand |
| Remediation never completed | The action list, with owners |
| Mental models | The reference appendix, already written |

The competing obvious choice was a dark operations console. Dark for on-call has a real argument
and I rejected it anyway: the product's entire argument is that reading matters more than
alerting, and nobody reads a glowing screen. Paper wins on legibility, and on contrast, which
resolves several accessibility problems for free. The one concession to night use is that machine
output stays monospaced and dense, so scanning at a glance still works.

## Palette

Two neutrals and one accent. Nothing else, and the accent means exactly one thing.

| Token | Value | Reason |
| --- | --- | --- |
| `--paper` | `#F2EFE9` | Warm off-white, the colour of document stock. Not `#fff`, which glares at night and flattens the hairline rules. |
| `--paper-2` | `#E9E5DC` | Sunken surface, for pasted log clippings so machine output reads as embedded evidence rather than interface chrome. |
| `--ink` | `#191917` | Warm near-black. Text and rules. |
| `--ink-2` | `#4A4740` | Secondary text. Measured 8.9:1 on paper. |
| `--ink-3` | `#6E6A61` | Labels and captions. Measured 5.1:1 on paper, clears AA for normal text. |
| `--rule` | `#CFC9BC` | Hairlines, the document's ruling. Also the focus ring, at 2px, for a 3.4:1 non-text contrast. |
| `--red` | `#A32B21` | **The accent, and the reviewer's pen.** Used only on findings that are still open. Never decoration, never a button fill, never a gradient. |
| `--red-wash` | `#F6E7E4` | The one tint, for the background of an open finding. |

Deliberately absent: green. A postmortem does not tick things green, and the document should not
pretend. "Resolved" is expressed with the absence of red, a weight change, and a hairline. Adding
a success green would make it a status dashboard, which is the thing this is arguing against.

Every pairing above is measured, not eyeballed. The previous palette failed WCAG AA on four
separate surfaces; this one was built from the ratios backwards.

## Typography

Two families, with a strict division of labour. Prose is prose. Everything a machine produced is
machine type.

| Use | Face | Reason |
| --- | --- | --- |
| Headings and body | **Newsreader** | A transitional serif with real editorial character, slightly narrow, designed for reading on screen. A postmortem is a written document, so the document is set in a reading face. It is also specifically *not* the sans-serif every developer tool ships in. |
| Log output, IDs, dates, labels | **IBM Plex Mono** | Drawn by IBM for technical documentation, which is literally what a log excerpt is. It carries the machine/human boundary: if it is set in Plex Mono, a machine wrote it. |

The rule is enforced everywhere, including in the console: the agent's prose analysis is set in
Newsreader, the raw alert and log lines in Plex Mono. That typographic split *is* the product's
thesis, rendered as a font decision.

Sizes are a small scale with no display sizes. The largest type on the page is the h1 at 34px.
## Nothing shouts, because a document does not shout.

## Composition: the ruled gutter

The identity motif, repeated in every screen: a narrow left column, about 96px, carrying the
metadata an author would put in the margin, separated from the body by a single hairline.

Dates, incident ids, service names, runbook numbers, owners. Never prose. It appears in the
console columns, in every table, in the metric definitions, and in each section of the landing
page. One gesture, applied consistently, is what makes the design recognisable without a logo.

Rhythm (dials call for 2) alternates deliberately: full-width prose sections, then single-measure
sections centred in the column, then full-bleed tables. Never two identical compositions in a row.

## Motion (dials call for 1)

Hover and focus states only, plus one moment worth animating: when an open finding is confirmed,
its rule draws across in red over 320ms. That is the entire motion budget.

No fade-up, no float, no scale, no stagger. A document does not animate, and an interface that
scroll-reveals its own content is telling you it has nothing to say.

## Rules I am holding myself to

- **No background grid, no glow, no gradient fills, no glass, no shadows for floating.** Depth
  comes from hairlines and from `--paper-2` for embedded evidence.
- **No capsule badges.** A status is set in Plex Mono, small, with a rule. No pills, no glow, no
  uppercase-with-wide-tracking.
- **No coloured left stripes on cards.** Emphasis is a red hairline plus a red label, not a
  decorative bar.
- **The accent means "still open".** If red is not attached to an unresolved finding, it is wrong.
- **No em dashes in any interface text.**
- **Every figure is measured on this corpus and labelled as such.** No invented statistics, no
  testimonials, no logo bars, no pricing.
- **Logo:** the wordmark set in Newsreader with the first letter in red. Invented here, so it is
  marked as provisional.

## What was rejected, and why

| Rejected | Reason |
| --- | --- |
| Dark operations console | The strongest competitor. Rejected because the product argues that reading matters more than alerting, and paper wins on contrast and legibility. Revisit if night use proves it wrong. |
| San Francisco / Inter, the developer-tool default | Reads as generic infrastructure. Serif prose is the whole counter-move. |
| Green success colour | Would turn a document into a status dashboard. |
| Blue-grey enterprise palette | Says "compliance software". This is a postmortem, not a control. |
| Bento grid, feature cards, three-step explainer | Template layout with no relationship to a document. |
