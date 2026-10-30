## 2026-10-30 — Maintenance — the README shows the semantic track

- Done: `assets/semantic-track.html`, an interactive schematic of the semantic track at its destination (every issue under Map #135 done): the domains the Airflow lab lands, the dbt project with its semantic YAML, checks and generated artefacts, the warehouse's tiers with the role zone each agent reads, the ADK agent with its metric tools, freshness and audit, the text-to-SQL baseline and the eval; a Here / On GCP switch relabels every stand-in with its GCP counterpart, hovering a part lights what it talks to, and a button traces a question through the system. `assets/semantic-track.png` is its export, under "Second track" in the README with a one-liner.
- Evidence: rendered in Chromium in both modes and both themes with no console error; the switch, hover and trace exercised in a browser; the PNG is the lab's names at 2x.
- Decisions: draw the end state rather than today's, so the picture does not change with each use-case issue; keep words to names and labels, with the sentences in the README; commit the image under `assets/` rather than as an upload, so a fork carries it.
- Open: none.
