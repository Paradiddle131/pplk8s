## 2026-10-31 — Semantic track — finance's daily table keeps a return recorded on a day without orders

- Done: `exp_net_sales_daily` covers every UTC day with orders or returns (owner's choice A on #150), revenue 0 on a day with returns only, so its returns columns equal the `returns_*` metrics by construction and the two metric hops stay strict; its description, contract and SL-9 say so. `semantic-check.sh`'s seeded return on a day without orders now expects that row and every hop passing; the migration doc names the parity difference this opens on real data. Carried in #160, whose lab run on a used warehouse failed on this hop (return D-1 on 2026-10-05, a day without orders). dbt 0.7.14, semantic-agent 0.1.13. #167 closed as its duplicate.
- Evidence: see the PR.
- Decisions: SL-9's "a return on a day without orders fails the build" replaced by the union grain.
- Open: none.
