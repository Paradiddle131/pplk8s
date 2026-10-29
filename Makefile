# Single entry point for the lab. `make help` lists targets.
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# Kind node image: Kubernetes 1.36, the GKE Regular-channel default (Oct 2026); see PLAN.md D4.
NODE_IMAGE ?= kindest/node:v1.36.4@sha256:099e049362a1526b2db71494e1947aae99bd16290d7c895f2b7ea312e3cbfaed
export NODE_IMAGE

# Workload images, tagged for the local registry so Phase 2 can push them as-is.
# The only place their tags live (D16): workloads-up.sh deploys these exact references.
ELF_IMAGE ?= localhost:5001/el-factory:0.7.0
DBT_IMAGE ?= localhost:5001/dbt:0.6.0
ADAPTER_IMAGE ?= localhost:5001/event-adapter:0.1.0
export ELF_IMAGE DBT_IMAGE ADAPTER_IMAGE

# Airflow image: 3.3.1 base (D1) plus our suffix revision, bumped when the Dockerfile, requirements or include/ change.
AIRFLOW_IMAGE ?= localhost:5001/airflow:3.3.1-pplk8s.14
export AIRFLOW_IMAGE

# The upgrade drill's older line: Airflow 3.2.2 on chart 1.21.0 (both offered by Composer / the chart repo).
AIRFLOW_DRILL_IMAGE ?= localhost:5001/airflow:3.2.2-pplk8s.3
export AIRFLOW_DRILL_IMAGE

# DAG delivery (PLAN.md D23): git-sync of `main` from GitHub, or `local` for this checkout's DAGs.
DAG_DELIVERY ?= git-sync
export DAG_DELIVERY

.PHONY: help tools lint check verify cluster-up cluster-down cluster-check services-up services-down services-reset build el-factory-up el-factory-down dbt-build test airflow-test phase1-check push workloads-up workloads-down dbt-job phase2-check airflow-image airflow-up airflow-down airflow-ui phase3-check phase4-check phase5-check observability-up observability-down grafana-ui prometheus-ui ci-integration keda-up keda-down airflow-drill-image phase6-check phase6-upgrade-drill db-cleanup-check metadata-restore-drill tlc-dbt-check ledger rules-test phase8-check el-factory-memory-drill tlc-resume-drill dbt-validate semantic-check

# `make -s print-DBT_IMAGE` prints one variable: scripts run outside make read their defaults this way.
print-%:
	@echo '$($*)'

help: ## List targets
	@grep -hE '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-20s %s\n", $$1, $$2}'

tools: ## Install pinned kind, kubectl, helm, k9s into ~/.local/bin
	scripts/install-tools.sh

cluster-up: ## Create the kind cluster and local registry (localhost:5001)
	platform/kind/cluster-up.sh

cluster-down: ## Delete the kind cluster and local registry
	platform/kind/cluster-down.sh

cluster-check: ## Verify workers are Ready and the registry serves images in-cluster
	platform/kind/cluster-check.sh

services-up: ## Start warehouse (localhost:5433), fake-gcs (localhost:4480), Pub/Sub emulator (localhost:8085)
	platform/compose/up.sh

services-down: ## Stop the out-of-cluster services, keeping their data
	docker compose -f platform/compose/compose.yaml down

services-reset: ## Stop the out-of-cluster services and delete their data
	docker compose -f platform/compose/compose.yaml down -v

build: ## Build the EL Factory lite, dbt, and event adapter images
	docker build -t $(ELF_IMAGE) services/el-factory
	docker build -t $(DBT_IMAGE) dbt
	docker build -t $(ADAPTER_IMAGE) services/event-adapter

el-factory-up: services-up ## Run EL Factory lite on localhost:8090 against the Compose services
	scripts/el-factory-local.sh up

el-factory-down: ## Stop the local EL Factory lite container
	scripts/el-factory-local.sh down

STAGE ?= bronze
tlc-dbt-check: services-up ## Build the tlc dbt models month by month on dbt/dev/tlc_fixture.sql in dbt_dev and assert month replacement (#55)
	tests/e2e/tlc-dbt-check.sh

dbt-build: ## Run `dbt build --select $(STAGE)` (bronze|silver|gold|exposed|semantic) against the warehouse
	docker run --rm --network pplk8s $(DBT_IMAGE) build --select $(STAGE)

