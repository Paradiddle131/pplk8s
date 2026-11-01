"""Record the call-label prompt's answers from an OpenRouter free model (semantic/PLAN.md SL-18).

The lab cannot call BigQuery's AI.GENERATE (the emulator lacks it; the $0.00 project may not call
Vertex), so dbt's `label_calls` macro reads recordings on Postgres and the emulator instead: this
script sends the prompt in dbt_project.yml's `call_label_prompt` with each transcript to a free model
and writes its answer to seeds/silver/call_label_recordings.csv, keyed by the transcript's MD5 hash
and the prompt version, as dbt's `dbt.hash` computes it.

Opt-in only (`make record-call-labels`); `make check` and the dbt checks never call a model. It refuses a
model id without `:free`, records only transcripts the current version has no successful recording
for, and on a spent quota (HTTP 402 or 429) stops and keeps what it has, exiting 3.

Usage: python scripts/record_call_labels.py [--model ID] [--transcripts CSV ...]
  (from dbt/; the transcripts default to the golden set, which holds the dev fixture's calls)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import yaml

DBT_DIR = Path(__file__).resolve().parent.parent
RECORDINGS = DBT_DIR / "seeds" / "silver" / "call_label_recordings.csv"
GOLDEN_SET = DBT_DIR / "seeds" / "silver" / "call_label_golden_set.csv"
FIELDS = (
    "transcript_hash",
    "prompt_version",
    "endpoint",
    "model_version",
    "topic",
    "objection",
    "sentiment",
    "next_step",
    "status",
    "recorded_at",
)
SIGNALS = ("topic", "objection", "sentiment", "next_step")
DEFAULT_MODEL = "nvidia/nemotron-3.5-super-vl:free"
# OpenRouter's free models allow 20 requests a minute.
PAUSE_SECONDS = 3.5
EXIT_QUOTA = 3


class QuotaSpent(Exception):
    pass


def transcript_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def load_prompt() -> dict:
    project = yaml.safe_load((DBT_DIR / "dbt_project.yml").read_text())
    return project["vars"]["call_label_prompt"]


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_labels(content: str) -> dict[str, str] | None:
    """The four labels from the model's answer, or None when it holds no JSON object with them."""
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None
    try:
        answer = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(answer, dict) or not all(isinstance(answer.get(s), str) for s in SIGNALS):
        return None
    return {s: answer[s].strip().lower() for s in SIGNALS}


def ask(base: str, model: str, prompt: str) -> tuple[str, str]:
    """(the model's answer, the model that answered)."""
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            # The cloud proxy replaces the key; on a laptop it is the real one.
            "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', 'proxy-injected')}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code in (402, 429):
            raise QuotaSpent(f"HTTP {error.code}: {error.read()[:300]!r}") from error
        raise
    if "error" in payload:
        code = payload["error"].get("code")
        if code in (402, 429):
            raise QuotaSpent(str(payload["error"])[:300])
        return "", f"error: {str(payload['error'])[:200]}"
    content = payload["choices"][0]["message"].get("content") or ""
    return content, str(payload.get("model") or model)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", default=os.environ.get("CALL_LABEL_MODEL", DEFAULT_MODEL))
    parser.add_argument("--transcripts", type=Path, nargs="*", default=[GOLDEN_SET])
    args = parser.parse_args()
    if not args.model.endswith(":free"):
        print(f"record_call_labels: {args.model!r} is not a free model (an id ending ':free')", file=sys.stderr)
        return 2
    base = os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1").rstrip("/")
    prompt = load_prompt()
    version = str(prompt["version"])

    recordings = {(r["transcript_hash"], r["prompt_version"]): r for r in read_rows(RECORDINGS)}
    texts = {transcript_hash(r["transcript"]): r["transcript"] for path in args.transcripts for r in read_rows(path)}
    pending = [h for h in sorted(texts) if recordings.get((h, version), {}).get("status", "x") != ""]
    print(f"record_call_labels: prompt {version}, {len(texts)} transcripts, {len(pending)} to record with {args.model}")

    code = 0
    for count, digest in enumerate(pending, start=1):
        try:
            content, answered_by = ask(base, args.model, f"{prompt['text']}\n{texts[digest]}")
        except QuotaSpent as spent:
            print(f"record_call_labels: quota spent after {count - 1} calls, keeping them ({spent})", file=sys.stderr)
            code = EXIT_QUOTA
            break
        labels = parse_labels(content)
        status = "" if labels else ("unparseable response" if not answered_by.startswith("error") else answered_by)
        recordings[(digest, version)] = {
            "transcript_hash": digest,
            "prompt_version": version,
            "endpoint": args.model,
            "model_version": "" if answered_by.startswith("error") else answered_by,
            **(labels or dict.fromkeys(SIGNALS, "")),
            "status": status,
            "recorded_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S+00:00"),
        }
        print(f"  {count}/{len(pending)} {digest[:8]} {labels or status}")
        if count < len(pending):
            time.sleep(PAUSE_SECONDS)

    with RECORDINGS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(recordings[key] for key in sorted(recordings, key=lambda k: (k[1], k[0])))
    failed = sum(r["status"] != "" for r in recordings.values() if r["prompt_version"] == version)
    print(f"record_call_labels: {RECORDINGS.relative_to(DBT_DIR)} holds {len(recordings)} recordings, {failed} failed")
    return code


if __name__ == "__main__":
    sys.exit(main())
