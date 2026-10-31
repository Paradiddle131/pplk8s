## 2026-10-31 — Maintenance — README images keep their proportions

- Done: the whole-lab picture, the agent's code picture and the k9s screenshot drop their `height` attribute and keep a `width` (the diagrams their 1x width, 1200, for a 2x PNG), so GitHub's `max-width: 100%` scales them down whole instead of stretching them tall.
- Evidence: GitHub's rendered README (`repos/<owner>/<repo>/readme`, HTML) in Chromium with GitHub's markdown CSS (`github-markdown-css` 5.9.0) at a 980 px page: before, the whole-lab picture showed 890×2344 for a 2400×2344 PNG (2.6 times too tall); after, 890×869, its own proportion.
- Decisions: none.
- Open: none.
