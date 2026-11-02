"""Publish the lab's native BigQuery data agent from the generated context, staging then published (#207).

Reads the v1 `Context` build_catalog.py writes (default: `dbt/target/bigquery/catalog/data_agent/context.json`,
from `make bigquery-check`), points its tables, verified queries and system instruction at the lab project,
and makes the data agent `projects/<GCP_PROJECT>/locations/<location>/dataAgents/<agent id>` hold it:
- missing: create it with the context as `dataAnalyticsAgent.stagingContext`;
- present: PATCH, with an update mask, only the fields that differ (the staging context, the display name and
  description, the BigQuery Agent Analytics fields); nothing when none differ;
- then publish: PATCH `dataAnalyticsAgent.publishedContext` to the staging context, when it differs (v1 has no
  publish method: the Chat API reads the published context, so publishing is writing that field).
A second run with the same context makes no write and says so. Every mutation is a long-running operation,
polled until done or `--timeout`. Every request body is validated first against the pinned discovery schemas
(`schemas/`, `pin_schema.py`), and every URL is built from the pinned method paths.

Location `us` by default: the lab's datasets are in BigQuery's US multi-region, and the `us` endpoint keeps the
agent and its ML processing in that jurisdiction, which `global` does not; an agent at any location reads
datasets in any location (https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/data-residency).
BigQuery Agent Analytics (Preview, enrolled projects only) is on, into `ops.data_agent_analytics`, unless
`--no-analytics`: a project that is not enrolled stores the fields and writes no rows.

Credentials, as platform/gcp/tofu.sh picks them, first that holds: GCP_ACCESS_TOKEN; a cloud session's
proxy-injected CLOUDSDK_AUTH_ACCESS_TOKEN; a short-lived token of a signed-in gcloud account ($GCP_ACCOUNT,
default the active one). Refuses without GCP_PROJECT. `--dry-run` prints the bodies and sends nothing.

Usage: python3 platform/gcp/data-agent/publish.py [--context PATH] [--dry-run] [--no-publish] [--no-analytics]
Run by `make gcp-data-agent` (Live: the cost check before and after).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PIN = HERE / "schemas" / "geminidataanalytics-v1-data-agent.json"
CONTEXT = (
    REPO / "dbt" / "target" / "bigquery" / "catalog" / "data_agent" / "context.json"
)
AGENT_ID = "pplk8s-semantic"
LOCATION = "us"
ANALYTICS_TABLE = "ops.data_agent_analytics"
DISPLAY_NAME = "pplk8s semantic layer"
DESCRIPTION = (
    "The lab's metrics, glossary terms and verified queries, generated from the dbt semantic layer "
    "(dbt/scripts/build_catalog.py) and published by platform/gcp/data-agent/publish.py."
)
STAGING = "dataAnalyticsAgent.stagingContext"
PUBLISHED = "dataAnalyticsAgent.publishedContext"
# The fields this publisher owns on the agent; any other field is left as the console or the API set it.
MANAGED = (
    "displayName",
    "description",
    "bigqueryAgentAnalyticsEnabled",
    "bigqueryAgentAnalyticsTable",
    STAGING,
)
REQUIRED = re.compile(r"\s*Required\.")
AT_MOST_BYTES = re.compile(r"[Mm]ust be at most ([\d,]+) bytes")

# (method, url, JSON body or None) -> (HTTP status, JSON body); tests pass a fake.
Transport = Callable[[str, str, dict | None], tuple[int, dict]]


class PublishError(Exception):
    pass


def load_pin(path: Path = PIN) -> dict:
    return json.loads(path.read_text())


def schema_problems(
    value: object, spec: dict, schemas: dict, path: str = ""
) -> list[str]:
    """Walk a value against a discovery-document schema, as dbt/scripts/check_catalog.py does for context.json,
    plus maps (`additionalProperties`) and enums: unknown keys, "Required." fields, byte bounds, output-only and
    deprecated fields, types."""
    if "$ref" in spec:
        if spec["$ref"] not in schemas:
            return [f"{path or 'the body'}: {spec['$ref']} is not in the pinned schema"]
        return schema_problems(value, schemas[spec["$ref"]], schemas, path)
    kind = spec.get("type")
    if kind == "any":
        return []
    if kind == "object":
        if not isinstance(value, dict):
            return [f"{path or 'the body'}: expected an object"]
        if "additionalProperties" in spec and "properties" not in spec:
            return [
                problem
                for key, item in value.items()
                for problem in schema_problems(
                    item, spec["additionalProperties"], schemas, f"{path}.{key}"
                )
            ]
        properties = spec.get("properties", {})
        found = [
            f"{path or 'the body'}: unknown key {key!r}"
            for key in sorted(value.keys() - properties.keys())
        ]
        for key, prop in properties.items():
            where = f"{path}.{key}" if path else key
            if value.get(key) in (None, "", [], {}):
                if REQUIRED.match(prop.get("description", "")):
                    found.append(f"{where}: required")
                continue
            if prop.get("readOnly") or prop.get("deprecated"):
                found.append(
                    f"{where}: {'output only' if prop.get('readOnly') else 'deprecated'}"
                )
            found += schema_problems(value[key], prop, schemas, where)
        return found
    if kind == "array":
        if not isinstance(value, list):
            return [f"{path}: expected a list"]
        return [
            problem
            for i, item in enumerate(value)
            for problem in schema_problems(item, spec["items"], schemas, f"{path}[{i}]")
        ]
    if kind == "string":
        if not isinstance(value, str):
            return [f"{path}: expected text"]
        if "enum" in spec and value not in spec["enum"]:
            return [f"{path}: {value!r} is not one of {spec['enum']}"]
        bound = AT_MOST_BYTES.search(spec.get("description", ""))
        if bound and len(value.encode()) > int(bound[1].replace(",", "")):
            return [f"{path}: {len(value.encode())} bytes, more than {bound[1]}"]
        return []
    if kind in ("boolean", "integer", "number"):
        types = {"boolean": bool, "integer": int, "number": (int, float)}[kind]
        return [] if isinstance(value, types) else [f"{path}: expected a {kind}"]
    return [f"{path}: schema type {kind!r} is not handled"]


def check_body(body: dict, pin: dict) -> None:
    """Refuse a request body the pinned `DataAgent` schema does not accept."""
    found = schema_problems(body, {"$ref": pin["root"]}, pin["schemas"])
    if found:
        raise PublishError(
            f"the request body does not validate against the pinned v1 schema (revision {pin['revision']}):\n  "
            + "\n  ".join(found)
        )


def url(
    pin: dict, method: str, location: str, query: dict | None = None, **path: str
) -> str:
    """A method's URL from its pinned path (`v1/{+name}`) on the location's endpoint; unknown parameters refused."""
    spec = pin["methods"][method]
    unknown = (set(path) | set(query or {})) - set(spec["parameters"])
    if unknown:
        raise PublishError(
            f"{method}: {sorted(unknown)} are not parameters of the pinned method"
        )
    rendered = re.sub(r"\{\+?(\w+)\}", lambda m: path[m[1]], spec["path"])
    return f"{endpoint(location)}/{rendered}" + (
        f"?{urllib.parse.urlencode(query)}" if query else ""
    )


def endpoint(location: str) -> str:
    """The service endpoint of a location (data-residency page): global, a multi-region (`us`, `eu`) or a region."""
    if location == "global":
        return "https://geminidataanalytics.googleapis.com"
    if location in ("us", "eu"):
        return f"https://geminidataanalytics.{location}.rep.googleapis.com"
    return f"https://geminidataanalytics-{location}.googleapis.com"


def retarget(context: dict, project: str) -> dict:
    """The context with its tables in `project`: build_catalog.py names the dbt target's project (the offline
    `bigquery` target says `pplk8s-lab`) in each table reference, each verified query's backticked table names and
    the system instruction's table names, so all three move together, or none if they already name `project`."""
    refs = ((context.get("datasourceReferences") or {}).get("bq") or {}).get(
        "tableReferences"
    ) or []
    sources = {ref.get("projectId") for ref in refs}
    if not refs or None in sources or len(sources) != 1:
        raise PublishError(
            f"context.json: expected BigQuery tables of one project, found {sorted(map(str, sources))}"
        )
    (source,) = sources
    if source == project:
        return context
    qualifier = re.compile(rf"(?<![\w-]){re.escape(source)}(?=[`.])")
    moved = json.loads(qualifier.sub(project, json.dumps(context)))
    for ref in moved["datasourceReferences"]["bq"]["tableReferences"]:
        ref["projectId"] = project
    return moved


