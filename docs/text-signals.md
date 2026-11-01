# Signals extracted from text

Where structured signals from unstructured text (a call transcript's topic, objection, sentiment and next step) are extracted, how the extraction is versioned and tested, and how a metric over model-made labels tells the agent and the user what it is ([Map #199](../../../issues/199), research [#191](../../../issues/191)).
"Stated" means read from Google's, dbt's or OpenRouter's documentation (2026-11); "measured" means run in this repo; "unverified" means neither.

## The short answer

- **Label in the warehouse, in dbt.** At work, an incremental silver model calls BigQuery's `AI.GENERATE` with an output schema over transcripts that already landed, one row per transcript and prompt version; Airflow only runs `dbt build`, as it does for every other stage.
- **Label once, never again by accident.** The model is incremental with `full_refresh: false`; each row records the prompt version, the endpoint asked for and the model version that answered; a new prompt or model is a new prompt version labelled beside the old one, never an overwrite.
- **Test labels against a golden set before a metric reads them.** Synthetic transcripts are generated from their labels, so every fixture row has a true label; a dbt test fails the build when agreement falls under a threshold agreed beforehand, and another when too many rows failed to label.
- **Say "model-derived" where the agent reads it.** The metric's description and a glossary term name the model, the prompt version and the last agreement score; the generated catalog carries them, as it carries every other description (SL-3).
- **In the lab, the model call is a recording.** The emulator cannot run `AI.GENERATE` and fakes `AI.CLASSIFY` (measured, below), and the $0.00 project may not call Vertex (`aiplatform.googleapis.com` is on `platform/gcp/free-path.yaml`'s paid list); so the same dbt model reads recorded labels on Postgres and the emulator, an opt-in target records them from an OpenRouter free model, and the BigQuery target compiles the real `AI.GENERATE` call without running it.

## The three places it could run

| Option | What it is | Verdict |
|---|---|---|
| A. In EL Factory, before landing | The extraction service calls a model per transcript and lands text and labels together | Rejected: labels become part of the source; a new prompt means re-extracting old intervals; inference sits in a service whose job is moving bytes, with its request timeouts |
| B. In dbt, through the warehouse's AI functions | An incremental model calls `AI.GENERATE` (or `AI.CLASSIFY`) over landed text | **Recommended**: the text never leaves the warehouse's governance, lineage and tests are dbt's, each row carries its own call status, and Airflow keeps orchestrating only |
| C. A separate batch job | A Cloud Run Job reads unlabelled text, calls a model, writes labels back | The fallback: when the model is not a Gemini model `AI.GENERATE` can reach, or when calls must be metered outside BigQuery; one more image, identity and deadline to run |

B follows the lab's split: extraction lands raw text (EL Factory), transformation derives everything else (dbt), and a label is a derivation of landed text.
The raw transcript stays in bronze, so a new prompt re-labels from it without touching extraction.

## The warehouse's AI functions (stated)

- [`AI.GENERATE`](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/bigqueryml-syntax-ai-generate) is a scalar function that sends a prompt to a Gemini model and returns `result` (`NULL` when the request fails or is filtered), `full_response` (the model's JSON response) and `status` (empty on success).
  An `output_schema` such as `topic STRING, objection STRING, sentiment STRING, next_step STRING` replaces `result` with typed fields; `model_params` takes any field of the `generateContent` request body except `contents`.
  It needs no remote model and, without a `connection_id`, runs with the caller's own credentials ([choose a text generation function](https://docs.cloud.google.com/bigquery/docs/choose-text-generation-function)); it reaches Gemini models only, where `AI.GENERATE_TEXT` over a remote model also reaches partner and open models.
- [`AI.CLASSIFY`](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/bigqueryml-syntax-ai-classify) picks one category (or several, `output_mode => 'multi'`) from a list, with optional descriptions and up to five examples; a failed call returns `NULL` for that row, and `max_error_ratio` fails the query when more rows than that share fail.
  It suits a single label such as sentiment; four signals from one transcript are one `AI.GENERATE` call, not four classifications.
- **The model behind a short name moves.** Without an `endpoint`, `AI.GENERATE` lets BigQuery pick "a recent stable version of Gemini" and `AI.CLASSIFY` picks the model with "the best cost to quality tradeoff"; a short name such as `gemini-3.5-flash` resolves to the `us`, `eu` or `global` endpoint.
  The response's [`modelVersion`](https://cloud.google.com/dotnet/docs/reference/Google.Cloud.AIPlatform.V1/latest/Google.Cloud.AIPlatform.V1.GenerateContentResponse) (output only) names the model that answered, and it is in `full_response`.
- **Repeating a call does not repeat its answer.** A fixed `seed` makes the model try "on a best-effort basis" to repeat a response, "deterministic output isn't guaranteed", and a low temperature gives "predictable (but not completely deterministic)" results ([content generation parameters](https://cloud-dot-devsite-v2-prod.appspot.com/vertex-ai/generative-ai/docs/multimodal/content-generation-parameters)).
- **Every call is billed in Vertex AI, per token.** The pages say inference "can be a relatively expensive operation", that Gemini 2.5 and later bill their thinking tokens (capped with `thinking_budget` or `thinking_level` in `model_params`), and that token usage "directly correlates with your Vertex AI billing" ([control costs with token quotas](https://docs.cloud.google.com/bigquery/docs/control-genai-costs)).
  Default daily quotas are 200 billion input and 20 billion output tokens per project; when one runs out mid-query, the remaining rows fail with a quota error and `max_error_ratio` decides whether the query returns the rest.

## Versioning

- **Key:** one row per `(transcript_id, prompt_version)`; dbt's [incremental](https://docs.getdbt.com/docs/build/incremental-models) `merge` on that key, selecting only transcripts without a successful label for the current prompt version, so a failed row is retried on the next run and a labelled one is never sent again.
- **No accidental re-labelling:** [`full_refresh: false`](https://docs.getdbt.com/reference/resource-configs/full_refresh) makes the model ignore `--full-refresh` (stated), so a routine rebuild cannot re-send the whole history and get different answers back.
- **Per row:** `prompt_version` (a name in the repo, bumped by hand with the prompt's text), `endpoint` (the name asked for, always set, never left to BigQuery's choice), `model_version` (from `full_response`), `labelled_at` and `status`.
- **The prompt lives in the repo**, as the macro that builds the `AI.GENERATE` call, so a change to it is a reviewed diff that also bumps `prompt_version`.
- **Re-labelling history is a deliberate step:** add the new prompt version beside the old one, label the golden set first, compare agreement, then label the history and switch the metric's filter to the new version; the old rows stay until no metric reads them.
  Its cost is the history's row count times the tokens per call (input, output and thinking) at the model's per-token price, bounded by the token quotas above; nothing in the lab measures a work price.

## Testing the labels

- **A golden set with true labels.** The synthetic generator picks each transcript's topic, objection, sentiment and next step first, then writes the text from them, so the fixture knows every true label; a few hand-written hard cases (two topics, sarcasm, no next step) join it as a seed.
- **Agreement, per signal.** A test model compares each signal's labels with the golden labels: accuracy, and [Cohen's kappa](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.cohen_kappa_score.html) for agreement beyond chance; a dbt test fails the build when either falls below a threshold written next to the prompt version before the comparison runs.
- **Failed calls.** A test fails when the share of rows with a non-empty `status` passes a limit, the dbt counterpart of `max_error_ratio`.
- **Allowed values.** `accepted_values` on each label column, as on every code column agents read (#157), so a label the prompt does not allow fails the build instead of reaching a group-by.
- **Drift.** A new `model_version` is the drift no data shows: a test fails until the golden set has been scored on it; label shares per week against the trailing weeks are the drift data shows, written to an `ops` table the monitoring exporter reads, as source freshness does (#130), and alerted on there.

## Telling the agent and the user

- The metric's description says it is model-derived and names the endpoint, the prompt version and the last agreement score (for example "Model-derived: labelled by gemini-3.5-flash, prompt v2, kappa 0.86 on the golden set, 2026-11-01").
  The agent catalog, the warehouse comments and a data agent's context are generated from descriptions (SL-3), so every consumer gets the sentence without a second copy.
- A glossary term "model-derived label" says what such a metric is and how it differs from a source column; `prompt_version` is a dimension, so an answer can be filtered to one version.
- `scripts/check_standard.py` can require the sentence: a column marked `meta: {derived_by: model}` makes any metric over it fail the standard without "Model-derived" in its description.
- No confidence dimension: the functions return a label and a status, not a calibrated probability, and a model's own stated confidence is not one (unverified for these models: not measured here).

## The lab

**The emulator (measured, `ghcr.io/goccy/bigquery-emulator:0.8.1`, the Compose image):**

| Query | Result |
|---|---|
| `SELECT AI.GENERATE('hello', endpoint => 'gemini-2.5-flash').result` | `Function not found: AI.GENERATE` |
| `SELECT * FROM ML.GENERATE_TEXT(MODEL d.m, (SELECT 'hi' AS prompt))` | `Table-valued function not found: ML.GENERATE_TEXT` |
| `SELECT * FROM AI.GENERATE_TABLE(MODEL d.m, ...)` | `Table-valued function not found: AI.GENERATE_TABLE` |
| `CREATE MODEL d.m REMOTE WITH CONNECTION ...` | `Keyword REMOTE is not supported` |
| `SELECT AI.CLASSIFY('the price is too high', ['price','timing','other'])` | `price` |
| `SELECT AI.CLASSIFY('the call was short and they asked about delivery', ['price','timing','other'])` | `price` |
| `SELECT AI.CLASSIFY('x', ['zzz','yyy'])` | `zzz` |
| `SELECT AI.SCORE('rate this')` | `0.5` |

`AI.CLASSIFY` returns the first category whatever the input, and `AI.SCORE` a constant: a model built on them passes on the emulator with wrong labels, which only a golden-set test would catch.
So the emulator target must take the recorded path, like Postgres.

**The shape that fits the lab:**
- A macro dispatched per adapter builds the label call: on the `bigquery` target, the real `AI.GENERATE` with its output schema, compiled by `make bigquery-check` and never run (the $0.00 project; `aiplatform.googleapis.com` is on `platform/gcp/free-path.yaml`'s paid list); on `dev` and `bigquery_emulator`, a join to recorded labels keyed by transcript hash, prompt version and model.
- An opt-in target records labels for the fixture's transcripts from an OpenRouter free model, refusing an id without `:free` as the semantic agent's model seam does, and writes the response's model name per row; unit tests and `make check` never call a model.
- The free budget bounds the fixture: OpenRouter's free models allow 20 requests a minute and 50 a day below 10 purchased credits, 1,000 a day above ([limits](https://openrouter.ai/docs/api/reference/limits), stated); one call per transcript keeps a 40-transcript fixture inside one day's quota, and a spent quota stops the recording and keeps what it has, as `make agent-eval` does.
- Airflow does nothing new: the domain's `<pipeline>_elt` DAG lands transcripts through EL Factory and runs the dbt stages (SL-8).

## Built in the lab ([#241](../../../issues/241), semantic/PLAN.md SL-18)

The call-transcripts domain follows the shape above:
- EL Factory's `synthetic/call_transcripts` lands text only, written from labels it picks first; `call_transcripts_elt` runs it on the shared ELT pattern.
- `dbt_project.yml`'s `call_label_prompt` holds the prompt, its version (`v1`), the endpoint (`gemini-3.5-flash`) and the thresholds per signal, written before the first comparison.
- `macros/call_labels.sql` builds the label call: `AI.GENERATE` on a BigQuery target, compiled by `make bigquery-check`; recorded answers on Postgres and the emulator.
- `slv_call_transcript_labels` and `slv_call_golden_labels` are incremental with `full_refresh: false`; `slv_call_label_agreement` scores each version; `dbt build` fails below a threshold, above the failed-call share or on a label outside its values.
- The metrics `calls_labelled`, `calls_with_objection`, `positive_calls`, `objection_rate` and `positive_sentiment_share` start "Model-derived", which `check_standard.py` enforces for any metric over a `derived_by: model` column; the glossary term "Model-derived label" explains them.

**Measured on the fixture** (2026-11-01, `make record-call-labels` with `nvidia/nemotron-3.5-super-vl:free`, 14 requests for 15 golden calls, two sharing a text):

| Signal | Accuracy | Kappa | Thresholds (accuracy, kappa) |
|---|---|---|---|
| topic | 1.00 | 1.00 | 0.8, 0.7 |
| objection | 0.87 | 0.76 | 0.8, 0.6 |
| sentiment | 0.93 | 0.90 | 0.7, 0.5 |
| next_step | 0.87 | 0.80 | 0.8, 0.7 |

Six of the seven misses are on the three hand-written hard cases: the two-topic call got an objection (timing) and a neutral mood, the sarcastic return was read as negative but its escalation as a follow-up call, and the competitor comparison as a price objection; one generated call's escalation was also read as a follow-up call.
The scores are one recording on 15 calls, not a model comparison.

## Unverified

- `AI.GENERATE` on real BigQuery: nothing here ran it, its `output_schema` included; the $0.00 project cannot.
- Whether `full_response` carries `modelVersion` through `AI.GENERATE` as the Vertex response does: stated for the Vertex API, not seen through BigQuery.
- How stable a free OpenRouter model's labels are between two recordings: not measured; the golden set would show it.
- Work prices per transcript: not computed; they depend on the model, the transcript length and the thinking budget.
- Thresholds for kappa and accuracy: a choice per signal, made before the first comparison; none is recommended here.
