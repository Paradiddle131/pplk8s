"""The bet's floor: a data agent with nothing but the tables, the arm native-bare (#372, Q2, Q8).

What it builds: `bet_bare`, copies of the 16 silver tables native-kc-max reads (`bq cp`, free), so no Knowledge
Catalog dbt entry links to them and they carry no BigQuery description; and the data agent `bet-bare` over those
copies plus native-kc-max's extra tables (the time spine and RULE.md's `legacy` tables, as they stand), with
native-kc's one-line instruction, no glossary, no verified queries, and the lab's byte cap. So its reach equals
native-kc-max's, and the two differ only in the context native-kc-max adds (descriptions and a linked glossary).

Run from the repo root, after `bash docs/research/semantic-bet/probes/326_dbt_artifacts.sh` (offline, the table
list comes from its manifests, as 360_kc_max.py's does):
  python3 -I docs/research/semantic-bet/probes/372_bare_agent.py --dry-run
      offline: prints the copies and the agent body; sends nothing.
  GCP_PROJECT=pplk8s-lab-001 python3 -I docs/research/semantic-bet/probes/372_bare_agent.py --publish
      live, after `make gcp-cost-check` and `make gcp-usage-check`: the missing copies, a check that none carries
      a description, then creates or updates and publishes `bet-bare` and reads it back.
Then score it through the runner: 328_mcp_live.py --agent 354_data_agent.py --arm native-bare.
Env: GCP_PROJECT (required live); the credential as platform/gcp/data-agent/publish.py picks it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COPY = "bet_bare"
AGENT_ID = "bet-bare"


def kc_max():
    """360_kc_max.py, pointed at this arm's dataset and agent (its context() and copies read COPY)."""
    spec = importlib.util.spec_from_file_location("kc_max_360", HERE / "360_kc_max.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.COPY = COPY
    module.AGENT_ID = AGENT_ID
    return module


def copies(kc, tables: list[str], project: str) -> int:
    """The missing copies, then a check that no copy carries a table or column description."""
    if kc.bq("show", f"{project}:{COPY}").returncode:
        made = kc.bq("mk", "--location=US", "--dataset", f"{project}:{COPY}")
        if made.returncode:
            print(f"372_bare_agent: bq mk {COPY}: {made.stdout}{made.stderr}")
            return 2
    for table in tables:
        if kc.bq("show", f"{project}:{COPY}.{table}").returncode:
            done = kc.bq(
                "cp",
                "-n",
                f"{project}:{kc.SOURCE}.{table}",
                f"{project}:{COPY}.{table}",
            )
            if done.returncode:
                print(f"372_bare_agent: copy {table}: {done.stderr.strip()}")
                return 2
        shown = json.loads(
            kc.bq("show", "--format=json", f"{project}:{COPY}.{table}").stdout
        )
        described = [
            f["name"] for f in shown["schema"]["fields"] if f.get("description")
        ]
        if shown.get("description") or described:
            print(
                f"372_bare_agent: {COPY}.{table} carries descriptions ({described}): not bare"
            )
            return 2
        print(f"372_bare_agent: copy {table}: ok, no descriptions")
    return 0


def publish(kc, tables: list[str], project: str) -> int:
    publisher = kc.publisher_module()
    cap = publisher.query_cap()
    send = publisher.http_transport(publisher.access_token(dict(os.environ)), project)
    agent = publisher.desired(
        kc.context(project, tables, cap),
        None,
        display_name="bet native-bare",
        description=(
            "The semantic bet's floor (native-bare): native-kc's one-line instruction over bet_bare (silver copied, "
            "no descriptions, no catalog links), the time spine and the legacy tables; nothing else."
        ),
    )
    try:
        writes = publisher.Publisher(send, project, kc.LOCATION, AGENT_ID).publish(
            agent
        )
    except publisher.PublishError as error:
        print(f"372_bare_agent: {AGENT_ID} publish refused: {error}")
        return 2
    print(f"372_bare_agent: {AGENT_ID} writes {writes}")
    return 0


def main(argv: list[str]) -> int:
    kc = kc_max()
    target = (
        Path(os.environ.get("TMPDIR", "/tmp")) / "semantic-bet-326" / "dbt" / "target"
    )
    if not (target / "semantic_manifest.json").exists():
        sys.exit(
            f"372_bare_agent: no manifests in {target}: run 326_dbt_artifacts.sh first (offline)"
        )
    tables = kc.Project(target).tables
    project = os.environ.get("GCP_PROJECT", kc.PROJECT)
    if "--dry-run" in argv:
        print(
            f"copies: {len(tables)} tables {kc.SOURCE} -> {COPY}: {', '.join(tables)}"
        )
        print("agent: " + json.dumps(kc.context(project, tables, None)))
        return 0
    if "--publish" in argv:
        if not os.environ.get("GCP_PROJECT"):
            sys.exit("GCP_PROJECT is required")
        return copies(kc, tables, project) or publish(kc, tables, project)
    sys.exit("usage: 372_bare_agent.py --dry-run | --publish")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
