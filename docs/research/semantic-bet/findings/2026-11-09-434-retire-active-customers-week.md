# Retiring `hard_active_customers_week` (#434)

Written 2026-11-09T10:39Z, under RULE.md § Retiring a defective case; part of the fairness epic #424.

## The case

`hard_active_customers_week` (sets `hard` and `hard-v2`, byte-identical in both): "How many active customers did we have in the week up to 3 October 2026?", an `ambiguous` turn over `customers_distinct` and `engaged_customers_7d`.
Its expected SQL gives two numbers, 10 (distinct customers with a non-cancelled order, 27 September to 3 October) and 9 (distinct customers with any site or CRM action in those days); `expected.json` holds `[[10.0], [9.0]]` for both sets.
As an `ambiguous` turn it is right only when the answer asks which meaning or gives both numbers.

## What is wrong (class: expected_sql)

- The lab's governed layer names `customers_distinct` "Active customers" (`dbt/models/silver/schema.yml`, the metric's `label`), and its glossary says an engaged customer "is not an active customer, which counts customers who placed a non-cancelled order" (the `Engaged customer` term in the same file).
- So the governed definitions give "active customers" one reading, 10; a setup that follows them, as every MetricFlow setup and `native-mcp` (quoting the definition) did, scores wrong.
- 9 and 10 are also small whole numbers an answer can carry by chance (§ Changes since freezing, #382).
- The test is wrong whatever any setup does: the case asks for an ambiguity the governed layer resolves.

## Reproduction

`expected.json` (read from the fixture by `bet_eval --write-expected`) gives 10 and 9; the metric's label and the glossary line above are in the repo at this commit.
Scored as it stood (`scored-runs.jsonl` before the retirement): on `hard` 90 wrong, 3 right, 2 declined; on `hard-v2` 99 wrong, 3 right, 2 declined.

## Confirmations

- The agent: the case is defective (expected_sql), judged on the case and the governed definitions, not on which setup passed.
- The owner, 2026-11-09, in a session (recorded on #434): "retire the case".

## What changes

A `case` row in `redacted.jsonl`, a row in RULE.md's register; the runs stay in the logs, every score leaves the case out from now on, and the report shows only scored questions.
