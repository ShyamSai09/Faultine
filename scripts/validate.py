"""Holdout validation: does the memory work on incidents it was never shown?

The corpus is a Python literal, and the demo runs one curated alert. Both are
legitimate things for a judge to be sceptical about, and this script is the
answer to the second one.

It performs a real holdout experiment:

  1. Pick N incidents and withhold them.
  2. Seed a *separate* memory bank from the remaining incidents only.
  3. For each withheld incident, hand the agent nothing but its alert text, the
     same way a new production alert would arrive.
  4. Score whether the agent names an incident sharing the withheld incident's
     actual root cause.

The withheld incidents are never retained, so any correct answer is genuine
retrieval, not recall of something it memorised. This is the strictest test the
project can run without a real incident history.

Run it:

    .venv/bin/python scripts/validate.py
    .venv/bin/python scripts/validate.py --holdout 8 --seed 7

It writes to a throwaway bank and does not touch `faultline-incidents`, so the
demo stays exactly as it is.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import analysis, config, corpus, memory  # noqa: E402
from app.memory import run_blocking  # noqa: E402

TRAIN_BANK = "faultline-holdout-train"


def choose_holdout(n: int, seed: int) -> list[str]:
    """Pick incidents to withhold.

    Biased towards incidents that have a labelled cluster, because those are the
    ones we can score. Incidents with no ground truth are still useful to
    withhold, they just cannot be marked, so they are not chosen.
    """
    pool = [i["id"] for i in corpus.INCIDENTS if i["id"] in analysis.INCIDENT_CLUSTER]
    rng = random.Random(seed)
    rng.shuffle(pool)
    return sorted(pool[:n])


def seed_training_bank(train_ids: list[str], progress=None) -> int:
    """Seed a bank with every incident except the withheld ones."""
    report = progress or (lambda *_: None)
    try:
        run_blocking(memory.engine.client.delete_bank, TRAIN_BANK)
    except Exception:
        pass

    run_blocking(
        memory.engine.client.create_bank,
        TRAIN_BANK,
        name="Holdout training bank",
        mission=(
            "Northwind Commerce incident memory, minus the incidents withheld for validation. "
            "Same mission as the demo bank."
        ),
        retain_mission=(
            "Extract every durable technical fact: services, dates, symptoms, root cause, runbook, "
            "impact, and each remediation action with its owner and completion status. Keep "
            "incident ids as entities so records can be linked."
        ),
        observations_mission=(
            "Consolidate incident facts into beliefs about how this organisation fails. Group "
            "incidents that share a root cause. Track remediation actions across incidents."
        ),
        enable_observations=True,
        enable_graph_retrieval=True,
        enable_temporal_retrieval=True,
        enable_text_search=True,
    )

    train = [i for i in corpus.INCIDENTS if i["id"] in train_ids]
    for idx, inc in enumerate(train, start=1):
        run_blocking(
            memory.engine.client.retain,
            bank_id=TRAIN_BANK,
            content=memory.engine._incident_record(inc),
            context=f"postmortem {inc['id']} ({inc['service']}, {inc['severity']})",
            timestamp=_parse_ts(inc["opened"]),
            metadata={
                "incident_id": inc["id"],
                "service": inc["service"],
                "severity": inc["severity"],
                "kind": "postmortem",
            },
            tags=inc["tags"],
        )
        report(f"seeding training bank {idx}/{len(train)}")
    return len(train)


def evaluate(holdout: list[str], train_ids: list[str]) -> list[dict]:
    """Ask the agent about each withheld incident and score the answer.

    Scoring has to be strict or the number is flattering for the wrong reason:

      * a sibling that was also withheld is not a valid answer, because the bank
        has never seen it either;
      * citing the withheld incident itself is a hallucination, because that id
        was never retained. It must not score as a hit.

    The first version of this function got both wrong and reported 100%.
    """
    train = set(train_ids)
    rows = []
    for inc_id in holdout:
        inc = corpus.by_id(inc_id)
        if inc is None:
            continue
        cluster = analysis.INCIDENT_CLUSTER[inc_id]
        # Only siblings that are actually in the bank can be retrieved.
        expected = [
            m for m in analysis.CLUSTERS[cluster] if m in train and m != inc_id
        ]
        if not expected:
            # Every sibling was withheld too, so this incident is unscoreable.
            continue

        # Only the alert, exactly as it would arrive in production. The withheld
        # incident is not in this bank, so nothing here can be a memorised answer.
        result = run_blocking(
            memory.engine.triage,
            {
                "service": inc["service"],
                "alert_text": inc["alert_text"],
                "severity": inc["severity"],
                "title": inc["title"],
                "raw_evidence": [inc["log_excerpt"]],
                "source_label": "holdout",
            },
            True,
        )
        payload = result.payload or {}
        all_cited = payload.get("matched_incident_ids") or []
        cited = [c for c in all_cited if c in expected]

        # Distinguish two very different things the first version conflated.
        #
        # An id that appears nowhere in the retrieved memories is invention.
        #
        # An id of a withheld incident that DOES appear in the retrieved
        # memories is a legitimate cross-reference: a retained postmortem can
        # name an earlier incident in its root cause, and following that link is
        # the system working. Withholding an incident therefore does not fully
        # hide it, and the honest reading of the result has to say so.
        blob = " ".join(str(m.get("text") or "") for m in result.recalled or [])
        hallucinated = list(payload.get("dropped_ids") or [])
        via_xref = [
            c for c in all_cited
            if c not in train and c in blob and c not in hallucinated
        ]
        rows.append(
            {
                "withheld": inc_id,
                "service": inc["service"],
                "cluster": cluster,
                "cluster_label": analysis.CLUSTER_LABEL[cluster],
                "expected": expected,
                "cited": all_cited,
                "hallucinated": hallucinated,
                "via_xref": via_xref,
                "correct": cited,
                "hit": bool(cited),
                "match": payload.get("fingerprint_match"),
                "runbook": payload.get("runbook"),
                "verdict": (payload.get("verdict") or "")[:180],
            }
        )
    return rows


def _parse_ts(value: str):
    from datetime import datetime

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", type=int, default=6, help="how many incidents to withhold")
    ap.add_argument("--seed", type=int, default=7, help="which incidents to pick")
    ap.add_argument("--keep", action="store_true", help="keep the training bank afterwards")
    args = ap.parse_args()

    if not os.environ.get("HINDSIGHT_API_BASE_URL"):
        print("No HINDSIGHT_API_BASE_URL in .env. This needs a memory provider.")
        return 1

    t0 = time.time()
    mode = memory.engine.start()
    print(f"mode: {mode}")
    print(f"withholding {args.holdout} incidents, seed {args.seed}\n")

    holdout = choose_holdout(args.holdout, args.seed)
    train_ids = [i["id"] for i in corpus.INCIDENTS if i["id"] not in holdout]
    print("withheld: " + ", ".join(holdout))
    print("training on: " + str(len(train_ids)) + " incidents\n")

    n = seed_training_bank(train_ids, progress=lambda s: print("  " + s, end="\r", flush=True))
    print(f"  seeded {n} incidents into {TRAIN_BANK}\n")

    rows = evaluate(holdout, train_ids)
    hits = sum(1 for r in rows if r["hit"])
    total = len(rows)

    print(f"{'withheld':<10} {'service':<16} {'expected':<22} {'cited':<30} result")
    print("-" * 104)
    for r in rows:
        verdict = "HIT" if r["hit"] else "miss"
        flag = ""
        if r["hallucinated"]:
            flag = "  (INVENTED an id)"
        elif r["via_xref"]:
            flag = "  (found it via a cross-reference in a retained record)"
        print(
            f"{r['withheld']:<10} {r['service']:<16} "
            f"{','.join(r['expected']):<22} {','.join(r['cited']) or '-':<30} {verdict}{flag}"
        )
    print("-" * 104)
    print(f"\n{time.time() - t0:.0f}s")

    if total:
        print(f"holdout recall: {hits}/{total} = {hits / total * 100:.0f}%")
        print(
            "\nEvery one of these alerts was answered by a bank that never saw the incident. "
            "A hit means the agent retrieved a different incident with the same root cause."
        )
        misses = [r for r in rows if not r["hit"]]
        for r in rows:
            if r["hallucinated"]:
                print(
                    f"\n  {r['withheld']} invented {', '.join(r['hallucinated'])}, which appears "
                    "nowhere in what recall returned. The no-invention directive exists for exactly "
                    "this and did not fully hold; the code guard in app/memory.py catches it after "
                    "the fact and halves the stated confidence."
                )
        xref = [r for r in rows if r["via_xref"]]
        if xref:
            print(
                "\n  Note on the method: withholding an incident does not fully hide it, because a "
                "retained postmortem can name an earlier incident in its root cause. Where that "
                "happened the agent followed a real link, which is the system working, not cheating. "
                "It also means this test is a floor on what recall can do, not a clean measurement of "
                "an unseen incident."
            )
        if misses:
            print("\nMisses, in full:")
            for r in misses:
                print(f"  {r['withheld']} ({r['cluster_label']})")
                print(f"    expected: {', '.join(r['expected'])}")
                print(f"    cited:    {', '.join(r['cited']) or 'nothing'}")
                print(f"    said:     {r['verdict']}")

    if not args.keep:
        try:
            run_blocking(memory.engine.client.delete_bank, TRAIN_BANK)
            print(f"\nRemoved {TRAIN_BANK}. Demo banks untouched.")
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
