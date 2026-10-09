# Single entry point for the lab. `make help` lists targets.
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# Kind node image: Kubernetes 1.36, the GKE Regular-channel default (Oct 2026); see PLAN.md D4.
NODE_IMAGE ?= kindest/node:v1.36.4@sha256:099e049362a1526b2db71494e1947aae99bd16290d7c895f2b7ea312e3cbfaed
export NODE_IMAGE

# Workload images, tagged for the local registry so Phase 2 can push them as-is.
ELF_IMAGE ?= localhost:5001/el-factory:0.1.0
DBT_IMAGE ?= localhost:5001/dbt:0.1.0
export ELF_IMAGE DBT_IMAGE

# Airflow image: 3.3.1 base (D1) plus our suffix revision, bumped when the Dockerfile or requirements change.
AIRFLOW_IMAGE ?= localhost:5001/airflow:3.3.1-pplk8s.3
export AIRFLOW_IMAGE

.PHONY: help tools lint cluster-up cluster-down cluster-check services-up services-down services-reset build el-factory-up el-factory-down dbt-build test airflow-test phase1-check push workloads-up workloads-down dbt-job phase2-check airflow-image airflow-up airflow-down airflow-ui phase3-check phase4-check

help: ## List targets
	@grep -hE '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

tools: ## Install pinned kind, helm, k9s into ~/.local/bin
	scripts/install-tools.sh

cluster-up: ## Create the kind cluster and local registry (localhost:5001)
	platform/kind/cluster-up.sh

cluster-down: ## Delete the kind cluster and local registry
	platform/kind/cluster-down.sh

cluster-check: ## Verify workers are Ready and the registry serves images in-cluster
	platform/kind/cluster-check.sh

services-up: ## Start warehouse Postgres (localhost:5433) and fake-gcs (localhost:4480)
	platform/compose/up.sh

services-down: ## Stop the out-of-cluster services, keeping their data
	docker compose -f platform/compose/compose.yaml down

services-reset: ## Stop the out-of-cluster services and delete their data
	docker compose -f platform/compose/compose.yaml down -v

build: ## Build the EL Factory lite and dbt images
	docker build -t $(ELF_IMAGE) services/el-factory
	docker build -t $(DBT_IMAGE) dbt

el-factory-up: services-up ## Run EL Factory lite on localhost:8090 against the Compose services
	scripts/el-factory-local.sh up

el-factory-down: ## Stop the local EL Factory lite container
	scripts/el-factory-local.sh down

STAGE ?= bronze
dbt-build: ## Run `dbt build --select $(STAGE)` (bronze|silver|gold|exposed) against the warehouse
	docker run --rm --network pplk8s $(DBT_IMAGE) build --select $(STAGE)

airflow-test: ## Lint and test the Airflow DAGs and workload seam (airflow/)
	cd airflow && uv run ruff check . && uv run ruff format --check . && uv run pytest -q

test: airflow-test ## Run unit tests and linters
	cd services/el-factory && uv run ruff check . && uv run ruff format --check . && uv run pytest -q

push: build ## Push the EL Factory and dbt images to the local registry (localhost:5001)
	docker push $(ELF_IMAGE)
	docker push $(DBT_IMAGE)

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

airflow-up: services-up ## Deploy Airflow (image, secrets, RBAC, Helm chart, pool) into namespace airflow
	platform/helm/airflow/deploy.sh

airflow-down: ## Uninstall the Airflow release (keeps the metadata DB, secrets and PV)
	helm --kube-context kind-pplk8s uninstall airflow -n airflow --wait

airflow-ui: ## Port-forward the Airflow UI/API to http://localhost:8080 (admin/admin)
	kubectl --context kind-pplk8s -n airflow port-forward svc/airflow-api-server 8080:8080

phase3-check: airflow-up ## Phase 3 exit check: hello DAG on a Celery worker, upgrade + rollback stays healthy
	tests/e2e/phase3-check.sh

phase4-check: airflow-up workloads-up ## Phase 4 exit check: full sales_elt run, idempotent clear/re-run, kill + FAIL_RATE retry drills
	tests/e2e/phase4-check.sh

lint: ## Lint shell scripts (shellcheck via uvx)
	uvx --from shellcheck-py shellcheck -x -P SCRIPTDIR scripts/*.sh platform/*/*.sh platform/helm/airflow/*.sh platform/k8s/*.sh tests/e2e/*.sh
