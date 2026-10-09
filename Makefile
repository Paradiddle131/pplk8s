# Single entry point for the lab. `make help` lists targets.
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# Kind node image: Kubernetes 1.36, the GKE Regular-channel default (Oct 2026); see PLAN.md D4.
NODE_IMAGE ?= kindest/node:v1.36.4@sha256:099e049362a1526b2db71494e1947aae99bd16290d7c895f2b7ea312e3cbfaed
export NODE_IMAGE

.PHONY: help tools lint cluster-up cluster-down cluster-check services-up services-down services-reset

help: ## List targets
	@grep -hE '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

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

lint: ## Lint shell scripts (shellcheck via uvx)
	uvx --from shellcheck-py shellcheck scripts/*.sh platform/*/*.sh
