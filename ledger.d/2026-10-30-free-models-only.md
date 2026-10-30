## 2026-10-30 — Semantic — the agent runs on OpenRouter's free models only

- Done: `build_model` refuses an OpenRouter model id that does not end in `:free`, so neither agent nor `make agent-eval` can reach a paid model whatever the key's budget allows; `semantic/PLAN.md` SL-5 and the agent's README say so.
- Evidence: see the PR.
- Decisions: free models only, even when the free quota is spent for the day (owner, 2026-10-30); enforced in the seam, not in a prompt or a doc alone.
- Open: none.
