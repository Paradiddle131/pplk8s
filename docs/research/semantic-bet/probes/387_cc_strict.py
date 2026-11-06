"""The strict headless runner for the Claude Code setups (#387): one `claude -p` process a case-run, a fresh session,
no built-in tool, only its setup's MCP tools, and a deterministic audit of every transcript (RULE.md, 2026-11-06).

Setups (semantic_agent.bet_tools.DECLARED; RULE.md § Changes since freezing, 2026-11-06T18:40Z):
  cc-metricflow   mirrors custom-metricflow: semantic_agent.mcp_server (127.0.0.1:8765), toolset_metricflow.INSTRUCTION
  cc-native-mcp   mirrors native-mcp: probes/387_mcp_guard.py (127.0.0.1:8766), 328_mcp_agent.INSTRUCTION

Each run: `claude -p --model M --tools "" --strict-mcp-config --mcp-config <setup> --allowedTools <its tools>
--permission-mode dontAsk --setting-sources "" --system-prompt-file <the arm's instruction> --no-session-persistence
--input-format stream-json --output-format stream-json --verbose`, the case's turns written to its stdin one at a
time, each after the previous turn's `result`. The run aborts before its first question when the `init` event's
tool list is not exactly the setup's. Its whole stream is kept (gzipped) beside the answers, and its answer line
carries every real tool call with its result head and the audit:
  1. tools: every `tool_use` is one of the setup's MCP tools (no built-in, no other server); a failure is a test
     fault, and the scorer never logs such a run (bet_live refuses it, bet_tools.outside);
  2. uncited: each number of the answer that no tool result of the run holds (rounding to the answer's decimals,
     a rate as a percentage), dates, years and the question's own numbers left out; reported, scored as given;
  3. fabricated: a tool call written as text (`query_metrics(`, `<invoke`, `"tool_use"`) in the model's text with
     no real call in that turn; reported, and never a figure source, since only real tool results count in 2.

Run from services/semantic-agent (servers up, NO_PROXY covering 127.0.0.1):
  uv run python ../../docs/research/semantic-bet/probes/387_cc_strict.py run SETUP MODEL SET [--runs 3] [--jobs 6]
      [--limit N] [case ...]
      asks every (run, case) that neither the answers file nor the setup's log holds for the label
      `claude-code-strict (MODEL)`; answers go to cc-strict/answers/<setup>-<model>-<set>.jsonl, streams to
      cc-strict/streams/<setup>/<model>/<set>/<case>-r<run>.jsonl.gz. A usage limit or two failed processes in a row
      stop the pass.
  uv run python ../../docs/research/semantic-bet/probes/387_cc_strict.py smoke SETUP MODEL CASE
      one case, unlogged, its answer and audit printed, nothing written beside the answers.
Scoring (the recorded-answer agent module, as 374_cc_agent.py):
  BET_CC_MODEL=<model> uv run python ../../docs/research/semantic-bet/probes/328_mcp_live.py --agent 387_cc_strict.py \
    --arm cc-metricflow|cc-native-mcp --set SET --runs 3 --no-canary
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import os
import re
import sys
import tempfile
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
ROOT = RESEARCH.parents[2]
OUT = RESEARCH / "cc-strict"
MODELS = ("haiku", "sonnet", "opus")
MODEL = f"claude-code-strict ({os.environ.get('BET_CC_MODEL', 'unknown')})"
SETS = {
    "frozen": ("semantic_bet.yaml", "eval-"),
    "hard": ("semantic_bet_hard.yaml", "eval-hard-"),
    "hard-v2": ("semantic_bet_hard_v2.yaml", "eval-hard-v2-"),
}
RESULT_HEAD = 400
TURN_TIMEOUT_S = 420
LIMIT_WORDS = ("usage limit", "rate limit", "limit reached", "quota")


def _declared(setup: str) -> frozenset[str]:
    sys.path.insert(0, str(ROOT / "services/semantic-agent/src"))
    from semantic_agent.bet_tools import declared

    return declared(setup)


def instruction(setup: str) -> str:
    """The arm's own ADK instruction, the system prompt its Claude Code variant runs under."""
    if setup == "cc-metricflow":
        sys.path.insert(0, str(ROOT / "services/semantic-agent/src"))
        from semantic_agent.toolset_metricflow import INSTRUCTION

        return INSTRUCTION
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "bet_mcp_agent", HERE / "328_mcp_agent.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.INSTRUCTION


SERVERS = {
    "cc-metricflow": ("semantic", "http://127.0.0.1:8765/mcp"),
    "cc-native-mcp": ("google", "http://127.0.0.1:8766/mcp"),
}