def analytics_table(spec: str, project: str) -> dict:
    """`dataset.table` or `project.dataset.table` as the v1 `BigQueryTableReference` the field takes; the API
    rejects a table outside the agent's project, so this does first."""
    parts = spec.split(".")
    if len(parts) == 2:
        parts = [project, *parts]
    if len(parts) != 3 or not all(parts):
        raise PublishError(f"--analytics-table {spec!r}: expected dataset.table")
    if parts[0] != project:
        raise PublishError(
            f"--analytics-table {spec!r}: the table must be in the agent's project, {project}"
        )
    return dict(zip(("projectId", "datasetId", "tableId"), parts, strict=True))


def desired(context: dict, analytics: dict | None) -> dict:
    """The `DataAgent` body this publisher owns: the context as the staging context, and the analytics fields."""
    agent = {
        "displayName": DISPLAY_NAME,
        "description": DESCRIPTION,
        "dataAnalyticsAgent": {"stagingContext": context},
    }
    if analytics:
        agent |= {
            "bigqueryAgentAnalyticsEnabled": True,
            "bigqueryAgentAnalyticsTable": analytics,
        }
    return agent


def canonical(value: object) -> object:
    """A value as the API echoes it in JSON: proto3 leaves out empty and default fields."""
    if isinstance(value, dict):
        kept = {k: canonical(v) for k, v in value.items()}
        return {k: v for k, v in kept.items() if v not in (None, "", [], {}, False, 0)}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    return value


