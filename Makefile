# Single entry point for the lab. `make help` lists targets.
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# Kind node image: Kubernetes 1.36, the GKE Regular-channel default (Oct 2026); see PLAN.md D4.
NODE_IMAGE ?= kindest/node:v1.36.4@sha256:099e049362a1526b2db71494e1947aae99bd16290d7c895f2b7ea312e3cbfaed
export NODE_IMAGE

# Workload images, tagged for the local registry so Phase 2 can push them as-is.
# The only place their tags live (D16): workloads-up.sh deploys these exact references.
ELF_IMAGE ?= localhost:5001/el-factory:0.7.5
DBT_IMAGE ?= localhost:5001/dbt:0.7.25
ADAPTER_IMAGE ?= localhost:5001/event-adapter:0.1.1
AGENT_IMAGE ?= localhost:5001/semantic-agent:0.1.22
export ELF_IMAGE DBT_IMAGE ADAPTER_IMAGE AGENT_IMAGE

# Builds behind a TLS-intercepting proxy (the cloud sandbox): BUILD_CA names the proxy's CA bundle, which
# every dependency step mounts as the BuildKit secret `build_ca` (never a layer), and builds use the host
# network to reach the proxy. Unset, as on the laptop, builds are plain.
BUILD_CA ?= $(wildcard /root/.ccr/ca-bundle.crt)
BUILD_SECRET = id=build_ca,src=$(BUILD_CA)
DOCKER_BUILD = docker build $(if $(BUILD_CA),--network host --build-arg HTTPS_PROXY --build-arg HTTP_PROXY --build-arg NO_PROXY --secret $(BUILD_SECRET))

# This checkout's GitHub <owner>/<repo>, from the origin remote: the registry cache and Airflow's git-sync
# name it from here, so a fork builds, caches and syncs against itself.
GITHUB_REPO ?= $(shell git remote get-url origin 2>/dev/null | sed -E 's#^(git@|[a-z]+://)([^@/]*@)?github\.com[:/]##; s#\.git$$##')
export GITHUB_REPO

# A layer cache in a registry, shared by every session that builds (the image-cache skill): each image reads
# and writes $(BUILD_CACHE)/<cache name>:buildcache, so a fresh cloud session rebuilds only what changed.
# On by default where BUILD_CA is (the cloud, whose proxy holds the ghcr.io login); a laptop opts in with
# BUILD_CACHE=ghcr.io/<owner>/<repo> after `docker login ghcr.io`. A failed cache write never fails a build.
BUILD_CACHE ?= $(if $(and $(BUILD_CA),$(GITHUB_REPO)),ghcr.io/$(shell echo '$(GITHUB_REPO)' | tr '[:upper:]' '[:lower:]'))
comma := ,
cache_flags = $(if $(BUILD_CACHE),--cache-from type=registry$(comma)ref=$(BUILD_CACHE)/$(1):buildcache --cache-to type=registry$(comma)ref=$(BUILD_CACHE)/$(1):buildcache$(comma)mode=max$(comma)ignore-error=true)
# $(call docker_build,<image ref>[,<cache name>]): the cache name defaults to the image's repository name.
docker_build = $(DOCKER_BUILD) -t $(1) $(call cache_flags,$(or $(2),$(firstword $(subst :, ,$(notdir $(1))))))