def tool_names(setup: str) -> list[str]:
    server = SERVERS[setup][0]
    return sorted(f"mcp__{server}__{t}" for t in _declared(setup))


async def served(setup: str, model: str) -> list[str]:
    """The tools the setup's server lists, as Claude Code names them; refused unless every one is declared.
    Google's servers listed 14 of native-mcp's 16 names on 2026-11-04 and 2026-11-06 (compile_query and
    execute_query absent), as they did to the ADK arm, so the init check holds a run to what is served."""
    from mcp import Client

    server, url = SERVERS[setup]
    os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
    if setup == "cc-metricflow":
        import httpx2
        from mcp.client.streamable_http import streamable_http_client

        http = httpx2.AsyncClient(headers={"Authorization": f"Bearer {token(model)}"})
        target: Any = streamable_http_client(url, http_client=http)
    else:
        target = url
    async with Client(target) as client:
        names = sorted(
            f"mcp__{server}__{t.name}" for t in (await client.list_tools()).tools
        )
    extra = set(names) - set(tool_names(setup))
    if extra or not names:
        raise SystemExit(
            f"387: {setup}'s server lists {sorted(extra) or 'nothing'} outside its declared tools"
        )
    return names


def mcp_config(setup: str, model: str) -> dict[str, Any]:
    server, url = SERVERS[setup]
    entry: dict[str, Any] = {"type": "http", "url": url}
    if setup == "cc-metricflow":
        entry["headers"] = {"Authorization": f"Bearer {token(model)}"}
    return {"mcpServers": {server: entry}}


def token(model: str) -> str:
    """The semantic MCP server's bearer token for this label (SEMANTIC_MCP_CLIENTS: `claude-code-strict-<model>`)."""
    return f"bet-strict-{model}"


def clients() -> str:
    """SEMANTIC_MCP_CLIENTS for the semantic server: each model's label and token, so its audit rows name it."""
    return ",".join(f"claude-code-strict-{m}={token(m)}" for m in MODELS)


def questions(name: str) -> list[dict[str, Any]]:
    import yaml

    data = yaml.safe_load(
        (ROOT / "services/semantic-agent/evals" / SETS[name][0]).read_text()
    )
    out = []
    for q in data["questions"]:
        turns = q.get("turns") or [q]
        out.append({"id": q["id"], "turns": [t["question"] for t in turns]})
    return out


def retired() -> set[str]:
    cases: set[str] = set()
    path = RESEARCH / "redacted.jsonl"
    for line in path.read_text().splitlines() if path.exists() else []:
        row = json.loads(line)
        if row.get("kind") == "case":
            (cases.discard if row.get("undo") else cases.add)(row["case"])
    return cases


def answers_path(setup: str, model: str, name: str) -> Path:
    return OUT / "answers" / f"{setup}-{model}-{name}.jsonl"


def stream_path(setup: str, model: str, name: str, case: str, run: int) -> Path:
    return OUT / "streams" / setup / model / name / f"{case}-r{run}.jsonl.gz"


# --- the audit ------------------------------------------------------------------------------------------------

NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")
MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
DATEISH = re.compile(
    rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTHS}|{MONTHS}\s+\d{{1,2}}\b|\b\d{{1,2}}:\d{{2}}\b",
    re.IGNORECASE,
)
FAKE_CALL = re.compile(
    r"\b(?:list_metrics|describe_metric|query_metrics|execute_sql\w*|search_entries|"
    r"lookup_context|get_table_info)\s*\(|<invoke|\"tool_use\"|<function_calls>"
)


def numbers(text: str) -> list[tuple[float, int]]:
    """The numbers a text states with their decimals, dates, clock times and years left out."""
    text = DATEISH.sub(" ", text)
    out = []
    for raw in NUMBER.findall(text):
        clean = raw.replace(",", "")
        try:
            value = float(clean)
        except ValueError:
            continue
        if clean.isdigit() and 1990 <= value <= 2100:
            continue
        decimals = len(clean.split(".")[1]) if "." in clean else 0
        out.append((value, decimals))
    return out


def cited(value: float, decimals: int, pool: Sequence[float]) -> bool:
    step = 0.5 * 10 ** (-decimals) + 1e-9
    return any(abs(value - p) <= step or abs(value - 100 * p) <= step for p in pool)


