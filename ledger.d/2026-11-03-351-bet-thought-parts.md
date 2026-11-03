## 2026-11-03 — Semantic track — the probes score the answer, not the model's reasoning (#351)

- Done: `docs/research/semantic-bet/probes/328_mcp_agent.py` and `330_toolbox_agent.py` keep ADK's `thought` parts out of `answer` (logged as `thought`), as `evaluation.py` already does; `bet_rule.NOT_IN_DATA` also reads "cannot provide / determine / compute / calculate" as a decline, with a unit test on a live answer.
- Evidence: rerunning the custom-toolbox arm's two misread cases: `median_order_value` scored declined (was wrong), `bet_customers_september` wrong (a decline beside a figure; was right off the leaked reasoning); `make agent-test` 307 passed.
- Open: the #328 and #330 JSONLs keep their concatenated answers (their findings carry hand readings); #350's run 1 used the old probe and was checked by hand.