# The semantic layer's stage check (semantic/PLAN.md SL-1), with host dbt on the image's pins as
# tlc-dbt-check runs it: the project parses, every metric is described and labelled, and MetricFlow
# validates the semantic models, dimensions, entities, measures and metrics against the warehouse.
DBT_DBNAME ?= warehouse
dbt-validate: ## Validate the semantic layer against the Compose warehouse (DBT_DBNAME=warehouse|dbt_dev): dbt parse, metric descriptions and labels, mf validate-configs
	cd dbt && export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME=$(DBT_DBNAME) DBT_PROFILES_DIR=$(CURDIR)/dbt \
	  && uvx --quiet --with-requirements requirements.txt --from dbt-core dbt parse --quiet \
	  && python3 scripts/check_metrics.py target/semantic_manifest.json \
	  && uvx --quiet --with-requirements requirements.txt --from dbt-metricflow mf validate-configs

semantic-check: services-up ## Build the sales, returns and finance models on dbt/dev/fixture.sql in dbt_dev, run dbt-validate on it, and assert the eight metrics equal gold.daily_sales and exposed.net_sales_daily (#100)
	tests/e2e/semantic-check.sh

airflow-test: ## Lint and test the Airflow DAGs and workload seam (airflow/)
	cd airflow && uv run ruff check . && uv run ruff format --check . && uv run pytest -q

check: export PPLK8S_REQUIRE_WAREHOUSE := 1
check: services-up ## Light gate on every change (PLAN.md D26): linters, unit and DagBag tests with the Compose warehouse required
	$(MAKE) lint test

verify: export PPLK8S_REQUIRE_WAREHOUSE := 1
verify: lint test build ## Pre-merge gate (PLAN.md D26): linters, unit and DagBag tests, every image build (needs services-up)
	docker build -t $(AIRFLOW_IMAGE) airflow

rules-test: ## Check the Prometheus alert rules and run their promtool unit tests (tests/monitoring)
	tests/monitoring/rules-test.sh

test: airflow-test rules-test ## Run unit tests and linters
	cd services/el-factory && uv run ruff check . && uv run ruff format --check . && uv run pytest -q
	cd services/event-adapter && uv run ruff check . && uv run ruff format --check . && uv run pytest -q

push: build ## Push the EL Factory, dbt, and event adapter images to the local registry (localhost:5001)
	docker push $(ELF_IMAGE)
	docker push $(DBT_IMAGE)
	docker push $(ADAPTER_IMAGE)

workloads-up: services-up push ## Apply the workloads namespace (EL Factory, Secret, ConfigMap) and wait for rollout
	platform/k8s/workloads-up.sh

workloads-down: ## Delete the workloads namespace and everything in it
	kubectl --context kind-pplk8s delete namespace workloads --ignore-not-found

dbt-job: ## Run `dbt build --select $(STAGE)` as a Kubernetes Job and print its logs
	platform/k8s/dbt-job.sh $(STAGE)

phase2-check: workloads-up ## Phase 2 exit check: EL Factory answers in-cluster, dbt Jobs build every stage
	tests/e2e/phase2-check.sh

phase1-check: services-up build ## Phase 1 exit check: extract via curl, re-run idempotently, dbt build every stage
	tests/e2e/phase1-check.sh

airflow-image: ## Build and push the Airflow image to the local registry
	docker build -t $(AIRFLOW_IMAGE) airflow
	docker push $(AIRFLOW_IMAGE)

# Extra values files from platform/helm/airflow, e.g. AIRFLOW_OVERLAYS=values-multi-executor.yaml.
AIRFLOW_OVERLAYS ?=
airflow-up: services-up keda-up ## Deploy Airflow into namespace airflow (DAG_DELIVERY=git-sync|local, AIRFLOW_OVERLAYS=...)
	platform/helm/airflow/deploy.sh $(addprefix -f ,$(AIRFLOW_OVERLAYS))

airflow-down: ## Uninstall the Airflow release (keeps the metadata DB, secrets and PV)
	helm --kube-context kind-pplk8s uninstall airflow -n airflow --wait

airflow-ui: ## Port-forward the Airflow UI/API to http://localhost:8080 (admin/admin)
	kubectl --context kind-pplk8s -n airflow port-forward svc/airflow-api-server 8080:8080

phase3-check: airflow-up ## Phase 3 exit check: hello DAG on a Celery worker, upgrade + rollback stays healthy
	tests/e2e/phase3-check.sh

phase4-check: airflow-up workloads-up ## Phase 4 exit check: full sales_elt run, idempotent clear/re-run, kill + FAIL_RATE retry drills
	tests/e2e/phase4-check.sh

phase5-check: airflow-up workloads-up ## Phase 5 exit check: one file -> one run, redelivery is a no-op, consumer defers on ops.readiness
	tests/e2e/phase5-check.sh