def audit(
    setup: str,
    turns: Sequence[dict[str, Any]],
    init_tools: Sequence[str],
    expected: Sequence[str],
) -> dict[str, Any]:
    allowed = set(tool_names(setup))
    calls = [c for t in turns for c in t["calls"]]
    outside = sorted({c["tool"] for c in calls if c["tool"] not in allowed})
    uncited: list[list[Any]] = []
    fabricated: list[int] = []
    for i, turn in enumerate(turns):
        pool = [
            v
            for t in turns[: i + 1]
            for c in t["calls"]
            for v, _ in numbers(c.get("full", ""))
        ]
        question = {v for v, _ in numbers(turn["question"])}
        for value, decimals in numbers(turn["answer"]):
            if value in question or (decimals == 0 and abs(value) <= 1):
                continue
            if not cited(value, decimals, pool):
                uncited.append([i, value])
        if FAKE_CALL.search(turn.get("text_all", "")) and not turn["calls"]:
            fabricated.append(i)
    return {
        "init_tools_ok": sorted(init_tools) == sorted(expected),
        "tools_ok": not outside and sorted(init_tools) == sorted(expected),
        "outside": outside,
        "uncited": uncited,
        "fabricated_turns": fabricated,
    }


# --- one run --------------------------------------------------------------------------------------------------


class Stop(Exception):
    """A pass-ending failure: the usage limit, or the process not answering."""


async def run_case(
    setup: str,
    model: str,
    turns_in: Sequence[str],
    keep: Path | None,
    expected: Sequence[str],
) -> dict[str, Any]:
    """One case-run in one fresh headless session: every turn's answer, real calls and the audit."""
    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp, "mcp.json")
        config.write_text(json.dumps(mcp_config(setup, model)))
        prompt = Path(tmp, "system.md")
        prompt.write_text(instruction(setup))
        env = {
            **os.environ,
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
        }
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", "--model", model, "--tools", "",
            "--strict-mcp-config", "--mcp-config", str(config),
            "--allowedTools", ",".join(expected), "--permission-mode", "dontAsk",
            "--setting-sources", "", "--system-prompt-file", str(prompt),
            "--no-session-persistence", "--input-format", "stream-json",
            "--output-format", "stream-json", "--verbose",
            cwd=tmp, env=env, limit=2**26,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )  # fmt: skip
        assert proc.stdin and proc.stdout
        events: list[dict[str, Any]] = []
        turns: list[dict[str, Any]] = []
        init_tools: list[str] | None = None
        pending: dict[str, dict[str, Any]] = {}

        async def next_event() -> dict[str, Any] | None:
            line = await asyncio.wait_for(proc.stdout.readline(), TURN_TIMEOUT_S)
            if not line:
                return None
            event = json.loads(line)
            events.append(event)
            return event

        try:
            for question in turns_in:
                message = {
                    "type": "user",
                    "message": {"role": "user", "content": question},
                }
                proc.stdin.write((json.dumps(message) + "\n").encode())
                await proc.stdin.drain()
                turn: dict[str, Any] = {
                    "question": question,
                    "calls": [],
                    "answer": "",
                    "text_all": "",
                }
                while True:
                    event = await next_event()
                    if event is None:
                        raise Stop(
                            f"the process ended mid-turn: {(await proc.stderr.read())[-300:]!r}"
                        )
                    kind = event.get("type")
                    if kind == "system" and event.get("subtype") == "init":
                        init_tools = list(event.get("tools") or [])
                        if sorted(init_tools) != sorted(expected):
                            proc.kill()
                            return {
                                "aborted": f"init tools {init_tools} are not {sorted(expected)}"
                            }
                    elif kind == "assistant":
                        for block in event["message"].get("content") or []:
                            if block.get("type") == "tool_use":
                                call = {
                                    "tool": block["name"],
                                    "args": block.get("input") or {},
                                }
                                pending[block["id"]] = call
                                turn["calls"].append(call)
                            elif block.get("type") == "text":
                                turn["text_all"] += block["text"] + "\n"
                    elif kind == "user":
                        for block in event["message"].get("content") or []:
                            if (
                                isinstance(block, dict)
                                and block.get("type") == "tool_result"
                            ):
                                content = block.get("content")
                                text = (
                                    content
                                    if isinstance(content, str)
                                    else json.dumps(content)
                                )
                                if (
                                    call := pending.get(block.get("tool_use_id"))
                                ) is not None:
                                    call["full"] = text
                                    call["result"] = text[:RESULT_HEAD]
                    elif kind == "result":
                        turn["answer"] = (event.get("result") or "").strip()
                        turn["usage"] = event.get("usage")
                        turn["cost_usd"] = event.get("total_cost_usd")
                        turn["is_error"] = event.get("is_error")
                        break
                if (
                    turn["is_error"]
                    or any(w in turn["answer"].lower() for w in LIMIT_WORDS)
                    and not turn["calls"]
                ):
                    raise Stop(f"the turn failed: {turn['answer'][:300]}")
                turns.append(turn)
        finally:
            if proc.returncode is None:
                proc.stdin.close()
                try:
                    await asyncio.wait_for(proc.wait(), 30)
                except TimeoutError:
                    proc.kill()
            if keep is not None:
                keep.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(keep, "wt") as out:
                    for event in events:
                        out.write(json.dumps(event) + "\n")
        checked = audit(setup, turns, init_tools or [], expected)
        for turn in turns:
            for call in turn["calls"]:
                call.pop("full", None)
            turn.pop("text_all", None)
        return {"turns": turns, "audit": checked}


