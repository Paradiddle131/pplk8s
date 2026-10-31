# Migrating consumers to the new layers, one at a time

How a team moves the dashboards, agents and automations that read its old tables onto the new layers without a day when numbers jump, rehearsed in the lab on synthetic data ([`semantic/PLAN.md`](../semantic/PLAN.md) U5, SL-11).
The old tables are what scheduled queries and routines wrote; where those belong once dbt runs is the companion question of [#141](../../../issues/141).
`make migration-check` runs every step below on the dev fixture.

## The plan

1. **Build next to the old.**
   The new layers build in their own datasets; the old tables keep being written, unchanged, on their old schedule.
   Nothing reads the new layers yet, so building them changes no number anyone sees.
2. **List the consumers.**
   One dbt [exposure](https://docs.getdbt.com/docs/build/exposures) per consumer: its type, its owner, and in `depends_on` the one relation it reads today.
   `meta.migration` names its old table, the model that replaces it, and its kind: dashboard, agent or automation.
3. **Compare.**
   `migration.parity` puts each consumer's old table beside its new model, in the consumer's own column names, and counts per field the keys on either side and the keys that differ.
   It reuses the layer hops' comparison (SL-9), so a key on one side only, a doubled key and a changed value all count.
4. **Resolve every difference before the switch.**
   A difference is either a fault in the new layers, fixed there, or a fault in the old table, which the consumer's owner accepts on its exposure (`accepted: {<field>: <why>}`) after seeing the numbers move.
   The tolerance is agreed before the comparison, never after; the lab's is zero.
5. **Switch consumers in order: dashboards, then agents, then automations.**
   A dashboard is read by a person who notices a jump; an agent repeats a number without noticing; an automation acts on it.
   Each switch is one change: the consumer is repointed in its own tool, and its exposure's `depends_on` names the new model.
6. **The gate.**
   The singular test `consumers_switch_on_parity` fails `dbt build` when a consumer reads its new model while a field differs unaccepted, while a consumer of an earlier kind still reads its old table, or while `migration.parity` has no row for it.
   The build that would publish the switch is the one that refuses it.
7. **Roll back** by pointing the consumer and its exposure at the old table again: the old table is still current, and the gate never blocks a consumer on its old table.
8. **Retire the old table** once no consumer has read it for a full cycle of its schedule: stop the job that writes it, then drop it, its legacy model and its rows in `migration.parity`.

## The lab's rehearsal

Three tables built the old way, straight off silver with their consumers' column names, sit in the `legacy` dataset (`dbt/models/legacy/`).
One calculated field is computed differently: `legacy.country_sales.revenue` sums every order, cancelled ones included, where the metric `revenue_eur` and `exposed.sales_by_country_daily` leave them out.

| Consumer | Kind | Old table | New model | Parity on the fixture | Reads |
|---|---|---|---|---|---|
| `finance_dashboard` | dashboard | `legacy.daily_net_sales` | `exposed.net_sales_daily` | every field matches on 2 days | the new model: switched |
| `sales_agent` | agent | `legacy.country_sales` | `exposed.sales_by_country_daily` | `revenue` differs on 4 of 12 country-days, the ones with a cancelled order | its old table: waits for its owner to accept the difference |
| `marketing_automation` | automation | `legacy.channel_daily` | `exposed.channel_performance_daily` | every field matches on 6 channel-days | its old table: waits for the agent |

`make migration-check` builds them, asserts the report above, and then, in a copy of `dbt/`, shows the gate:
- switching the agent fails on `revenue differs on 4 keys, not accepted`;
- the same switch with the difference accepted passes;
- switching the automation before the agent fails on `switched before agent sales_agent`;
- rolling the dashboard back to its old table passes.

No DAG builds `legacy` or `migration`; `dbt build --select +tag:migration` does.
A consumer here is an exposure, not a running dashboard or agent: the lab has none to repoint, so the switch is the exposure's half of the change.

## At work, on BigQuery

- The old tables stay where the scheduled queries write them; a `legacy` model can be a [source](https://docs.getdbt.com/docs/build/sources) instead of a rebuild, since the point is to read what consumers read today.
- The parity model and the gate run on a BigQuery engine unchanged: `make bigquery-emulator-check` builds them on the emulator and gets the same 13 rows of `migration.parity` as Postgres (measured); real BigQuery is unverified.
- Repointing a consumer is per tool: a Looker Studio data source, the tables named in a data agent's authored context, the query of a scheduled automation.
- dbt docs draws every exposure under the model it reads, so the lineage graph is the switch board: who is on the old table and who is on the new.
