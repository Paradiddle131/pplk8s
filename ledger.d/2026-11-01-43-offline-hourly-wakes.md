## 2026-11-01 — Autopilot — hourly offline wakes that run every gate on cloud

- Done: `docs/agents/autopilot.md` gains offline wakes (the hourly schedule): they skip Map #212, #276 and every live GCP step, and never fall through to Map #212.
- Done: the Gates section states there are no `local` gates: each wake runs every gate on cloud, the long ones once on the PR's final head, one at a time.
- Evidence: docs only; `make lint` in the PR.
- Decisions: none in `PLAN.md`; supersedes the cloud/local split proposed in PR 268.
- Open: none.
