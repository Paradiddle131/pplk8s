# The agent-ready warehouse standard

What a dbt project keeps so that LLM agents read its warehouse correctly: where each layer lives, how models are named, what every description says, which layer agents read, and where each calculated field lives ([`semantic/PLAN.md`](../semantic/PLAN.md) U2, SL-3, SL-4).
A team adopts it as written; `dbt/scripts/check_standard.py` fails a parse that strays from the rules it can see.
How the words reach BigQuery and a native data agent is in [`semantic-layer-on-bigquery.md`](semantic-layer-on-bigquery.md); this page is the rule book.

## Datasets per layer

Each layer is one folder under `dbt/models/` and one schema in the warehouse, which is one dataset on BigQuery.

| Layer | Dataset | Model prefix | Holds | Agents read it |
|---|---|---|---|---|
| bronze | `bronze` | `brz_` | The landing tables cast, one to one, every run and metadata column kept | no |
| silver | `silver` | `slv_` | One row per natural key, latest load wins; a snapshot's history of a source that overwrites its rows (`snp_`); the semantic models sit here | only through a metric |
| gold | `gold` | `gld_` | Business aggregates at a stated grain | yes, `access: public` |
| exposed | `exposed` | `exp_` | What a consumer reads: gold joined or reshaped for one use | yes, `access: public`, unless it holds personal data |
| semantic | `semantic` | none | MetricFlow's `time_spine`, `metrics` (one row per metric) and `glossary` (one row per term) | `metrics` and `glossary` |
| legacy | `legacy` | `lgc_` | During a migration only: what a consumer read before the layers, rebuilt as it was, in the consumer's column names | no |
| migration | `migration` | none | During a migration only: `parity`, each consumer's legacy table against its new model ([`migration-rehearsal.md`](migration-rehearsal.md)) | no |

A model builds in its layer's dataset, never in one it chooses (`generate_schema_name` uses the layer verbatim).
The landing dataset (`ds_source`) belongs to the extraction service; dbt reads it only through `source()` in bronze.

## Naming

- A model in bronze, silver, gold, exposed or legacy starts with its layer's prefix, and its relation is the name without it: `gld_daily_sales` builds `gold.daily_sales` (`alias`).
  The prefix keeps names unique across the project; the dataset already says the layer, so the table does not repeat it.
  An ephemeral model builds no relation and needs only the prefix.
- A dbt snapshot starts with `snp_` and builds in silver, its relation named for what it keeps (`snp_candidate_stages` builds `silver.candidate_stage_snapshots`); a silver model renames its columns for the semantic layer (semantic/PLAN.md SL-17).
- A semantic-stage or migration model carries no layer prefix; its relation names what it holds (`time_spine`, `metrics`, `glossary`, `parity`).
- Models, columns, semantic models, entities, dimensions and metrics are lower snake case; a metadata column the loader adds starts with an underscore (`_loaded_at`, `_run_id`).
- A metric is the quantity with its unit as a suffix (`revenue_eur`, `cost_per_lead_eur`); a count names what it counts, and how when there is more than one way (`leads`, `orders_total`, `orders_cancelled`, `customers_distinct`); a ratio of two counts ends in `_rate`.
- A dimension is asked for as `<entity>__<dimension>` (`order__status`, `customer__country`), and time as `metric_time__day` (or `__week`, `__month`, `__year`).
- A grain in the name says how many rows a key has: `_daily` is one row per day and whatever else the description names.

## What every description says

A description is written for a reader who sees only it: an agent choosing a table, or a person reading BigQuery's column list.

