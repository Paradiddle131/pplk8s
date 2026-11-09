"""#440: a data-agent turn keeps its reasoning, result heads, job ids and follow-ups, read back
from a stream recorded from Google's data agent (findings/2026-11-06-388-data-agent-streams.jsonl).
"""

import importlib.util
import json
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[3] / "docs/research/semantic-bet"
spec = importlib.util.spec_from_file_location("data_agent", RESEARCH / "probes/354_data_agent.py")
data_agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_agent)


def test_a_recorded_stream_gives_its_results_jobs_and_follow_ups():
    line = (RESEARCH / "findings/2026-11-06-388-data-agent-streams.jsonl").open().readline()
    stream = json.loads(line)["stream"]
    trace = data_agent.trace_of(stream)
    assert trace["jobs"] == ["job_x58csEZ9tdYR4r-lXGLiAow1aA8D"]
    (head,) = trace["results"]
    assert '"total_bookings": 31' in head and len(head) <= data_agent.RESULT_HEAD
    assert trace["followups"][0].startswith("What was the total ad spend")


def test_a_stream_without_data_adds_nothing():
    assert data_agent.trace_of([{"systemMessage": {"text": {"textType": "THOUGHT"}}}]) == {}
