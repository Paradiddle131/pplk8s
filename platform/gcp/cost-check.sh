#!/usr/bin/env bash
# `make gcp-cost-check` (#233): prove from the billing export that the lab project has cost nothing this
# month, so a mistake surfaces the same day; run it before and after every gcp- step that changes the project.
# Exit 0: $0.00 after credits. Exit 1: a cost, listed by service and SKU. Exit 3: unknown (no export rows
# yet, or the query failed): treat it as "not proven" and do no live GCP work.
# The export (dataset $GCP_BILLING_DATASET, default billing_export) lags by hours: a pass proves the
# spend up to the export's last load, which it prints. Its own query reads a few MB under a 100 MB cap.
set -euo pipefail
: "${GCP_PROJECT:?GCP_PROJECT is unset: the gcp- targets act on the lab project and need its id (platform/gcp/README.md)}"
dataset=${GCP_BILLING_DATASET:-billing_export}
cap=104857600

table=$(bq ls --format=json --max_results=100 "$GCP_PROJECT:$dataset" 2>/dev/null |
  python3 -c 'import json,sys; print(next((t["tableReference"]["tableId"] for t in json.loads(sys.stdin.read().strip() or "[]") if t["tableReference"]["tableId"].startswith("gcp_billing_export_v1_")), ""))' || true)
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
if ! rows=$(bq query --quiet --format=csv --max_rows=1000 --maximum_bytes_billed="$cap" "$sql"); then
  echo "gcp-cost-check: UNKNOWN: the billing export query failed" >&2
  exit 3
fi

ROWS=$rows python3 - "$GCP_PROJECT" <<'PY'
import csv, io, os, sys
project = sys.argv[1]
rows = list(csv.DictReader(io.StringIO(os.environ["ROWS"])))
total = float(rows[0]["month_total"]) if rows else 0.0
until = rows[0]["exported_until"] if rows else "no rows this month"
costly = [r for r in rows if float(r["net"]) > 0]
if total > 0 or costly:  # strict: any SKU above zero, even below a cent, stops the work
    print(f"gcp-cost-check: FAIL: {project} has a cost above zero this month (${total:.2f} rounded) (export until {until}):", file=sys.stderr)
    for r in costly:
        print(f"  {r['net']:>12}  {r['service']} / {r['sku']}", file=sys.stderr)
    sys.exit(1)
print(f"gcp-cost-check: ok: {project} has cost $0.00 this month after credits (export until {until}, {len(rows)} SKUs seen)")
PY
