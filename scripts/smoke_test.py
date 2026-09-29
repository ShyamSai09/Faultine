"""Smoke test: prove Hindsight retain/recall/reflect works against the configured LLM.

Run with:  .venv/bin/python scripts/smoke_test.py
This is the first thing to run on a fresh clone — if it passes, the memory layer
is real and everything else in Faultline is just UI and orchestration.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: F401  (loads .env into os.environ)

from hindsight import HindsightServer  # noqa: E402
from hindsight_client import Hindsight as HindsightClient  # noqa: E402

BANK = "smoke-test-bank"


def main() -> int:
    t0 = time.time()
    print(f"provider={config.os.environ.get('HINDSIGHT_API_LLM_PROVIDER')} "
          f"model={config.os.environ.get('HINDSIGHT_API_LLM_MODEL')}")

    with HindsightServer(
        llm_provider=config.os.environ.get("HINDSIGHT_API_LLM_PROVIDER", "gemini"),
        llm_model=config.os.environ.get("HINDSIGHT_API_LLM_MODEL", "gemini-3.8-flash"),
        llm_api_key=config.os.environ.get("HINDSIGHT_API_LLM_API_KEY", ""),
        log_level="warning",
    ) as server:
        print(f"server up at {server.url} ({time.time() - t0:.1f}s)")
        client = HindsightClient(base_url=server.url)

        try:
            client.delete_bank(BANK)
        except Exception:
            pass
        client.create_bank(
            BANK,
            name="Smoke test",
            mission="Test bank for verifying the Faultline memory layer.",
        )
        print("bank created")

        t = time.time()
        client.retain(
            bank_id=BANK,
            content=(
                "INC-1042: payments-api returned HTTP 503 for 41 minutes on 2026-03-14. "
                "Root cause was a stale IAM role after an automated credential rotation "
                "removed the sts:AssumeRole permission. Fixed by re-running runbook RB-07."
            ),
            context="incident postmortem",
        )
        print(f"retain ok ({time.time() - t:.1f}s)")

        client.retain(
            bank_id=BANK,
            content=(
                "On 2026-03-16 the same stale IAM role issue affected checkout-web in staging "
                "and was never remediated. The action item from INC-1042 to sweep all services "
                "for the same misconfiguration is still open."
            ),
            context="follow-up audit",
        )
        print("retain 2 ok")

        t = time.time()
        r = client.recall(bank_id=BANK, query="What broke payments-api in March?")
        print(f"\n--- recall ({time.time() - t:.1f}s) ---")
        for item in (r.results or [])[:5]:
            print("  *", getattr(item, "text", item))

        t = time.time()
        a = client.reflect(
            bank_id=BANK,
            query="Which services are still exposed to the stale IAM role problem?",
        )
        print(f"\n--- reflect ({time.time() - t:.1f}s) ---")
        print(getattr(a, "text", a))

    print(f"\nSMOKE OK in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
