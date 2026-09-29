# Security

Short, because there is very little to say and most of it is good.

---

## The only secret

A Hindsight API key, which grants access to the memory banks. It lives in one place:

```
.env
```

Which is in `.gitignore`, verified as the first line of the file. `.env.example` is the tracked
version and contains no key, only blank placeholders.

**Verified before publishing:** the key appears in **no commit** and in **no tracked file**. Checked
by scanning every commit in the repository, not just the current tree.

## If you think a key has leaked

1. Revoke it in the Hindsight dashboard. That is the only step that matters; the rest is cleanup.
2. Generate a new one and put it in `.env`.
3. Scan the history rather than trusting the working tree:

   ```bash
   git log --all -p -S 'hsk_' -- . | head -40
   ```

   If the key is in history, `git filter-repo` or a fresh repository with a clean first commit.
   Rewriting published history is not enough on its own, which is why revoking first is the right
   order.

## What the app does with it

Sends it to Hindsight Cloud with every memory call. That is the entire use. It is not logged, not
written to the corpus, not returned by any API route, and not included in any error response.

## What Faultline does not have

| Absent | Consequence |
| --- | --- |
| Authentication | Anyone who can reach the port can triage. Do not expose it |
| Multi-tenancy | One shared set of banks. Two people using it share a memory |
| Audit trail | No record of who asked what or when |
| Input validation beyond Pydantic | The only user input is the memory search box, which goes to `recall` as a query |
| Rate limiting | Concurrent triages serialise behind the single memory thread, which is a crude form of backpressure but not a control |
| Encryption at rest beyond Hindsight's | The corpus is synthetic and the key is the only sensitive value |

## If you put this on a network

Do not, as it stands. The minimum needed to try it safely:

1. Bind to `127.0.0.1` only, which is the default
2. Put it behind something that authenticates
3. Be aware that the triage endpoint is unauthenticated, so anyone reaching it can read your
   incident corpus and write to the memory banks
4. Remember `/api/setup?force=true` deletes both banks and rebuilds them

## Dependency posture

| Package | Why |
| --- | --- |
| `hindsight-all` | The memory system. MIT |
| `fastapi`, `uvicorn` | The server. MIT, BSD |
| `google-genai` | Only for the offline local-model path, and not loaded when using Hindsight Cloud |

No CDN-hosted JavaScript. The only external request any page makes is to Google Fonts for
Newsreader and IBM Plex Mono, and the design degrades to Georgia and the system monospace if that
does not load.

## Reporting something

If you find a genuine security problem in this project, open an issue describing it. There is no
disclosure process because there is no deployed service and no user data, and inventing one would
be theatre.