| Thing | Says | Example |
|---|---|---|
| Model | Its grain (one row per what), the time zone of its dates, and the relation it builds | `One row per order_date (UTC). Alias gold.daily_sales.` |
| Column | What the value is, its unit, and what is in or out of it | `Sum of amount for non-cancelled orders.` |
| Key column | That it is the key, and of what | `Natural key.` |
| Code column | The codes it takes, also declared as an `accepted_values` test when the set is fixed | `ISO-2 country code of the customer (NL, TR, GB, DE, FR, US).` |
| Semantic model, entity, dimension | What the rows are, and what grouping by it means | `UTC date the customer signed up; group by its month for signup cohorts.` |
| Metric `label` | The business term in plain words, the unit in brackets | `Net revenue (EUR)` |
| Metric `description` | What it counts or sums, what it leaves out, and how a ratio divides | `Ad spend divided by bookings over the whole period asked (total spend over total bookings, never an average of daily ratios); the one definition of cost per conversion.` |
| Glossary term | What the term means, what it is not (the term it is confused with), and the metrics and dimensions it maps to | `Market`: `The ISO-2 country a campaign targets. It can differ from a lead's own country and a customer's country, …` with `dimensions: [campaign__market]` |

Every model that builds a relation has a description; every public model also describes every column; every semantic model describes itself, its entities, dimensions and measures; every metric has a description and a label.
Bronze and silver columns may stay undescribed: no agent reads them, and their meaning reaches agents through the metrics.
A categorical dimension whose column takes a fixed set of codes declares them with `accepted_values`: the catalog lists them under the dimension, and the metric tools refuse a filter value outside them instead of answering a guessed value with a confident zero.
A dimension with an open set (a campaign's name) declares none, and any value passes.
Declaring values on a column that already holds rows covers those rows too: silver maps each older code to a declared one (bronze keeps the raw value), so the test holds over all history and every value a group-by shows is one the filter accepts.

## The glossary

A business term that is not a metric (a cohort, a channel, a market, what a conversion is) is a glossary term, kept in `config.meta.glossary` on the model that holds the concept, usually the silver model under its semantic model:

```yaml
- name: slv_campaigns
  config:
    meta:
      glossary:
        - term: Market
          description: The ISO-2 country a campaign targets. …
          synonyms: [target market, campaign country]
          metrics: [ad_spend_eur, leads, bookings]
          dimensions: [campaign__market]
```

A term maps to at least one metric or dimension, names metrics by their name and dimensions as `<entity>__<dimension>`, and never repeats a metric: a metric's label and description are already its glossary entry, and a second definition is how two agents come to disagree.
dbt has no glossary node; `meta` on the model keeps the term beside the columns it explains, in the YAML the catalog already reads.

## Which layer agents read

Gold and exposed models, and only they, are `access: public` in the `analytics` group (`dbt/models/groups.yml`); bronze, silver and the semantic stage are `protected` (SL-4).
A column of personal data carries `meta: {pii: true}` from bronze on; a gold or exposed model holding one is `protected` instead, so it stays out of the agent catalog, and its consumer is an automation or a person, never an agent (`exp_outreach_activation`, semantic/PLAN.md SL-16).
No semantic model sits on a model with personal data, so no metric or dimension can name a personal column.
A public model enforces a contract (`contract: {enforced: true}`, set per layer in `dbt_project.yml`) and gives every column a `data_type`, so a change that renames, drops, adds or retypes a column an agent relies on fails `dbt build` before it replaces the table, instead of leaving the agent's context stale.
A type is spelled so both warehouses accept it: `date`, `numeric`, `bigint` and `integer` as they are, a string as the file's `text` anchor (`text` on Postgres, `string` on BigQuery).
A view gets the same name and type check, but no constraints; the standard asks for none.
The agent catalog lists exactly the public models and the metrics (`dbt/target/catalog/agent.json`), and each agent's read-only warehouse role reaches only its layers: `agent_metrics` silver and semantic through MetricFlow, `agent_sql` gold and exposed.
At work that is a dataset-level read grant per agent identity.

## Where each calculated field lives

Every calculated field is defined once, as a metric, on a semantic model over silver (R1, SL-1):
- a sum, count or distinct count over one silver model is a simple metric in that model's YAML (`dbt/models/silver/schema.yml`);
- a ratio or a combination of metrics is a ratio or derived metric, in the model's YAML when its inputs share it, in `dbt/models/semantic/semantic.yml` when they do not.

Gold and exposed keep their hand-written aggregates as the parity oracle (`make semantic-check` asserts the metrics equal them, and a `hop_metric_<metric>_to_<model>` test on the column fails `dbt build` when they drift, semantic/PLAN.md SL-9); a new number an agent should answer becomes a metric first, and a gold column only when a consumer needs the table.
A ratio is never stored per day for agents to average: the metric divides the totals for whatever period and grouping is asked.

## How the words reach BigQuery and Knowledge Catalog

| Words | Reach | Through |
|---|---|---|
| Public model and column descriptions | BigQuery table and column descriptions, which Knowledge Catalog shows | `persist_docs` on gold and exposed, written as the models build |
| Metric labels and descriptions | `semantic.metrics`, and the data agent's glossary | `semantic_metrics.sql` from dbt's graph; `build_catalog.py` |
| Glossary terms | `semantic.glossary`, the agent catalog's `glossary` (the lab agent's `list_metrics`), and the data agent's glossary with the mapping in its description | `semantic_glossary.sql` from dbt's graph; `build_catalog.py` |
| Semantic models, entities and dimensions | The data agent's tables, fields, aggregations and relationships | `build_catalog.py` (`system_instruction.yaml`) |
| Each metric's compiled SQL | The data agent's verified queries | `build_catalog.py` (`example_queries.json`) |
| Saved queries (`models/semantic/saved_queries.yml`): a recurring question with its metrics, group-bys and filters | The data agent's verified queries, with the question as asked; the lab agent's `list_metrics`, run by name through `query_metrics` | `build_catalog.py` (`example_queries.json`, `agent.json`) |

