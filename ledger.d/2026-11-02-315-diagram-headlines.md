## 2026-11-02 — Docs — a headline on every architecture sheet (#315)

- Done: `assets/gcp-target.html`, `platform.html` and `semantic-agent.html` carry the headline claude-dotfiles' `draw-architecture` kit now requires (`Sheet(svg, {headline})`), each the one question its sheet answers: "How the platform runs on GCP, from sources to the agent", "What runs where in the lab, and what it becomes on GCP", "How a question travels through the semantic agent"; each drawing moved down to start at y 64 (40, 40 and 48 units, the viewBox as much taller), rebuilt with the new kit, PNGs regenerated; the `<picture>` embeds set width only, so they stay as they are.
- Evidence: the kit's `bin/check.cjs` on the three: 0 problems in light and dark, and in both of `platform.html`'s modes (lab, gcp); crossings unchanged (4, 1 and 4, bridged); each PNG looked at in light or dark.
- Decisions: none in PLAN.md.
- Open: none.