def logged(setup: str, model: str, name: str) -> set[tuple[str, int]]:
    log = RESEARCH / f"{SETS[name][1]}{setup}.jsonl"
    label = f"claude-code-strict ({model})"
    done = set()
    for line in log.read_text().splitlines() if log.exists() else []:
        row = json.loads(line)
        if row["model"] == label and row.get("outcome"):
            done.add((row["case"], int(row["run"])))
    return done


def recorded_runs(path: Path) -> set[tuple[str, int]]:
    rows = (
        [json.loads(line) for line in path.read_text().splitlines()]
        if path.exists()
        else []
    )
    return {(r["case"], int(r["run"])) for r in rows}


async def run_pass(args: argparse.Namespace) -> int:
    path = answers_path(args.setup, args.model, args.set)
    path.parent.mkdir(parents=True, exist_ok=True)
    gone = retired()
    cases = [
        c
        for c in questions(args.set)
        if c["id"] not in gone and (not args.cases or c["id"] in args.cases)
    ]
    expected = await served(args.setup, args.model)
    have = recorded_runs(path) | logged(args.setup, args.model, args.set)
    todo = [
        (r, c)
        for r in range(1, args.runs + 1)
        for c in cases
        if (c["id"], r) not in have
    ]
    if args.limit:
        todo = todo[: args.limit]
    print(
        f"387: {args.setup} {args.model} {args.set}: {len(todo)} case-runs to ask, {args.jobs} at once",
        flush=True,
    )
    queue: asyncio.Queue[tuple[int, dict[str, Any]]] = asyncio.Queue()
    for item in todo:
        queue.put_nowait(item)
    state = {"misses": 0, "stop": None, "done": 0}

    async def worker() -> None:
        while not queue.empty() and not state["stop"]:
            run, case = queue.get_nowait()
            keep = stream_path(args.setup, args.model, args.set, case["id"], run)
            try:
                got = await run_case(
                    args.setup, args.model, case["turns"], keep, expected
                )
            except (Stop, TimeoutError, json.JSONDecodeError) as failed:
                state["misses"] += 1
                print(f"  {case['id']} r{run}: failed: {failed}", flush=True)
                if state["misses"] >= 2 or any(
                    w in str(failed).lower() for w in LIMIT_WORDS
                ):
                    state["stop"] = str(failed)
                continue
            if "aborted" in got:
                state["stop"] = got["aborted"]
                print(f"  {case['id']} r{run}: ABORTED: {got['aborted']}", flush=True)
                continue
            state["misses"] = 0
            row = {
                "case": case["id"],
                "run": run,
                "setup": args.setup,
                "model": args.model,
                **got,
            }
            with path.open("a") as out:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
            state["done"] += 1
            a = got["audit"]
            flags = "" if a["tools_ok"] else f" TOOLS {a['outside']}"
            flags += f" uncited {a['uncited']}" if a["uncited"] else ""
            print(
                f"  {case['id']} r{run}: {sum(len(t['calls']) for t in got['turns'])} calls{flags}",
                flush=True,
            )

    await asyncio.gather(*(worker() for _ in range(args.jobs)))
    print(f"387: {state['done']} recorded to {path}; stop: {state['stop']}", flush=True)
    return 0 if not state["stop"] else 3


async def smoke(setup: str, model: str, case_id: str) -> int:
    case = next(c for name in SETS for c in questions(name) if c["id"] == case_id)
    got = await run_case(setup, model, case["turns"], None, await served(setup, model))
    print(json.dumps(got, indent=1, ensure_ascii=False)[:6000])
    return 0


# --- the recorded-answer agent module (328_mcp_live.py --agent 387_cc_strict.py) -------------------------------