def field(agent: dict, path: str) -> object:
    for part in path.split("."):
        agent = (agent or {}).get(part)
    return agent


def only(agent: dict, paths: list[str]) -> dict:
    """The part of `agent` the update mask names, nested as the API reads it."""
    body: dict = {}
    for path in paths:
        value = field(agent, path)
        if value is None:
            continue  # in the mask but absent: the API clears the field
        *parents, leaf = path.split(".")
        node = body
        for part in parents:
            node = node.setdefault(part, {})
        node[leaf] = value
    return body


class Publisher:
    def __init__(
        self,
        transport: Transport,
        project: str,
        location: str = LOCATION,
        agent_id: str = AGENT_ID,
        *,
        pin: dict | None = None,
        timeout: float = 300,
        interval: float = 2,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        log: Callable[[str], None] = print,
    ) -> None:
        self.transport, self.project, self.location, self.agent_id = (
            transport,
            project,
            location,
            agent_id,
        )
        self.pin = pin or load_pin()
        self.timeout, self.interval, self.sleep, self.clock, self.log = (
            timeout,
            interval,
            sleep,
            clock,
            log,
        )
        self.parent = f"projects/{project}/locations/{location}"
        self.name = f"{self.parent}/dataAgents/{agent_id}"

    def call(
        self,
        method: str,
        target: str,
        body: dict | None = None,
        *,
        missing_ok: bool = False,
    ) -> dict | None:
        status, payload = self.transport(method, target, body)
        if status == 404 and missing_ok:
            return None
        if not 200 <= status < 300:
            error = (payload or {}).get("error", {})
            raise PublishError(
                f"{method} {target}: HTTP {status} {error.get('status', '')}: {error.get('message', payload)}"
            )
        return payload

    def wait(self, operation: dict, what: str) -> dict:
        """Poll a long-running operation until done: its response (the agent), or its error raised."""
        deadline = self.clock() + self.timeout
        while not operation.get("done"):
            if self.clock() >= deadline:
                raise PublishError(
                    f"{what}: operation {operation.get('name')} not done after {self.timeout:g} s; it may still finish: "
                    "run again once it has (the publisher is idempotent)"
                )
            self.sleep(self.interval)
            operation = self.call(
                "GET",
                url(self.pin, "operations.get", self.location, name=operation["name"]),
            )
        if operation.get("error"):
            error = operation["error"]
            raise PublishError(
                f"{what}: operation failed: {error.get('code')} {error.get('message')}"
            )
        return operation.get("response") or {}

    def publish(self, agent: dict, *, publish: bool = True) -> list[str]:
        """Make the data agent hold `agent` (a `desired` body), staging then published; the writes made."""
        check_body(agent, self.pin)
        writes = []
        current = self.call(
            "GET", url(self.pin, "get", self.location, name=self.name), missing_ok=True
        )
        if current is not None and current.get("deleteTime"):
            raise PublishError(
                f"{self.name} is soft-deleted (deleteTime {current['deleteTime']}, purged at {current.get('purgeTime')}): "
                "undelete it in the console or wait for the purge"
            )
        if current is None:
            body = only(agent, list(MANAGED))
            check_body(body, self.pin)
            target = url(
                self.pin,
                "create",
                self.location,
                {"dataAgentId": self.agent_id},
                parent=self.parent,
            )
            current = self.wait(self.call("POST", target, body), f"create {self.name}")
            writes.append(f"created {self.name} with the staging context")
        else:
            mask = [
                path
                for path in MANAGED
                if canonical(field(current, path)) != canonical(field(agent, path))
            ]
            if mask:
                body = only(agent, mask)
                check_body(body, self.pin)
                target = url(
                    self.pin,
                    "patch",
                    self.location,
                    {"updateMask": ",".join(mask)},
                    name=self.name,
                )
                current = self.wait(
                    self.call("PATCH", target, body), f"update {self.name}"
                )
                writes.append(f"updated {', '.join(mask)}")
        staging = field(agent, STAGING)
        if publish and canonical(field(current, PUBLISHED)) != canonical(staging):
            body = {"dataAnalyticsAgent": {"publishedContext": staging}}
            check_body(body, self.pin)
            target = url(
                self.pin,
                "patch",
                self.location,
                {"updateMask": PUBLISHED},
                name=self.name,
            )
            self.wait(self.call("PATCH", target, body), f"publish {self.name}")
            writes.append("published the staging context")
        for write in writes:
            self.log(f"publish.py: {write}")
        if not writes:
            self.log(
                f"publish.py: {self.name} already holds this context, staged and published: no write"
            )
        return writes


