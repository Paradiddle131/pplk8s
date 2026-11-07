# Probes

The scripts the track's findings ran, one per experiment, named after the issue: `<issue>_<slug>.py` (or `.sh`).
Each starts with a docstring: what it measures, how to run it (`uv run --with … python <file>` from the repo root), the env it reads, and whether it is live (the lab project) or offline.
Live probes cap every BigQuery job (`maximum_bytes_billed`), dry-run first, and never write outside a `bet_` dataset or a `bet-` data agent.
Lint: `uvx ruff@0.17.0 check docs/research/semantic-bet/probes && uvx ruff@0.17.0 format --check docs/research/semantic-bet/probes`.
