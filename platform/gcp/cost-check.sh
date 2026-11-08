#!/usr/bin/env bash
# `make gcp-cost-check` (#233): prove from the billing export that the lab project has cost nothing this
# month, so a mistake surfaces the same day; run it before and after every gcp- step that changes the project.
# Exit 0: $0.00 after credits, or a month's total under GCP_COST_TOLERANCE_USD (default 1.00), whose costly
# SKUs it lists: the owner accepts incidental charges such as a few cents of registry egress (#338; 0 restores
# the strict rule). Exit 1: a total at or above the tolerance, listed by service and SKU. Exit 3: unknown (no
# export table, or no rows for the project this month yet; bq failed, or the query failed; a malformed
# tolerance): treat it as "not proven" and do no live GCP work.
# The export (dataset $GCP_BILLING_DATASET, default billing_export) lags by hours: a pass proves the
# spend up to the export's last load, which it prints. Its own query reads a few MB under a 100 MB cap.
set -euo pipefail
: "${GCP_PROJECT:?GCP_PROJECT is unset: the gcp- targets act on the lab project and need its id (platform/gcp/README.md)}"
dataset=${GCP_BILLING_DATASET:-billing_export}
cap=104857600
tolerance=${GCP_COST_TOLERANCE_USD:-1.00}
if ! [[ "$tolerance" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
  echo "gcp-cost-check: UNKNOWN: GCP_COST_TOLERANCE_USD must be a non-negative number of dollars, got '$tolerance'" >&2
  exit 3
fi

# A missing dataset is the no-export case; any other bq failure (a broken install, no credentials) is
# reported as itself, so it is not mistaken for the export's lag (#271). bq prints its own errors
# ("BigQuery error in ls operation: Not found: Dataset ...") on stdout and a crash's traceback on stderr.
err=$(mktemp)
trap 'rm -f "$err"' EXIT
if ! listing=$(bq ls --format=json --max_results=100 "$GCP_PROJECT:$dataset" 2>"$err"); then
  if grep -q "Not found: Dataset" <<<"$listing"; then
    listing="[]"
  else
    echo "gcp-cost-check: UNKNOWN: bq failed: $(printf '%s\n%s\n' "$listing" "$(cat "$err")" | grep -v '^[[:space:]]*$' | tail -n 5 | tr '\n' ' ' | sed 's/ *$//')" >&2
    exit 3
  fi
fi
table=$(LISTING=$listing python3 -c 'import json,os; print(next((t["tableReference"]["tableId"] for t in json.loads(os.environ["LISTING"].strip() or "[]") if t["tableReference"]["tableId"].startswith("gcp_billing_export_v1_")), ""))')
if [ -z "$table" ]; then
  echo "gcp-cost-check: UNKNOWN: no gcp_billing_export_v1_* table in $GCP_PROJECT:$dataset yet (the first rows take about a day after the export is set up)" >&2
  exit 3
fi

sql="WITH c AS (
  SELECT service.description AS service, sku.description AS sku,
         SUM(cost) + SUM(IFNULL((SELECT SUM(x.amount) FROM UNNEST(credits) x), 0)) AS net
  FROM \`$GCP_PROJECT.$dataset.$table\`
  WHERE invoice.month = FORMAT_DATE('%Y%m', CURRENT_DATE()) AND project.id = '$GCP_PROJECT'
  GROUP BY 1, 2)
SELECT service, sku, FORMAT('%.6f', net) AS net,
       FORMAT('%.2f', SUM(net) OVER ()) AS month_total,
       (SELECT FORMAT_TIMESTAMP('%FT%H:%MZ', MAX(export_time)) FROM \`$GCP_PROJECT.$dataset.$table\`) AS exported_until
FROM c ORDER BY net DESC"
# A spent daily query fence refuses this query too (#369): say so, since it resets at 00:00 Pacific and the
# export is fine. bq prints "Custom quota exceeded: Your usage exceeded the custom quota for QueryUsagePerDay".
if ! rows=$(bq query --quiet --format=csv --max_rows=1000 --maximum_bytes_billed="$cap" "$sql" 2>"$err"); then
  said=$(printf '%s\n%s\n' "$rows" "$(cat "$err")")
  fence=$(grep -o 'Custom quota exceeded[^.]*\(QueryUsagePerDay\|QueryUsagePerUserPerDay\)' <<<"$said" | grep -o 'QueryUsagePer[A-Za-z]*' | head -n 1 || true)
  if [ -n "$fence" ]; then
    echo "gcp-cost-check: UNKNOWN: BigQuery's daily query fence ($fence, free-path.yaml caps.bigquery_query_mib_per_day) is spent, so the billing export query was refused: wait for its reset at 00:00 Pacific; the export is not broken" >&2
  else
    echo "gcp-cost-check: UNKNOWN: the billing export query failed: $(grep -v '^[[:space:]]*$' <<<"$said" | tail -n 5 | tr '\n' ' ' | sed 's/ *$//')" >&2
  fi
  exit 3
fi

ROWS=$rows python3 - "$GCP_PROJECT" "$tolerance" <<'PY'
import csv, io, os, sys
project, tolerance = sys.argv[1], float(sys.argv[2])
rows = list(csv.DictReader(io.StringIO(os.environ["ROWS"])))
if not rows:  # an empty export is its lag, not $0.00: nothing is proven until its first rows land
    print(f"gcp-cost-check: UNKNOWN: no billing export rows for {project} this month yet (the first rows take about a day after the export is set up)", file=sys.stderr)
    sys.exit(3)
# The total from the SKUs' six decimals, not the query's month_total, which is rounded to cents.
total = sum(float(r["net"]) for r in rows)
until = rows[0]["exported_until"]
costly = [r for r in rows if float(r["net"]) > 0]
if total <= 0 and not costly:
    print(f"gcp-cost-check: ok: {project} has cost $0.00 this month after credits (export until {until}, {len(rows)} SKUs seen)")
    sys.exit(0)
if total < tolerance:  # the owner's accepted incidental charges (#338): pass, and name them every time
    print(f"gcp-cost-check: ok: {project} has cost ${total:.6f} this month, under the accepted ${tolerance:.2f} (export until {until}):")
    for r in costly:
        print(f"  {r['net']:>12}  {r['service']} / {r['sku']}")
    sys.exit(0)
print(f"gcp-cost-check: FAIL: {project} has cost ${total:.6f} this month, at or above the accepted ${tolerance:.2f} (export until {until}):", file=sys.stderr)
for r in costly:
    print(f"  {r['net']:>12}  {r['service']} / {r['sku']}", file=sys.stderr)
sys.exit(1)
PY