[`semantic-layer-on-bigquery.md`](semantic-layer-on-bigquery.md) has the mapping in full, with what is measured, stated and unverified.

## The check

`dbt/scripts/check_standard.py` reads the manifests `dbt parse` writes, with no warehouse, and fails on:
- a model outside a layer folder, building outside its layer's dataset, without its layer's prefix, or whose relation is not its name without the prefix;
- a name that is not snake case: model, column, semantic model, entity, dimension, measure or metric;
- a public model outside gold and exposed or outside the `analytics` group, a gold or exposed model that is not public unless it holds a column marked `meta: {pii: true}`, a public model that holds one, or a semantic model off silver;
- a public model without an enforced contract, or a public model's column without a `data_type`;
- a missing description on any of the things the rules above name, or a metric without a label;
- a metric over a model-derived column (`meta: {derived_by: model}`, a label a language model read out of text), directly or through its input metrics, whose description does not start with "Model-derived" (semantic/PLAN.md SL-18).

It runs in `make dbt-validate` and in the dbt image build; `make semantic-check` shows it failing on an undescribed metric, on a metric over model-derived labels that does not say so, and on an unprefixed, undescribed, untyped gold model with a personal-data column, and `dbt build` failing on a public model whose SQL renames or retypes a contracted column.
`check_catalog.py` (`make dbt-catalog`) checks the catalog artefacts built from the same manifests, glossary terms included (an unknown metric, a dimension none of the term's metrics has, a term repeating a metric), and `make catalog-check` that every gold and exposed column has its comment in the warehouse.

A column the SQL selects but the YAML does not name is absent from the manifest, so the parse cannot see it; the contract can, and the build fails on it.

A script, not `dbt-project-evaluator`: the package builds its rules as models and tests in the warehouse, its naming rules default to staging, intermediate and marts models, and no rule covers metrics or semantic models (stated, its [rules page](https://dbt-labs.github.io/dbt-project-evaluator/latest/rules/), 2026-10).
Its modelling and governance rules (fan-out, public models without contracts) are worth a look when the project grows; this check stays the one for the agent-facing words.
