"""Faultline configuration.

Hindsight's LLM settings are read from the process environment, so this module
loads .env into os.environ before anything imports the Hindsight client.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
DOCS_DIR = ROOT / "docs"


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

HOST = os.environ.get("FAULTLINE_HOST", "127.0.0.1")
PORT = int(os.environ.get("FAULTLINE_PORT", "8000"))

# Two memory banks, deliberately separated.
#
#   faultline-incidents  the technical corpus: alerts, timelines, root causes,
#                        runbooks, config changes. What broke, where, why.
#   faultline-team       the human layer: who owned which postmortem action,
#                        which action items were never closed, team conventions.
#
# Hindsight isolates banks strictly. Keeping them apart lets Faultline prove the
# split matters, and means a query about "what broke" is never polluted by
# chatter about "who owes what".
BANK_INCIDENTS = os.environ.get("FAULTLINE_BANK_INCIDENTS", "faultline-incidents")
BANK_TEAM = os.environ.get("FAULTLINE_BANK_TEAM", "faultline-team")

# Where the embedded Hindsight engine persists its database.
DATA_DIR = ROOT / "data" / "hindsight"
