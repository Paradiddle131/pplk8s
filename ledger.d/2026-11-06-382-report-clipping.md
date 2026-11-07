## 2026-11-06 — Semantic track — the report's clipped text, found by a detector and fixed (#336, #382)

- Done: the owner saw "Claude Code subagent" lose its first letters in the setup explorer; a subagent reproduced it and found 7 more clipping spots: 26 findings across 324 page states, from 6 causes (the explorer's lane heads and narrow side titles, Figure 2's two-panel and phone labels, Figure 5's right labels, Figure 4's axis title).
  Labels now wrap instead of clipping, and Figures 2 and 5 redraw once the label font loads. `report/tools/clipcheck.js` keeps the check.
- Evidence: `node tools/clipcheck.js` → before 26 distinct findings, after `Findings: 0 distinct`, no console errors and no horizontal page scroll at 1280, 1024, 768, 400 and 360 px in light, dark and the dark button; rerun by the main session on the committed page.
- Open: none.