def access_token(env: dict, run: Callable = subprocess.run) -> str:
    """The bearer token, as platform/gcp/tofu.sh picks it."""
    if env.get("GCP_ACCESS_TOKEN"):
        return env["GCP_ACCESS_TOKEN"]
    if env.get("CLOUDSDK_AUTH_ACCESS_TOKEN"):
        return env[
            "CLOUDSDK_AUTH_ACCESS_TOKEN"
        ]  # a cloud session: the egress proxy replaces it
    account = (
        env.get("GCP_ACCOUNT")
        or run(
            ["gcloud", "config", "get-value", "account"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    )
    if not account:
        raise PublishError(
            "no credential: set GCP_ACCESS_TOKEN or sign in to gcloud (platform/gcp/README.md)"
        )
    print(f"publish.py: acting as {account} (GCP_ACCOUNT=<account> picks another)")
    return run(
        ["gcloud", "auth", "print-access-token", f"--account={account}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def http_transport(token: str, project: str) -> Transport:
    """The real transport: JSON over HTTPS, the quota billed to the lab project (`x-goog-user-project`)."""

    def send(method: str, target: str, body: dict | None) -> tuple[int, dict]:
        request = urllib.request.Request(
            target,
            data=None if body is None else json.dumps(body).encode(),
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "x-goog-user-project": project,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            raw = error.read()
            try:
                return error.code, json.loads(raw or b"{}")
            except ValueError:
                return error.code, {
                    "error": {"message": raw.decode(errors="replace")[:500]}
                }

    return send


def main(
    argv: list[str] | None = None,
    env: dict | None = None,
    transport: Transport | None = None,
) -> int:
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--context", type=Path, default=CONTEXT, help="build_catalog.py's context.json"
    )
    parser.add_argument("--agent-id", default=AGENT_ID)
    parser.add_argument(
        "--location", default=LOCATION, help="global, us, eu or a region (default us)"
    )
    parser.add_argument(
        "--analytics-table",
        default=ANALYTICS_TABLE,
        help="dataset.table for Agent Analytics rows",
    )
    parser.add_argument(
        "--no-analytics", action="store_true", help="leave BigQuery Agent Analytics off"
    )
    parser.add_argument(
        "--no-publish", action="store_true", help="update the staging context only"
    )
    parser.add_argument(
        "--timeout", type=float, default=300, help="seconds to wait for each operation"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the bodies and send nothing"
    )
    args = parser.parse_args(argv)

    project = env.get("GCP_PROJECT")
    if not project:
        print(
            "publish.py: GCP_PROJECT is unset: the data agent goes to the lab project and needs its id "
            "(platform/gcp/README.md)",
            file=sys.stderr,
        )
        return 2
    try:
        if not args.context.is_file():
            raise PublishError(f"{args.context} is missing: run make bigquery-check")
        context = retarget(json.loads(args.context.read_text()), project)
        analytics = (
            None
            if args.no_analytics
            else analytics_table(args.analytics_table, project)
        )
        agent = desired(context, analytics)
        pin = load_pin()
        check_body(agent, pin)
        if args.dry_run:
            name = f"projects/{project}/locations/{args.location}/dataAgents/{args.agent_id}"
            print(
                f"publish.py: dry run for {name} (revision {pin['revision']}): create or update with"
            )
            print(json.dumps(only(agent, list(MANAGED)), indent=2))
            print(f"publish.py: then PATCH updateMask={PUBLISHED} with")
            print(
                json.dumps(
                    {"dataAnalyticsAgent": {"publishedContext": context}}, indent=2
                )
            )
            return 0
        transport = transport or http_transport(access_token(env), project)
        publisher = Publisher(
            transport,
            project,
            args.location,
            args.agent_id,
            pin=pin,
            timeout=args.timeout,
        )
        publisher.publish(agent, publish=not args.no_publish)
    except PublishError as error:
        print(f"publish.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
