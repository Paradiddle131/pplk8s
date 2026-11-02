"""data-agent/publish.py against a fake Conversational Analytics API, and its pinned schema (#207)."""

from __future__ import annotations

import copy
import json
import re
import sys
import urllib.parse
from pathlib import Path

import pytest

GCP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GCP / "data-agent"))

import pin_schema
from publish import (
    MANAGED,
    PIN,
    Publisher,
    PublishError,
    analytics_table,
    capped,
    desired,
    load_pin,
    main,
    query_cap,
    retarget,
)

PROJECT = "lab-project"
NAME = f"projects/{PROJECT}/locations/us/dataAgents/pplk8s-semantic"
ENDPOINT = "https://geminidataanalytics.us.rep.googleapis.com/v1/"
DBT_PIN = (
    GCP.parent.parent
    / "dbt"
    / "scripts"
    / "schemas"
    / "geminidataanalytics-v1-context.json"
)


def context(project: str = "pplk8s-lab", total: str = "sum(amount)") -> dict:
    """A small v1 Context as build_catalog.py writes it on the offline `bigquery` target."""
    return {
        "datasourceReferences": {
            "bq": {
                "tableReferences": [
                    {
                        "projectId": project,
                        "datasetId": "silver",
                        "tableId": "orders",
                        "schema": {
                            "description": "One row per order.",
                            "fields": [{"name": "amount", "type": "NUMERIC"}],
                        },
                    }
                ]
            }
        },
        "systemInstruction": f"- tables:\n  - table:\n    - name: {project}.silver.orders\n",
        "glossaryTerms": [{"displayName": "Revenue", "description": "Order amounts."}],
        "exampleQueries": [
            {
                "naturalLanguageQuestion": "What is revenue?",
                "sqlQuery": f"SELECT {total} AS revenue FROM `{project}`.`silver`.`orders`",
            }
        ],
    }


class FakeApi:
    """The v1 dataAgents surface the publisher uses: get, create and patch as operations, operations.get."""

    def __init__(self, polls: int = 1, error: dict | None = None) -> None:
        self.agents: dict[str, dict] = {}
        self.operations: dict[str, dict] = {}
        self.calls: list[tuple[str, str, dict]] = []
        self.polls, self.error = polls, error

    def __call__(self, method: str, url: str, body: dict | None) -> tuple[int, dict]:
        assert url.startswith(ENDPOINT), url
        parsed = urllib.parse.urlsplit(url)
        path = parsed.path.removeprefix("/v1/")
        query = dict(urllib.parse.parse_qsl(parsed.query))
        self.calls.append((method, path, query))
        if method == "GET" and "/operations/" in path:
            op = self.operations[path]
            op["polls"] -= 1
            if op["polls"] <= 0:
                return 200, {"name": path, "done": True} | op["result"]
            return 200, {"name": path, "done": False}
        if method == "GET":
            return (
                (200, copy.deepcopy(self.agents[path]))
                if path in self.agents
                else (404, {"error": {"code": 404}})
            )
        if method == "POST":
            name = f"{path}/{query['dataAgentId']}"
            assert name not in self.agents
            self.agents[name] = {"name": name, **copy.deepcopy(body)}
            return 200, self.operation(name)
        if method == "PATCH":
            agent = self.agents[path]
            for field in query["updateMask"].split(","):
                *parents, leaf = field.split(".")
                source, target = body, agent
                for part in parents:
                    source, target = source.get(part, {}), target.setdefault(part, {})
                if leaf in source:
                    target[leaf] = copy.deepcopy(source[leaf])
                else:
                    target.pop(leaf, None)
            return 200, self.operation(path)
        raise AssertionError(f"unexpected {method} {url}")

    def operation(self, name: str) -> dict:
        op = f"projects/{PROJECT}/locations/us/operations/op-{len(self.operations)}"
        result = (
            {"error": self.error}
            if self.error
            else {"response": copy.deepcopy(self.agents[name])}
        )
        self.operations[op] = {"polls": self.polls, "result": result}
        return {"name": op, "done": False}

    def writes(self) -> list[tuple[str, str, dict]]:
        return [call for call in self.calls if call[0] != "GET"]


def publisher(api: FakeApi, **kwargs) -> Publisher:
    return Publisher(api, PROJECT, sleep=lambda _: None, log=lambda _: None, **kwargs)


def agent(total: str = "sum(amount)") -> dict:
    return desired(
        retarget(context(total=total), PROJECT),
        analytics_table("agent_logs.data_agent_conversations", PROJECT),
    )