# $(call publish,<image ref>,<build args and context>[,<cache name>]): build the image and push it to the local registry.
# On cloud (BUILD_CA set) the session's disk allowance cannot hold each image in Docker, the local registry and the
# nodes at once (#119): a tag the registry already serves is not rebuilt (D16: a tag names its content; FORCE_BUILD=1
# rebuilds it), and after a push Docker's copy and BuildKit's local cache go. The laptop always builds and keeps both.
publish = $(if $(and $(BUILD_CA),$(if $(FORCE_BUILD),,$(call in_registry,$(1)))),@echo "$(1): the local registry has it",$(call docker_build,$(1),$(3)) $(2) && docker push $(1)$(if $(BUILD_CA), && docker image rm $(1) >/dev/null && docker builder prune -af >/dev/null))
manifest_types = application/vnd.oci.image.index.v1+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.docker.distribution.manifest.v2+json
in_registry = $(shell curl -sf -o /dev/null -H 'Accept: $(manifest_types)' http://$(firstword $(subst /, ,$(1)))/v2/$(firstword $(subst :, ,$(notdir $(1))))/manifests/$(word 2,$(subst :, ,$(notdir $(1)))) && echo yes)

# Airflow image: 3.3.1 base (D1) plus our suffix revision, bumped when the Dockerfile, requirements or include/ change.
AIRFLOW_IMAGE ?= localhost:5001/airflow:3.3.1-pplk8s.20
export AIRFLOW_IMAGE

# The upgrade drill's older line: Airflow 3.2.2 on chart 1.21.0 (both offered by Composer / the chart repo).
AIRFLOW_DRILL_IMAGE ?= localhost:5001/airflow:3.2.2-pplk8s.4
export AIRFLOW_DRILL_IMAGE

# DAG delivery (PLAN.md D23): git-sync of `main` from GitHub, or `local` for this checkout's DAGs.
DAG_DELIVERY ?= git-sync
export DAG_DELIVERY

.PHONY: help tools lint check verify cluster-up cluster-down cluster-check services-up services-down services-reset build el-factory-up el-factory-down dbt-build test airflow-test phase1-check push workloads-up workloads-down dbt-job phase2-check airflow-image airflow-up airflow-down airflow-ui phase3-check phase4-check phase5-check observability-up observability-down grafana-ui prometheus-ui ci-integration keda-up keda-down airflow-drill-image phase6-check phase6-upgrade-drill db-cleanup-check metadata-restore-drill tlc-dbt-check ledger rules-test phase8-check el-factory-memory-drill tlc-resume-drill dbt-validate semantic-check dbt-catalog catalog-check agent-test agent-serve agent-key-check agent-deploy-check agent-eval bigquery-check bigquery-emulator-check migration-check metric-query warehouse-sql agent-web agent-warehouse agent-standalone-check source-freshness-check source-freshness-table gcp-validate gcp-plan gcp-up gcp-down gcp-cost-check

# `make -s print-DBT_IMAGE` prints one variable: scripts run outside make read their defaults this way.
print-%:
	@echo '$($*)'

help: ## List targets
	@grep -hE '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-20s %s\n", $$1, $$2}'

tools: ## Install pinned kind, kubectl, helm, k9s into ~/.local/bin
	scripts/install-tools.sh

cluster-up: ## Create the kind cluster and local registry (localhost:5001)
	platform/kind/cluster-up.sh

egress-up: ## Behind a loopback HTTPS proxy (the cloud sandbox): relay the kind nodes' pulls and pods' calls through it; otherwise nothing (#119)
	BUILD_CA=$(BUILD_CA) platform/kind/egress-up.sh

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

build: ## Build the EL Factory lite, dbt, event adapter and semantic agent images
	$(call docker_build,$(ELF_IMAGE)) services/el-factory
	$(call docker_build,$(DBT_IMAGE)) dbt
	$(call docker_build,$(ADAPTER_IMAGE)) services/event-adapter
	$(call docker_build,$(AGENT_IMAGE)) --build-context dbt=dbt services/semantic-agent

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
# tlc-dbt-check runs it: the project parses, it keeps the agent-ready standard (naming by layer, public
# models, semantic models and metrics described; docs/agent-ready-warehouse.md), and MetricFlow
# validates the semantic models, dimensions, entities, measures and metrics against the warehouse.
DBT_DBNAME ?= warehouse
dbt-validate: ## Validate the semantic layer against the Compose warehouse (DBT_DBNAME=warehouse|dbt_dev): dbt parse, the agent-ready standard, mf validate-configs
	cd dbt && export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME=$(DBT_DBNAME) DBT_PROFILES_DIR=$(CURDIR)/dbt \
	  && uvx --quiet --with-requirements requirements.txt --from dbt-core dbt parse --quiet \
	  && python3 scripts/check_standard.py target \
	  && uvx --quiet --with-requirements requirements.txt --from dbt-metricflow mf validate-configs

# The catalog (semantic/PLAN.md SL-3), with the same host dbt: the agent catalog and the BigQuery data
# agent's authored context under dbt/target/catalog/ (offline), then the semantic stage, whose
# semantic.metrics table is the warehouse copy; persist_docs comments gold and exposed as they build.
dbt-catalog: ## Write the agent catalog and the data agent's authored context to dbt/target/catalog, and build semantic.metrics (DBT_DBNAME=warehouse|dbt_dev)
	cd dbt && export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME=$(DBT_DBNAME) DBT_PROFILES_DIR=$(CURDIR)/dbt \
	  && uvx --quiet --with-requirements requirements.txt --from dbt-core dbt parse --quiet \
	  && uv run --quiet --no-project --with-requirements requirements.txt python scripts/build_catalog.py \
	  && uv run --quiet --no-project --with-requirements requirements.txt python scripts/check_catalog.py \
	  && uvx --quiet --with-requirements requirements.txt --from dbt-core dbt build --quiet --select semantic

# Query metrics through MetricFlow from the host, as an agent's query_metrics does (docs/demo.md).
METRICS ?= revenue_eur,returns_eur,net_revenue_eur
GROUP_BY ?= metric_time__day
metric-query: ## Query metrics with `mf query` on the Compose warehouse (METRICS=a,b GROUP_BY=metric_time__day DBT_DBNAME=warehouse|dbt_dev)
	cd dbt && export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME=$(DBT_DBNAME) DBT_PROFILES_DIR=$(CURDIR)/dbt \
	  && uvx --quiet --with-requirements requirements.txt --from dbt-core dbt parse --quiet \
	  && uvx --quiet --with-requirements requirements.txt --from dbt-metricflow mf query --metrics $(METRICS) --group-by $(GROUP_BY) --order $(GROUP_BY)

SQL ?= select 1
warehouse-sql: ## Run one psql command on the Compose warehouse as its owner (SQL='\d+ gold.daily_sales' DBT_DBNAME=warehouse|dbt_dev)
	docker compose -f platform/compose/compose.yaml exec -T warehouse psql -U warehouse -d $(DBT_DBNAME) -c '$(SQL)'

catalog-check: services-up ## Build the fixture's models in dbt_dev, run dbt-catalog on it, and assert every gold and exposed column is commented and every metric is in semantic.metrics (#101)
	tests/e2e/catalog-check.sh

bigquery-check: ## Parse, validate and compile the dbt project on the compile-only BigQuery target, offline, and write the BigQuery catalog to dbt/target/bigquery (#104)
	tests/e2e/bigquery-check.sh

bigquery-emulator-check: services-up ## Run the semantic path on the BigQuery emulator (Compose profile bigquery): copy the fixture in, dbt build, and assert the metrics equal the hand-written gold and exposed there, the migration rehearsal reports as on Postgres, and the recruitment snapshot replayed extract by extract on a recreated emulator keeps the stage history (#125, #246)
	tests/e2e/bigquery-emulator-check.sh

source-freshness-check: services-up ## Run dbt source freshness on the dev fixtures in dbt_freshness: fresh data passes, a stopped source errors, and the warehouse sql_exporter exports each verdict (#130)
	tests/e2e/source-freshness-check.sh

semantic-check: services-up ## Build the sales, returns, finance, marketing, customer-actions, partner-outreach and recruitment models on dbt/dev/fixture.sql in dbt_dev, run dbt-validate on it, and assert the metrics equal the hand-written gold and exposed models, an incremental build places late actions, the activation list honours consent, and the recruitment snapshot replayed extract by extract answers stage counts as of a date (#100, #126, #188, #190, #189)
	tests/e2e/semantic-check.sh

migration-check: services-up ## Build the legacy tables, the new layers and migration.parity on dbt/dev/fixture.sql in dbt_dev, and assert the parity report and the gate on each consumer's switch
	tests/e2e/migration-check.sh

# The semantic agent's warehouse objects (semantic/PLAN.md SL-4, SL-10; #166): its roles, their grants and the
# audit table, from one dbt macro (dbt/macros/agent_warehouse.sql) on any database the dbt project builds in,
# with its own target path so a catalog built for another database stays. services-up runs it on warehouse.
agent-warehouse: ## Create the semantic agent's roles, grants and ops.agent_queries in a database dbt builds in (DBT_DBNAME=warehouse|dbt_dev|...)
	cd dbt && export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME=$(DBT_DBNAME) DBT_PROFILES_DIR=$(CURDIR)/dbt DBT_TARGET_PATH=target/agent-warehouse \
	  && uvx --quiet --with-requirements requirements.txt --from dbt-core dbt run-operation agent_warehouse

source-freshness-table: ## Create ops.source_freshness, which the source-freshness CronJob fills, in a database dbt builds in (DBT_DBNAME=warehouse|...; #130)
	cd dbt && export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME=$(DBT_DBNAME) DBT_PROFILES_DIR=$(CURDIR)/dbt DBT_TARGET_PATH=target/source-freshness-table \
	  && uvx --quiet --with-requirements requirements.txt --from dbt-core dbt run-operation source_freshness_table

# The semantic agent and its text-to-SQL baseline (semantic/PLAN.md SL-2, SL-5). Only the semantic agent is
# deployed (workloads-up); the baseline is the eval's control, served here only beside it for the local demo.
agent-test: ## Lint and test the semantic agent with a scripted model (services/semantic-agent); the database tests need services-up
	cd services/semantic-agent && uv run ruff check . && uv run ruff format --check . && uv run pytest -q

AGENT_DBNAME ?= warehouse
agent-serve: ## Serve both agents locally (the semantic agent and the eval's baseline) with `adk api_server` on localhost:8000, sessions in the metadata DB's agent_sessions database (needs services-up and dbt-catalog)
	cd services/semantic-agent && DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME=$(AGENT_DBNAME) DBT_USER=agent_metrics DBT_PASSWORD=agent_metrics \
	  uv run adk api_server --host 127.0.0.1 --port 8000 \
	  --session_service_uri postgresql+asyncpg://agent_sessions:agent_sessions@localhost:5434/agent_sessions src

agent-web: ## Serve both agents locally (the semantic agent and the eval's baseline) in ADK's dev UI on localhost:8000, the demo surface (needs services-up and dbt-catalog)
	cd services/semantic-agent && DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME=$(AGENT_DBNAME) DBT_USER=agent_metrics DBT_PASSWORD=agent_metrics \
	  uv run adk web --host 127.0.0.1 --port 8000 \
	  --session_service_uri postgresql+asyncpg://agent_sessions:agent_sessions@localhost:5434/agent_sessions src

agent-standalone-check: services-up ## Run the semantic agent on an empty database with only the dbt project: make agent-warehouse, the fixture, one scripted turn; asserts its audit row and "Freshness unknown" (#166; no model quota)
	tests/e2e/agent-standalone-check.sh

agent-key-check: ## Ask OpenRouter whether it accepts the agents' key, spending no model request (#158; the cloud proxy adds the key)
	tests/e2e/openrouter-key-check.sh

# The key check runs before the image builds and the deploy, so a refused key fails in seconds.
agent-deploy-check: agent-key-check services-up push ## Live: deploy the workloads with the semantic agent on the dbt_dev fixture and ask it one question through its Service (#111; needs cluster-up; one model turn)
	tests/e2e/agent-deploy-check.sh

agent-eval: services-up ## Live: score the semantic agent against the text-to-SQL baseline on dbt/dev/fixture.sql; writes docs/research/semantic-agent-eval.md (spends ~2 x 15 free-tier model turns)
	tests/e2e/agent-eval.sh

airflow-test: ## Lint and test the Airflow DAGs and workload seam (airflow/)
	cd airflow && uv run ruff check . && uv run ruff format --check . && uv run pytest -q

check: export PPLK8S_REQUIRE_WAREHOUSE := 1
check: services-up ## Light gate on every change (PLAN.md D26): linters, unit and DagBag tests with the Compose warehouse required
	$(MAKE) lint test

verify: export PPLK8S_REQUIRE_WAREHOUSE := 1
verify: lint test build ## Pre-merge gate (PLAN.md D26): linters, unit and DagBag tests, every image build (needs services-up)
	$(call docker_build,$(AIRFLOW_IMAGE)) airflow

rules-test: ## Check the Prometheus alert rules and run their promtool unit tests (tests/monitoring)
	tests/monitoring/rules-test.sh

test: airflow-test rules-test agent-test ## Run unit tests and linters
	cd services/el-factory && uv run ruff check . && uv run ruff format --check . && uv run pytest -q
	cd services/event-adapter && uv run ruff check . && uv run ruff format --check . && uv run pytest -q

push: ## Build the EL Factory, dbt, event adapter and semantic agent images and push them to the local registry (localhost:5001)
	$(call publish,$(ELF_IMAGE),services/el-factory)
	$(call publish,$(DBT_IMAGE),dbt)
	$(call publish,$(ADAPTER_IMAGE),services/event-adapter)
	$(call publish,$(AGENT_IMAGE),--build-context dbt=dbt services/semantic-agent)

workloads-up: services-up push egress-up ## Apply the workloads namespace (EL Factory, event adapter, semantic agent, Secrets, ConfigMaps) and wait for rollout
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
	$(call publish,$(AIRFLOW_IMAGE),airflow)

# Extra values files from platform/helm/airflow, e.g. AIRFLOW_OVERLAYS=values-multi-executor.yaml.
AIRFLOW_OVERLAYS ?=
airflow-up: services-up keda-up egress-up ## Deploy Airflow into namespace airflow (DAG_DELIVERY=git-sync|local, AIRFLOW_OVERLAYS=...)
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
	$(call publish,$(AIRFLOW_DRILL_IMAGE),--build-arg AIRFLOW_VERSION=3.2.2 --build-arg REQUIREMENTS=requirements-drill-3.2.2.txt --build-arg DROP_CONSTRAINTS=-none- airflow,airflow-drill)

metadata-restore-drill: airflow-up observability-up workloads-up ## Phase 6 drill 10: restore the metadata DB to an earlier point, detect the drift from the warehouse, replay the lost runs (~6 min)
	tests/e2e/metadata-restore-drill.sh

phase6-upgrade-drill: airflow-up observability-up airflow-drill-image ## Phase 6 drill 5: chart 1.21.0 + Airflow 3.2.2 -> 1.22.0 + 3.3.1 and back, on a throwaway DB (~10 min)
	tests/e2e/phase6-upgrade-drill.sh

ci-integration: ## CI integration test: deploy with this checkout's DAGs, hello on a worker, then the Phase 5 event path
	$(MAKE) airflow-up workloads-up DAG_DELIVERY=local AIRFLOW_OVERLAYS=$(CURDIR)/platform/helm/airflow/values-ci.yaml
	tests/e2e/smoke-check.sh
	tests/e2e/phase5-check.sh

keda-up: egress-up ## Deploy the KEDA operator that scales the Celery workers (namespace keda)
	platform/keda/deploy.sh

keda-down: ## Uninstall KEDA (uninstall Airflow first: its worker ScaledObject needs the CRDs)
	helm --kube-context kind-pplk8s uninstall keda -n keda --wait --ignore-not-found

observability-up: services-up egress-up ## Deploy kube-prometheus-stack, Airflow scrape targets, alert rules, and dashboards (namespace monitoring)
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

lint: ## Lint shell scripts (shellcheck via uvx), the dbt helper scripts and the BigQuery emulator shim (ruff via uvx)
	uvx --from shellcheck-py shellcheck -x -P SCRIPTDIR scripts/*.sh platform/*/*.sh platform/helm/airflow/*.sh platform/k8s/*.sh tests/e2e/*.sh tests/monitoring/*.sh
	cd dbt && uvx ruff@0.17.0 check scripts && uvx ruff@0.17.0 format --check scripts
	uvx ruff@0.17.0 check platform/compose/bigquery-shim && uvx ruff@0.17.0 format --check platform/compose/bigquery-shim
	$(MAKE) --no-print-directory gcp-validate

# The lab project on GCP (semantic/PLAN.md SL-13, platform/gcp/README.md): validated offline in `make lint`;
# every other gcp- target needs GCP_PROJECT and refuses without it.
gcp-validate: ## Offline: tofu fmt and validate, tflint, and the free-path allowlist on platform/gcp/ (no credentials; needs `make tools`)
	@command -v tofu >/dev/null && command -v tflint >/dev/null || { echo "gcp-validate: tofu and tflint are missing: run make tools" >&2; exit 1; }
	tofu -chdir=platform/gcp/infra fmt -check -recursive
	# Its own working directory: one a live gcp- target initialised remembers the gcs backend and its credentials.
	TF_DATA_DIR=.terraform-validate tofu -chdir=platform/gcp/infra init -backend=false -input=false >/dev/null
	TF_DATA_DIR=.terraform-validate tofu -chdir=platform/gcp/infra validate
	cd platform/gcp/infra && tflint --init >/dev/null && tflint
	uvx ruff@0.17.0 check platform/gcp && uvx ruff@0.17.0 format --check platform/gcp
	uv run --no-project --with pyyaml==6.0.2 python platform/gcp/check_free_path.py
	uvx --from pytest==8.4.2 --with pyyaml==6.0.2 pytest -q platform/gcp/tests

gcp-plan: ## Live, read-only: show what `gcp-up` would change on the lab project (GCP_PROJECT)
	platform/gcp/tofu.sh plan

gcp-up: ## Live, the owner's step: apply platform/gcp/infra to the lab project from Cloud Shell (GCP_PROJECT; agents' credentials cannot)
	platform/gcp/tofu.sh apply

gcp-down: ## Live, the owner's step: destroy what platform/gcp/infra created on the lab project (GCP_PROJECT)
	platform/gcp/tofu.sh destroy

gcp-cost-check: ## Live, read-only: exit 1 on any cost this month on the lab project's billing export, 3 when not yet provable (GCP_PROJECT; #233)
	platform/gcp/cost-check.sh