def recorded(arm: str) -> dict[str, list[dict[str, Any]]]:
    """Every recorded answer of this setup and model by case, runs in order; a run already logged stays out."""
    model = os.environ["BET_CC_MODEL"]
    by_case: dict[str, list[dict[str, Any]]] = {}
    for path in sorted((OUT / "answers").glob(f"{arm}-{model}-*.jsonl")):
        name = path.stem.removeprefix(f"{arm}-{model}-")
        done = logged(arm, model, name)
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if (row["case"], row["run"]) not in done:
                by_case.setdefault(row["case"], []).append(row)
    for rows in by_case.values():
        rows.sort(key=lambda r: r["run"])
    return by_case


def asker(arm: str) -> Callable[[Sequence[str]], Awaitable[list[dict[str, Any]]]]:
    by_case = recorded(arm)
    by_turns = {tuple(c["turns"]): c["id"] for name in SETS for c in questions(name)}

    async def ask(qs: Sequence[str]) -> list[dict[str, Any]]:
        rows = by_case.get(by_turns.get(tuple(qs), ""), [])
        if not rows:
            failure = {
                "kind": "error",
                "message": "no recorded answer",
                "retry_after_s": None,
            }
            return [
                {
                    "question": qs[0],
                    "answer": "",
                    "calls": [],
                    "model_calls": 0,
                    "failure": failure,
                }
            ]
        row = rows.pop(0)
        turns = row["turns"]
        return [
            {
                "question": q,
                "answer": turns[i]["answer"] if i < len(turns) else "",
                "calls": turns[i]["calls"] if i < len(turns) else [],
                "model_calls": 1,
            }
            for i, q in enumerate(qs)
        ]

    return ask


def redact_faults(dry: bool = False) -> int:
    """Every logged strict run whose transcript failed the tool check (a call outside the setup's
    tools, a built-in tool, or an init list unlike the server's) gets one `run` row in
    redacted.jsonl as a test fault, the same check on every Claude Code setup; prints the census."""
    sys.path.insert(0, str(ROOT / "services/semantic-agent/src"))
    from semantic_agent.bet_eval import OVERLAY, read_overlay, run_key

    _, redacted = read_overlay(RESEARCH)
    failed: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    for path in sorted((OUT / "answers").glob("*.jsonl")):
        setup, model, name = _parts(path.stem)
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if not row["audit"]["tools_ok"]:
                failed[(setup, model, name, row["case"], row["run"])] = row["audit"]
    rows = []
    for setup, model, name, case, run in failed:
        log = RESEARCH / f"{SETS[name][1]}{setup}.jsonl"
        label = f"claude-code-strict ({model})"
        for line in log.read_text().splitlines() if log.exists() else []:
            r = json.loads(line)
            if r["model"] == label and r["case"] == case and r["run"] == run:
                key = run_key({"arm": setup, **r})
                if key not in redacted:
                    rows.append(
                        {
                            "kind": "run",
                            "arm": setup,
                            "model": label,
                            "case": case,
                            "run": run,
                            "at": r["at"],
                            "class": "test_fault",
                            "reason": f"strict audit: tools {failed[(setup, model, name, case, run)]['outside']}",
                            "issue": 387,
                        }
                    )
    print(
        f"387: {len(failed)} recorded runs failed the tool check; {len(rows)} logged and not yet redacted"
    )
    if rows and not dry:
        with (RESEARCH / OVERLAY).open("a") as out:
            for row in rows:
                out.write(json.dumps(row) + "\n")
    return 0


def _parts(stem: str) -> tuple[str, str, str]:
    """An answers file's setup, model and set from `<setup>-<model>-<set>`."""
    for setup in SERVERS:
        if stem.startswith(setup + "-"):
            model, _, name = stem[len(setup) + 1 :].partition("-")
            return setup, model, name
    raise ValueError(stem)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("setup", choices=sorted(SERVERS))
    r.add_argument("model", choices=MODELS)
    r.add_argument("set", choices=sorted(SETS))
    r.add_argument("--runs", type=int, default=3)
    r.add_argument("--jobs", type=int, default=6)
    r.add_argument("--limit", type=int)
    r.add_argument("cases", nargs="*")
    s = sub.add_parser("smoke")
    s.add_argument("setup", choices=sorted(SERVERS))
    s.add_argument("model", choices=MODELS)
    s.add_argument("case")
    sub.add_parser("clients")
    sub.add_parser("redact")
    args = parser.parse_args()
    if args.cmd == "redact":
        return redact_faults()
    if args.cmd == "clients":
        print(clients())
        return 0
    if args.cmd == "smoke":
        return asyncio.run(smoke(args.setup, args.model, args.case))
    return asyncio.run(run_pass(args))


if __name__ == "__main__":
    sys.exit(main())
