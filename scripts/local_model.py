"""Boot Hindsight on a local llama.cpp model. No API key, no network cost.

This exists so the whole pipeline can be verified without depending on a paid or
rate-limited provider. The first run downloads the model (~3.5 GB) and caches it.

Run:  .venv/bin/python scripts/local_model.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hindsight import HindsightServer  # noqa: E402
from hindsight_client import Hindsight as HindsightClient  # noqa: E402

BANK = "local-smoke"


def main() -> int:
    t0 = time.time()
    print("starting local llama.cpp model (first run downloads ~3.5GB)…", flush=True)
    server = HindsightServer(
        llm_provider="llamacpp",
        llm_model="gemma-4-e2b-it",
        log_level="warning",
    )
    # The default 30s budget is not enough to download and load a multi-GB model.
    server.start(timeout=3600)
    try:
        print(f"server up at {server.url} ({time.time() - t0:.0f}s)", flush=True)
        client = HindsightClient(base_url=server.url, timeout=1800.0)

        try:
            client.delete_bank(BANK)
        except Exception:
            pass
        client.create_bank(BANK, name="local smoke", mission="Verify local model retain works.")

        t = time.time()
        client.retain(
            bank_id=BANK,
            content=(
                "INC-1042: payments-api returned 503 for 41 minutes because a stale IAM role "
                "survived an automated credential rotation. Runbook RB-07 fixed it."
            ),
            context="postmortem",
        )
        print(f"retain ok ({time.time() - t:.0f}s)", flush=True)

        t = time.time()
        r = client.recall(bank_id=BANK, query="Why did payments-api return 503?")
        print(f"recall ok ({time.time() - t:.0f}s):", flush=True)
        for item in (getattr(r, "results", None) or [])[:4]:
            print("  *", getattr(item, "text", item), flush=True)

        t = time.time()
        a = client.reflect(bank_id=BANK, query="What broke and how was it fixed?")
        print(f"reflect ok ({time.time() - t:.0f}s):", flush=True)
        print(getattr(a, "text", a), flush=True)
    finally:
        try:
            server.stop()
        except Exception:
            pass
    print(f"LOCAL PIPELINE OK in {time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