def test_creates_when_missing_then_publishes() -> None:
    api = FakeApi()
    writes = publisher(api).publish(agent())
    assert writes == [
        f"created {NAME} with the staging context",
        "published the staging context",
    ]
    create, publish = api.writes()
    assert create[:2] == ("POST", f"projects/{PROJECT}/locations/us/dataAgents")
    assert create[2] == {"dataAgentId": "pplk8s-semantic"}
    assert publish == (
        "PATCH",
        NAME,
        {"updateMask": "dataAnalyticsAgent.publishedContext"},
    )
    stored = api.agents[NAME]
    assert (
        stored["dataAnalyticsAgent"]["publishedContext"]
        == stored["dataAnalyticsAgent"]["stagingContext"]
    )
    assert stored["bigqueryAgentAnalyticsTable"] == {
        "projectId": PROJECT,
        "datasetId": "agent_logs",
        "tableId": "data_agent_conversations",
    }


def test_a_second_run_with_the_same_context_writes_nothing() -> None:
    api = FakeApi()
    publisher(api).publish(agent())
    logged: list[str] = []
    before = len(api.calls)
    writes = Publisher(api, PROJECT, sleep=lambda _: None, log=logged.append).publish(
        agent()
    )
    assert writes == []
    assert api.calls[before:] == [("GET", NAME, {})]
    assert logged == [
        f"publish.py: {NAME} already holds this context, staged and published: no write"
    ]


def test_a_changed_context_patches_the_staging_context_then_publishes() -> None:
    api = FakeApi()
    publisher(api).publish(agent())
    before = len(api.writes())
    writes = publisher(api).publish(agent(total="sum(amount) - sum(discount)"))
    assert writes == [
        "updated dataAnalyticsAgent.stagingContext",
        "published the staging context",
    ]
    staging, publish = api.writes()[before:]
    assert staging == (
        "PATCH",
        NAME,
        {"updateMask": "dataAnalyticsAgent.stagingContext"},
    )
    assert publish == (
        "PATCH",
        NAME,
        {"updateMask": "dataAnalyticsAgent.publishedContext"},
    )
    published = api.agents[NAME]["dataAnalyticsAgent"]["publishedContext"]
    assert "sum(discount)" in published["exampleQueries"][0]["sqlQuery"]


def test_no_publish_stops_at_the_staging_context() -> None:
    api = FakeApi()
    publisher(api).publish(agent(), publish=False)
    assert [call[0] for call in api.writes()] == ["POST"]
    assert "publishedContext" not in api.agents[NAME]["dataAnalyticsAgent"]


def test_turning_analytics_off_clears_both_fields() -> None:
    api = FakeApi()
    publisher(api).publish(agent())
    publisher(api).publish(desired(retarget(context(), PROJECT), None))
    assert api.writes()[-1] == (
        "PATCH",
        NAME,
        {"updateMask": "bigqueryAgentAnalyticsEnabled,bigqueryAgentAnalyticsTable"},
    )
    assert "bigqueryAgentAnalyticsTable" not in api.agents[NAME]


def test_an_operation_is_polled_until_done() -> None:
    api = FakeApi(polls=3)
    publisher(api).publish(agent())
    polls = [call for call in api.calls if "/operations/" in call[1]]
    assert len(polls) == 6  # three for the create, three for the publish


def test_an_operation_that_never_ends_times_out() -> None:
    api = FakeApi(polls=10**6)
    now = [0.0]

    def sleep(seconds: float) -> None:
        now[0] += seconds

    slow = Publisher(
        api,
        PROJECT,
        timeout=10,
        interval=2,
        sleep=sleep,
        clock=lambda: now[0],
        log=lambda _: None,
    )
    with pytest.raises(PublishError, match="not done after 10 s"):
        slow.publish(agent())


def test_a_failed_operation_raises_its_error() -> None:
    api = FakeApi(error={"code": 3, "message": "table not found"})
    with pytest.raises(PublishError, match="operation failed: 3 table not found"):
        publisher(api).publish(agent())


def test_an_http_error_raises() -> None:
    def denied(method: str, url: str, body: dict | None) -> tuple[int, dict]:
        return 403, {
            "error": {"status": "PERMISSION_DENIED", "message": "no dataAgents.get"}
        }

    with pytest.raises(PublishError, match="HTTP 403 PERMISSION_DENIED"):
        publisher(denied).publish(agent())


def test_a_body_off_the_pinned_schema_is_refused_before_any_call() -> None:
    api = FakeApi()
    bad = agent()
    bad["dataAnalyticsAgent"]["stagingContext"]["glossaryTerms"][0]["synonym"] = (
        "takings"
    )
    del bad["dataAnalyticsAgent"]["stagingContext"]["datasourceReferences"]["bq"][
        "tableReferences"
    ][0]["tableId"]
    bad["createTime"] = "2026-11-02T00:00:00Z"
    with pytest.raises(PublishError) as raised:
        publisher(api).publish(bad)
    message = str(raised.value)
    assert "glossaryTerms[0]: unknown key 'synonym'" in message
    assert "tableReferences[0].tableId: required" in message
    assert "createTime: output only" in message
    assert api.calls == []


def test_a_soft_deleted_agent_is_refused() -> None:
    api = FakeApi()
    api.agents[NAME] = {"name": NAME, "deleteTime": "2026-11-01T00:00:00Z"}
    with pytest.raises(PublishError, match="soft-deleted"):
        publisher(api).publish(agent())
    assert api.writes() == []


