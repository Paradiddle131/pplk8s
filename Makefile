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

.PHONY: help tools lint cluster-up cluster-down cluster-check services-up services-down services-reset build el-factory-up el-factory-down dbt-build test phase1-check

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

test: ## Run unit tests and linters
	cd services/el-factory && uv run ruff check . && uv run ruff format --check . && uv run pytest -q

phase1-check: services-up build ## Phase 1 exit check: extract via curl, re-run idempotently, dbt build every stage
	tests/e2e/phase1-check.sh

lint: ## Lint shell scripts (shellcheck via uvx)
	uvx --from shellcheck-py shellcheck scripts/*.sh platform/*/*.sh tests/e2e/*.sh
