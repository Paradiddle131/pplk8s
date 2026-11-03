#!/usr/bin/env bash
# What it measures: whether the BigQuery emulator the lab uses (ghcr.io/goccy/bigquery-emulator:0.8.1) accepts
# probes/329_bet_shaped.sql's table functions, and what each returns over a few hand-made silver rows whose
# right answers are known (in the comments below): a check of the hand-written SQL, not of BigQuery itself.
# How to run (from the repo root): bash docs/research/semantic-bet/probes/329_emulator_check.sh
# Offline: a throwaway emulator container on 127.0.0.1:9051, removed at the end.
set -euo pipefail

SQL="$(dirname "$0")/329_bet_shaped.sql"
PORT=9051
docker rm -f bet-bq-emu >/dev/null 2>&1 || true
docker run -d --rm --name bet-bq-emu -p 127.0.0.1:$PORT:9050 ghcr.io/goccy/bigquery-emulator:0.8.1 \
  --project=pplk8s-lab --port=9050 --grpc-port=9060 >/dev/null
trap 'docker rm -f bet-bq-emu >/dev/null 2>&1 || true' EXIT
for _ in $(seq 1 30); do curl -s -o /dev/null "localhost:$PORT/bigquery/v2/projects/pplk8s-lab/datasets" && break; sleep 1; done

# One statement through the jobs.query API; prints its rows or its error.
q() {
  python3 -I -c 'import json, sys; print(json.dumps({"query": sys.stdin.read(), "useLegacySql": False}))' |
    curl -s -X POST "localhost:$PORT/bigquery/v2/projects/pplk8s-lab/queries" -H 'content-type: application/json' -d @- |
    python3 -I -c 'import json, sys
r = json.load(sys.stdin)
names = [f["name"] for f in r.get("schema", {}).get("fields", [])]
if r.get("error"): print("  error:", r["error"]["message"][:200])
for row in r.get("rows", []): print("  ", dict(zip(names, [c["v"] for c in row["f"]])))'
}

# The emulator answers `dataset silver is not found` to each CREATE TABLE yet creates the table (seen
# 2026-11-03), so the fixture's errors are dropped; the inserts and the functions' results show it worked.
while IFS= read -r stmt; do q <<<"$stmt" | grep -v 'is not found' || true; done <<'SQL'
CREATE SCHEMA silver
CREATE SCHEMA bet_shaped
CREATE TABLE silver.orders (order_id STRING, order_date TIMESTAMP, status STRING, amount NUMERIC, customer_id STRING)
INSERT silver.orders VALUES ('o1', TIMESTAMP '2026-02-10', 'shipped', 100, 'c1'), ('o2', TIMESTAMP '2026-02-10', 'cancelled', 50, 'c2'), ('o3', TIMESTAMP '2026-02-11', 'placed', 30, 'c1'), ('o4', TIMESTAMP '2026-06-01', 'shipped', 999, 'c2')
CREATE TABLE silver.customers (customer_id STRING, country STRING)
INSERT silver.customers VALUES ('c1', 'DE'), ('c2', 'FR')
CREATE TABLE silver.returns (return_id STRING, return_date TIMESTAMP, reason STRING, amount NUMERIC, order_id STRING)
INSERT silver.returns VALUES ('r1', TIMESTAMP '2026-02-10 10:00:00', 'damaged', 10.5, 'o1'), ('r2', TIMESTAMP '2026-02-10 11:00:00', 'late', 3, 'o2'), ('r3', TIMESTAMP '2026-05-01', 'damaged', 7, 'o3')
CREATE TABLE silver.campaigns (campaign_id STRING, channel STRING)
INSERT silver.campaigns VALUES ('k1', 'search'), ('k2', 'social')
CREATE TABLE silver.ad_spend (campaign_id STRING, spend_date TIMESTAMP, spend NUMERIC)
INSERT silver.ad_spend VALUES ('k1', TIMESTAMP '2026-02-10', 40), ('k2', TIMESTAMP '2026-02-10', 20), ('k1', TIMESTAMP '2026-06-01', 1000)
CREATE TABLE silver.leads (campaign_id STRING, created_date TIMESTAMP)
INSERT silver.leads VALUES ('k1', TIMESTAMP '2026-02-10'), ('k1', TIMESTAMP '2026-02-12'), ('k2', TIMESTAMP '2026-02-10')
CREATE TABLE silver.bookings (campaign_id STRING, booked_date TIMESTAMP)
INSERT silver.bookings VALUES ('k1', TIMESTAMP '2026-02-15')
SQL

echo "== create the table functions"
python3 -I - "$SQL" <<'PY' | while IFS= read -r stmt; do printf '%b' "$stmt" | q; done
import re
import sys

for m in re.finditer(r"CREATE OR REPLACE TABLE FUNCTION.*?\n\);", open(sys.argv[1]).read(), re.S):
    print(m.group(0).replace("\\", "\\\\").replace("\n", "\\n"))
PY

# Right answers for February and March 2026 (the June and May rows fall outside):
# daily_sales 02-10: revenue 100 (o2 cancelled), 2 orders, 1 cancelled, 1 customer; 02-11: 30, 1, none, 1.
# net_sales_daily 02-10: revenue 100, 2 returns, 13.5 returned, net 86.5; 02-11: 30 and net 30.
# sales_by_country_daily 02-10: DE 100 and 1 order, FR no revenue and 1 order; 02-11: DE 30 and 1.
# orders_by_status: 1 each of cancelled, placed, shipped; returns_by_reason: damaged 1 and 10.5, late 1 and 3.
# damaged_returns_daily 02-10: 1 and 10.5. channel_performance: search 40 spend, 2 leads, 1 booking, 20 a lead,
# 40 a booking; social 20 spend, 1 lead, no booking, 20 a lead.
for fn in daily_sales net_sales_daily sales_by_country_daily orders_by_status returns_by_reason \
  damaged_returns_daily channel_performance; do
  echo "== $fn(2026-02-01, 2026-03-31)"
  q <<<"SELECT * FROM bet_shaped.$fn(DATE '2026-02-01', DATE '2026-03-31')"
done
