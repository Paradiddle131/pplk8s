## 2026-11-03 — Semantic track — Knowledge Catalog's dbt import, the offline half (#326)

- Done: `docs/research/semantic-bet/probes/326_dbt_artifacts.sh` builds the import's `manifest.json` offline on the `gcp` target, full and trimmed to the semantic layer; the finding `docs/research/semantic-bet/findings/2026-11-03-326-kc-dbt-import.md` records both sizes and the import's documented shape; Q1 is `measuring`.
- Evidence: full 2,846,984 bytes (427 nodes, 625 macros, 16 semantic models, 57 metrics, 7 saved queries), trimmed 254,713 bytes (16 silver models and the semantic layer).
- Open: `make gcp-cost-check` fails on $0.000010 of Artifact Registry intercontinental egress (2026-11-02), which stops live steps until the owner answers #338; then staging, the owner's import paste and the read-back.
