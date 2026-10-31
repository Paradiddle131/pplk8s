#!/usr/bin/env bash
# Apply the workloads namespace: generate the warehouse Secret inputs, then `kubectl apply -k`. Idempotent.
# WAREHOUSE_PASSWORD matches compose.yaml's ${WAREHOUSE_PASSWORD:-warehouse}.
# ELF_IMAGE, ADAPTER_IMAGE, AGENT_IMAGE and DBT_IMAGE (Makefile) are the only source of the workload image tags (D16).
# The semantic agent reads AGENT_DBNAME (default warehouse; dbt_dev holds the fixture) and the model key from
# OPENROUTER_API_KEY (a placeholder when unset: a cloud network secret replaces it in flight).
# EGRESS_PROXY and EGRESS_CA, when set, route the agent's model calls through an HTTPS proxy that
# intercepts TLS (the cloud sandbox; tests/e2e/agent-deploy-check.sh sets both); unset on the laptop.
set -euo pipefail
cd "$(dirname "$0")/workloads"
mk() { make -s -C ../../.. "print-$1"; } # the Makefile default, when run outside make
elf_image="${ELF_IMAGE:-$(mk ELF_IMAGE)}"
adapter_image="${ADAPTER_IMAGE:-$(mk ADAPTER_IMAGE)}"
agent_image="${AGENT_IMAGE:-$(mk AGENT_IMAGE)}"
dbt_image="${DBT_IMAGE:-$(mk DBT_IMAGE)}"

pw="${WAREHOUSE_PASSWORD:-warehouse}"
# Lab defaults, never real credentials; the file is git-ignored and consumed by the Kustomize secretGenerator.
cat > warehouse.secret.env <<ENV
WAREHOUSE_DSN=postgresql://warehouse:${pw}@warehouse:5432/warehouse
DBT_HOST=warehouse
DBT_PORT=5432
DBT_USER=warehouse
DBT_PASSWORD=${pw}
DBT_DBNAME=warehouse
ENV
# The semantic agent's read-only role and its audit writer (dbt/macros/agent_warehouse.sql, make agent-warehouse), its session store
# (the metadata DB's agent_sessions database, platform/compose/up.sh) and the model key (semantic/PLAN.md SL-2).
# No agent_sql login: the text-to-SQL baseline is the eval's control, never deployed (SL-5).
agent_db="${AGENT_DBNAME:-warehouse}"
cat > semantic-agent.secret.env <<ENV
DBT_HOST=warehouse
DBT_PORT=5432
DBT_USER=agent_metrics
DBT_PASSWORD=agent_metrics
DBT_DBNAME=${agent_db}
AUDIT_URL=postgresql://agent_audit:agent_audit@warehouse:5432/${agent_db}
SESSION_SERVICE_URI=postgresql+asyncpg://agent_sessions:agent_sessions@metadata-db:5432/agent_sessions
OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-placeholder-replaced-by-the-proxy}
ENV
if [ -n "${EGRESS_PROXY:-}" ]; then
  cat >> semantic-agent.secret.env <<ENV
HTTPS_PROXY=${EGRESS_PROXY}
NO_PROXY=warehouse,metadata-db,localhost,127.0.0.1,.svc,.cluster.local
SSL_CERT_FILE=/etc/egress-ca/ca.crt
ENV
  kubectl --context kind-pplk8s create namespace workloads --dry-run=client -o yaml | kubectl --context kind-pplk8s apply -f - >/dev/null
  kubectl --context kind-pplk8s -n workloads create configmap egress-ca --from-file=ca.crt="${EGRESS_CA:?EGRESS_PROXY needs EGRESS_CA}" \
    --dry-run=client -o yaml | kubectl --context kind-pplk8s apply -f - >/dev/null
  echo "semantic agent: model calls through $EGRESS_PROXY"
fi
# The adapter's own Airflow API identity (Airflow role User, created by the Airflow deploy script).
cat > airflow-api.secret.env <<ENV
AIRFLOW_USERNAME=event-adapter
AIRFLOW_PASSWORD=$(../../helm/airflow/api-identity.sh)
ENV

adapter_secret() { kubectl --context kind-pplk8s -n workloads get secret event-adapter-airflow -o jsonpath='{.data}' 2>/dev/null || true; }
before=$(adapter_secret)
# The manifests name their images by placeholder; a throwaway overlay maps each to its Makefile reference.
# It sits next to the base because Kustomize refuses an absolute path to a base.
overlay=$(mktemp -d ../.workloads-overlay.XXXXXX)
trap 'rm -rf "$overlay"' EXIT
cat > "$overlay/kustomization.yaml" <<YAML
resources: [../workloads]
images:
  - {name: el-factory, newName: "${elf_image%:*}", newTag: "${elf_image##*:}"}
  - {name: event-adapter, newName: "${adapter_image%:*}", newTag: "${adapter_image##*:}"}
  - {name: semantic-agent, newName: "${agent_image%:*}", newTag: "${agent_image##*:}"}
YAML
kubectl --context kind-pplk8s apply -k "$overlay"
# The generated Secret keeps a fixed name, so a changed login does not roll the adapter by itself.
if [ -n "$before" ] && [ "$before" != "$(adapter_secret)" ]; then
  kubectl --context kind-pplk8s -n workloads rollout restart deployment/event-adapter
fi
kubectl --context kind-pplk8s -n workloads rollout status deployment/el-factory --timeout=120s
kubectl --context kind-pplk8s -n workloads rollout status deployment/event-adapter --timeout=120s
# The agent's Secret also keeps a fixed name: restart it so a changed database or key takes effect.
kubectl --context kind-pplk8s -n workloads rollout restart deployment/semantic-agent >/dev/null
kubectl --context kind-pplk8s -n workloads rollout status deployment/semantic-agent --timeout=300s
# dbt has no Deployment: Airflow's run_dbt reads the image from the dbt_image Variable at task run time.
../../helm/airflow/dbt-image-variable.sh "$dbt_image"