phase6-check: airflow-up observability-up workloads-up airflow-drill-image ## Phase 6 exit check: dashboards' series, KEDA scale-out/in, then every failure drill incl. the chart/minor roll and the metadata DB restore (alert fires, runbook recovers, canary) (~70 min)
	tests/e2e/observability-check.sh
	tests/e2e/keda-check.sh
	tests/e2e/phase6-check.sh
	tests/e2e/db-cleanup-check.sh
	tests/e2e/metadata-restore-drill.sh
	tests/e2e/phase6-upgrade-drill.sh

phase8-check: airflow-up workloads-up ## Phase 8 exit check: tlc_monthly's scheduled months, backfilled drift months, reconciled layers, a republished month (downloads real TLC files)
	tests/e2e/phase8-check.sh

el-factory-memory-drill: ## Phase 8 drill 1: FHVHV chunks against EL Factory's 1 GiB ceiling (TIGHT_LIMIT=448Mi: the memory alerts fire)
	tests/e2e/el-factory-memory-drill.sh

tlc-resume-drill: airflow-up workloads-up observability-up ## Phase 8 drill 2: lose the EL Factory pod mid-file; the extract's retry resumes after the last loaded chunk (~10 min)
	tests/e2e/tlc-resume-drill.sh

db-cleanup-check: airflow-up observability-up ## Run the metadata DB cleanup CronJob once: a 61-day-old crashed job row goes, live jobs stay, a failed run's KubeJobFailed clears (D30)
	tests/e2e/db-cleanup-check.sh

airflow-drill-image: ## Build and push the upgrade drill's Airflow 3.2.2 image (AIRFLOW_DRILL_IMAGE)
	docker build -t $(AIRFLOW_DRILL_IMAGE) --build-arg AIRFLOW_VERSION=3.2.2 --build-arg REQUIREMENTS=requirements-drill-3.2.2.txt --build-arg DROP_CONSTRAINTS=-none- airflow
	docker push $(AIRFLOW_DRILL_IMAGE)

metadata-restore-drill: airflow-up observability-up workloads-up ## Phase 6 drill 10: restore the metadata DB to an earlier point, detect the drift from the warehouse, replay the lost runs (~6 min)
	tests/e2e/metadata-restore-drill.sh

phase6-upgrade-drill: airflow-up observability-up airflow-drill-image ## Phase 6 drill 5: chart 1.21.0 + Airflow 3.2.2 -> 1.22.0 + 3.3.1 and back, on a throwaway DB (~10 min)
	tests/e2e/phase6-upgrade-drill.sh

ci-integration: ## CI integration test: deploy with this checkout's DAGs, hello on a worker, then the Phase 5 event path
	$(MAKE) airflow-up workloads-up DAG_DELIVERY=local AIRFLOW_OVERLAYS=$(CURDIR)/platform/helm/airflow/values-ci.yaml
	tests/e2e/smoke-check.sh
	tests/e2e/phase5-check.sh

keda-up: ## Deploy the KEDA operator that scales the Celery workers (namespace keda)
	platform/keda/deploy.sh

keda-down: ## Uninstall KEDA (uninstall Airflow first: its worker ScaledObject needs the CRDs)
	helm --kube-context kind-pplk8s uninstall keda -n keda --wait --ignore-not-found

observability-up: services-up ## Deploy kube-prometheus-stack, Airflow scrape targets, alert rules, and dashboards (namespace monitoring)
	platform/monitoring/deploy.sh

observability-down: ## Uninstall the monitoring stack (the database exporters stay with the Compose services)
	kubectl --context kind-pplk8s delete -k platform/monitoring/manifests --ignore-not-found
	helm --kube-context kind-pplk8s uninstall kube-prometheus-stack -n monitoring --wait --ignore-not-found

grafana-ui: ## Port-forward Grafana to http://localhost:3000 (admin/admin)
	kubectl --context kind-pplk8s -n monitoring port-forward svc/grafana 3000:80

prometheus-ui: ## Port-forward Prometheus to http://localhost:9090
	kubectl --context kind-pplk8s -n monitoring port-forward svc/kps-prometheus 9090:9090

ledger: ## Fold ledger.d/ fragments into LEDGER.md (run on main after merges)
	scripts/ledger-fold.sh

lint: ## Lint shell scripts (shellcheck via uvx)
	uvx --from shellcheck-py shellcheck -x -P SCRIPTDIR scripts/*.sh platform/*/*.sh platform/helm/airflow/*.sh platform/k8s/*.sh tests/e2e/*.sh tests/monitoring/*.sh docs/agents/*.sh
