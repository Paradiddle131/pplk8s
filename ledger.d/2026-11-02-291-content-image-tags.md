## 2026-11-02 — Maintenance — image tags computed from their build inputs (#291)

- Done: `scripts/image-tag.sh` hashes an image's build inputs from the working tree, committed or not (git pathspecs: its contexts less tests, DAGs and evals, plus build args); the `Makefile` derives all six image tags from it as `<line>-<12 hex>` (`ELF_IMAGE`, `DBT_IMAGE`, `ADAPTER_IMAGE`, `AGENT_IMAGE` with `dbt/`, `AIRFLOW_IMAGE`, `AIRFLOW_DRILL_IMAGE` with its build args), once per top-level `make`, an override still winning; `tests/images/image-tag-test.sh` (`make image-tag-test`, in `make test`); owner's call mid-session: pathspecs in the `Makefile` rather than a `.dockerignore` parser; D16, the autopilot profile's bump rules, the runbook and a LESSONS line follow.
- Evidence: see the PR for `make image-tag-test` (20 checks, three runs), `make check`, `make verify` and the cluster deploy with the computed tags.
- Decisions: D16 rewritten: tags name their content and are never bumped by hand.
- Open: a base image that moves under an unchanged Dockerfile keeps its tag (pin bases; `FORCE_BUILD=1`).
