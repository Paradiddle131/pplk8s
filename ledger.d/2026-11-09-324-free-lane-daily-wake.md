## 2026-11-09, the semantic bet's daily free-lane wake

- Ran the free lane from the 00:12Z reset until the session's 2-hour background limit stopped it (free count 595): `custom-metricflow` and `custom-metricflow-compute` hard-v2 to k = 3 (both whole), `custom-metricflow-compute` frozen k = 3 to 94 of 228 runs; a container restart mid-lane cost an hour of re-skipping; no anomaly, GCP cost unchanged at $0.000010.
- Rebuilt and republished the report after each pass that moved a figure; added the #335 watch line and the handoff block in `findings/free-lane-days.md`.