def test_every_query_the_agent_runs_is_capped_at_the_free_paths_cap() -> None:
    cap = query_cap()
    assert cap == 1073741824
    body = capped(retarget(context(), PROJECT), cap)
    assert body["options"] == {
        "datasource": {"bigQueryMaxBilledBytes": "1073741824"},
        "model": "MODEL_UNSPECIFIED",
    }
    assert capped(body, cap) == body


def test_retarget_moves_tables_queries_and_instruction_together() -> None:
    moved = retarget(context(), "pplk8s-lab-001")
    text = json.dumps(moved)
    assert (
        moved["datasourceReferences"]["bq"]["tableReferences"][0]["projectId"]
        == "pplk8s-lab-001"
    )
    assert (
        "`pplk8s-lab-001`.`silver`.`orders`" in moved["exampleQueries"][0]["sqlQuery"]
    )
    assert "name: pplk8s-lab-001.silver.orders" in moved["systemInstruction"]
    assert not re.search(r"pplk8s-lab(?!-001)", text)
    assert (
        retarget(moved, "pplk8s-lab-001") == moved
    )  # already there: unchanged, never pplk8s-lab-001-001


def test_retarget_refuses_tables_of_several_projects() -> None:
    mixed = context()
    mixed["datasourceReferences"]["bq"]["tableReferences"].append(
        {"projectId": "other", "datasetId": "silver", "tableId": "returns"}
    )
    with pytest.raises(PublishError, match="one project"):
        retarget(mixed, PROJECT)


def test_the_analytics_table_stays_in_the_project() -> None:
    assert analytics_table(f"{PROJECT}.ops.t", PROJECT)["tableId"] == "t"
    with pytest.raises(PublishError, match="must be in the agent's project"):
        analytics_table("elsewhere.ops.t", PROJECT)
    with pytest.raises(PublishError, match="expected dataset.table"):
        analytics_table("ops", PROJECT)


def write_context(tmp_path: Path) -> Path:
    path = tmp_path / "context.json"
    path.write_text(json.dumps(context()))
    return path


def test_main_refuses_without_gcp_project(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    assert main(["--context", str(write_context(tmp_path)), "--dry-run"], env={}) == 2
    assert "GCP_PROJECT is unset" in capsys.readouterr().err


def test_main_dry_run_prints_the_bodies_and_sends_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    def no_network(method: str, url: str, body: dict | None) -> tuple[int, dict]:
        raise AssertionError("a dry run sent a request")

    argv = ["--context", str(write_context(tmp_path)), "--dry-run"]
    assert main(argv, env={"GCP_PROJECT": PROJECT}, transport=no_network) == 0
    out = capsys.readouterr().out
    assert f"`{PROJECT}`.`silver`.`orders`" in out
    assert "updateMask=dataAnalyticsAgent.publishedContext" in out


def test_main_publishes_through_the_transport(tmp_path: Path) -> None:
    api = FakeApi(polls=0)
    assert (
        main(
            ["--context", str(write_context(tmp_path))],
            env={"GCP_PROJECT": PROJECT},
            transport=api,
        )
        == 0
    )
    assert (
        main(
            ["--context", str(write_context(tmp_path))],
            env={"GCP_PROJECT": PROJECT},
            transport=api,
        )
        == 0
    )
    assert [call[0] for call in api.writes()] == ["POST", "PATCH"]


def test_main_reports_a_missing_context(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    assert (
        main(["--context", str(tmp_path / "none.json")], env={"GCP_PROJECT": PROJECT})
        == 1
    )
    assert "make bigquery-check" in capsys.readouterr().err


def test_the_pin_is_closed_and_holds_the_methods_used() -> None:
    pin = load_pin()
    assert pin["root"] == "GoogleCloudGeminidataanalyticsV1DataAgent"
    for name, schema in pin["schemas"].items():
        assert pin_schema.refs(schema) <= pin["schemas"].keys(), name
    assert {"get", "create", "patch", "operations.get"} <= pin["methods"].keys()
    assert pin["methods"]["patch"]["httpMethod"] == "PATCH"
    assert "updateMask" in pin["methods"]["patch"]["parameters"]
    root = pin["schemas"][pin["root"]]["properties"]
    for path in [*MANAGED, "dataAnalyticsAgent.publishedContext"]:
        head, *rest = path.split(".")
        assert head in root, path
        if rest:
            assert rest[0] in pin["schemas"][root[head]["$ref"]]["properties"], path


def test_the_pin_agrees_with_the_context_pin_of_dbt() -> None:
    """Both pins come from the same discovery revision, and the Context messages build_catalog.py fills are equal."""
    ours, dbt = load_pin(PIN), json.loads(DBT_PIN.read_text())
    assert ours["revision"] == dbt["revision"]
    for name, schema in dbt["schemas"].items():
        assert ours["schemas"][name] == schema, name
