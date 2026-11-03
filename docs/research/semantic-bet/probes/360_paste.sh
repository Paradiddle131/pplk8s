# bet-kc-max (#360): a Knowledge Catalog business glossary linked to the columns of bet_kcmax.
# Paste into Cloud Shell on project pplk8s-lab-001. Safe to paste again: what exists answers 409 and is kept.
# Docs: https://docs.cloud.google.com/knowledge-catalog/docs/manage-glossaries (glossary, terms, column links,
#   REST as the page gives it, read 2026-11-03); https://cloud.google.com/bigquery/pricing#free (table copies free).
bet360() {
P=pplk8s-lab-001; L=us; G=bet-kc-max; D=bet_kcmax
NUM=$(gcloud projects describe $P --format='value(projectNumber)')
API=https://dataplex.googleapis.com/v1
TOKEN=$(gcloud auth print-access-token)
# The docs' gcurl, as a function that prints the HTTP status and keeps the body in ~/bet-360/last.json.
gcurl() { curl -sS -o ~/bet-360/last.json -w "%{http_code}" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" "$@"; }
mkdir -p ~/bet-360 && cd ~/bet-360
gcloud storage cp gs://$P-semantic-bet/bet-360-plan.json plan.json
echo '282a7461a0476dfff0f5451388c1d6b7a33e0802e2e419fbcbc692013abf6fd3  plan.json' | sha256sum -c - || { echo 'plan.json changed: stop'; return 1; }
# 1. The copies the links point at (BigQuery copy jobs are free; only the copied bytes' storage counts).
bq --location=US mk --dataset $P:$D 2>/dev/null || true
for t in $(jq -r '.tables[]' plan.json); do bq cp -n $P:silver.$t $P:$D.$t >/dev/null 2>&1 || true; done
for t in $(jq -r '.tables[]' plan.json); do
  E=projects/$NUM/locations/$L/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/$P/datasets/$D/tables/$t
  for i in $(seq 1 30); do c=$(gcurl "$API/projects/$P/locations/$L:lookupEntry?entry=$E"); [ "$c" = 200 ] && break; sleep 10; done
  echo "entry $D.$t $c"
done
TOKEN=$(gcloud auth print-access-token)
# 2. The glossary (a long-running operation), then wait until it reads back.
c=$(gcurl -X POST "$API/projects/$P/locations/$L/glossaries?glossary_id=$G" --data "$(jq -c '.glossary|{displayName,description}' plan.json)"); echo "glossary $c"; [ "$c" = 200 ] || [ "$c" = 409 ] || cat last.json
for i in $(seq 1 30); do c=$(gcurl "$API/projects/$P/locations/$L/glossaries/$G"); [ "$c" = 200 ] && break; sleep 5; done
TOKEN=$(gcloud auth print-access-token)
# 3. One term per metric and per business term.
jq -c '.terms[]' plan.json | while read -r t; do
  id=$(jq -r .id <<<"$t")
  c=$(gcurl -X POST "$API/projects/$P/locations/$L/glossaries/$G/terms?term_id=$id" --data "$(jq -c --arg p "projects/$P/locations/$L/glossaries/$G" '{displayName,description,parent:$p}' <<<"$t")")
  echo "term $id $c"; case $c in 200|409) ;; *) head -c 300 last.json; echo;; esac
done
TOKEN=$(gcloud auth print-access-token)
# 4. Each term linked to the columns it reads (a definition entry link from the table's column to the term).
jq -c '.links[]' plan.json | while read -r k; do
  id=$(jq -r .id <<<"$k"); t=$(jq -r .table <<<"$k"); col=$(jq -r .column <<<"$k"); term=$(jq -r .term <<<"$k")
  body=$(jq -nc --arg s "projects/$NUM/locations/$L/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/$P/datasets/$D/tables/$t" \
    --arg path "Schema.$col" --arg g "projects/$NUM/locations/$L/entryGroups/@dataplex/entries/projects/$NUM/locations/$L/glossaries/$G/terms/$term" \
    '{entry_link_type:"projects/dataplex-types/locations/global/entryLinkTypes/definition",entry_references:[{name:$s,path:$path,type:"SOURCE"},{name:$g,type:"TARGET"}]}')
  for i in 1 2 3 4 5 6; do c=$(gcurl -X POST "$API/projects/$NUM/locations/$L/entryGroups/@bigquery/entryLinks?entry_link_id=$id" --data "$body"); case $c in 200|409) break;; esac; sleep 10; done
  echo "link $t.$col -> $term $c"; case $c in 200|409) ;; *) head -c 300 last.json >&2; echo >&2;; esac
done | tee links.log | awk '{print $NF}' | sort | uniq -c
echo "done: $(jq '.terms|length' plan.json) terms, $(jq '.links|length' plan.json) links; tell the agent 'kc-max pasted'"
}
bet360
