## 2026-11-01 — Maintenance — the autopilot profile splits gates into cloud (fast) and local (long)

- Done: `docs/agents/autopilot.md` § Gates lists the `cloud` gates every wake runs (`make check`, dbt parse and validation on a scratch database, EL Factory from the host, `make rules-test`) and the `local` gates the owner's WSL agent runs from each handoff (`make semantic-check`, `make bigquery-emulator-check`, `make catalog-check`, `make verify`, the cluster, Airflow, a live eval), following claude-dotfiles' autopilot skill.
- Evidence: a session spent about six rounds of 15 to 20 minutes on the long suites before each push of a ten-PR stack.
- Decisions: none in PLAN.md; the profile is the owner's workflow.
- Open: none.
