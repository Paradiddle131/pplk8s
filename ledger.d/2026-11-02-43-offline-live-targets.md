## 2026-11-02 — Autopilot — offline wakes skip only the `Live` make targets

- Done: `docs/agents/autopilot.md` names the targets an offline wake skips by their `Live` help text, so the emulator-only `gcp-image-check` and the offline `gcp-validate` still run as gates.
- Evidence: the first hourly offline wake (2026-11-01 23:45Z) was refused `make gcp-image-check` under the earlier `make gcp-*` wording.
- Decisions: none.
- Open: none.
