## 2026-10-30 — Maintenance — image builds share a layer cache on ghcr.io

- Done: every `make` image build reads and writes `ghcr.io/paradiddle131/pplk8s/<image>:buildcache` (BuildKit registry cache, `mode=max`, `ignore-error=true`) when `BUILD_CACHE` is set: by default on cloud, where the egress proxy logs ghcr.io requests in as the owner; a laptop opts in after `docker login ghcr.io`. The drill image keeps its own cache name (`airflow-drill`). `cloud-docker.sh` no longer retags `astral/uv`: ghcr.io serves public images since the environment's ghcr.io secret became a base64 Bearer token.
- Evidence: see the PR.
- Decisions: a registry layer cache rather than pushing finished images by hand: it fills itself on every build, cannot serve a stale layer, and needs no tag discipline; claude-dotfiles' `image-cache` skill holds the way of working for every repo.
- Open: none.
