## 2026-11-06 — Semantic track — the free lane's order for hard-v2, and the data agents on its new cases (#379, under way)

- Done: `probes/lanes/free_lane.sh` runs v1's k = 1 remainder, then `bet_carry` and `hard-v2` at k = 1 and k = 3 for the four core free-model arms, then the frozen set's k = 3 round, v1-hard's k = 3 dropped; `gcp_pass.sh` takes the arm, k and the default mode, with the cost and usage gates before and after; the profile's completion plan says so.
  The four data-agent arms (`native-context-bare` with thinking, `native-bare`, `native-context`, `native-kc-max`) ran `hard-v2`'s 15 new cases at k = 1, then k = 3; the report was rebuilt and republished with `hard-v2` in its appendix.
- Evidence: 180 of 180 data-agent runs right on the new cases (`eval-hard-v2-native-*.jsonl`); 16 gates, each `gcp-cost-check` ok at $0.000010 and `gcp-usage-check` ok; shellcheck passes on both lane scripts; OpenRouter free count 991 of 1,000 all day, so no free-model pass ran.
- Open: the free-model `hard-v2` passes, from the 00:07Z lane on 2026-11-07 (about four daily quotas), then #380.
