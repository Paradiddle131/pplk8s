#!/usr/bin/env bash
# What it measures: what open-source Lightdash makes of the lab's dbt project with no licence, no dbt platform
# and no warehouse: its CLI (`lightdash compile`, the step `lightdash deploy` runs before uploading) translates
# the project's MetricFlow semantic models and metrics into Lightdash explores and metrics from manifest.json
# alone; the probe prints the CLI's own summary and errors and counts which of the project's metrics it kept.
# How to run (from the repo root): bash docs/research/semantic-bet/probes/334_lightdash.sh [out-dir]
# Needs: uv, npx (Node itself comes from npm's node@24 package; the CLI needs Node >= 24).
# Env: LIGHTDASH_CLI (default @lightdash/cli@3.128.0). Offline: `dbt parse` and `lightdash compile
# --skip-dbt-compile --no-warehouse-credentials` open no connection; npx and uv fetch packages.
# Writes <out-dir>/dbt (the project copy and its manifest) and <out-dir>/compile.log
# (default ${TMPDIR:-/tmp}/semantic-bet-334-lightdash).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../../.." && pwd)"
# shellcheck source-path=SCRIPTDIR source=../../../../tests/e2e/lib/dbt-deps.sh
source "$REPO/tests/e2e/lib/dbt-deps.sh"
OUT=${1:-${TMPDIR:-/tmp}/semantic-bet-334-lightdash}
PROJECT="$OUT/dbt"
CLI=${LIGHTDASH_CLI:-@lightdash/cli@3.128.0}
export DBT_TARGET=dev DBT_PROFILES_DIR="$PROJECT"

rm -rf "$OUT" && mkdir -p "$PROJECT"
(cd "$REPO/dbt" && tar --exclude=./target --exclude=./logs --exclude=./dbt_packages -cf - .) | tar -xf - -C "$PROJECT"
dbt_deps "$PROJECT"
(cd "$PROJECT" && uv run --quiet --no-project --with-requirements requirements-postgres.txt dbt parse --quiet)

# `--no-warehouse-credentials` skips dbt and the warehouse catalog: types come from the YAML and the manifest.
# The CLI asks `dbt --version` even with --skip-dbt-compile, so it runs inside dbt's environment.
(cd "$PROJECT" && uv run --quiet --no-project --with-requirements requirements-postgres.txt \
  npx -y -p node@24 -p "$CLI" lightdash compile --project-dir . --profiles-dir . \
  --skip-dbt-compile --no-warehouse-credentials --no-version-check --verbose) >"$OUT/compile.log" 2>&1 ||
  echo "lightdash compile exited $?"
grep -E "^(> (Translated|Invalid)|Compiled|- ERROR>)" "$OUT/compile.log"

python3 -I - "$PROJECT/target/manifest.json" "$OUT/compile.log" <<'PY'
import collections
import json
import re
import sys

m = json.load(open(sys.argv[1]))
log = open(sys.argv[2]).read()
kinds = {x["name"]: x["type"] for x in m.get("metrics", {}).values()}
print(f"manifest: {len(m.get('semantic_models', {}))} semantic models, {len(kinds)} metrics: "
      + ", ".join(f"{t} {n}" for t, n in sorted(collections.Counter(kinds.values()).items())))
skipped = dict(re.findall(r'Skipped MetricFlow metric "([^"]+)": (.+)', log))
for line in re.findall(r"Translated \d+ MetricFlow metric.*", log):
    print(line)
for t in sorted(set(kinds.values())):
    names = [n for n, k in kinds.items() if k == t]
    lost = [n for n in names if n in skipped]
    print(f"  {t}: {len(names) - len(lost)} of {len(names)} translated")
reasons = collections.Counter(re.sub(r'"[^"]+"|\([^)]*\)', "…", r) for r in skipped.values())
for reason, n in reasons.most_common():
    print(f"  skipped {n}: {reason}")
PY
