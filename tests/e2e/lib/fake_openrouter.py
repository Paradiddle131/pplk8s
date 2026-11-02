"""A scripted OpenRouter for an agent served in a container (tests/e2e/gcp-image-check.sh): no model quota spent.

It answers OpenAI-style `POST .../chat/completions`, as LiteLLM sends them to OPENROUTER_API_BASE: a request
whose messages hold no tool result gets one tool call (the tool and its JSON arguments from argv), the next the
final answer; each tool result it was shown is appended to `<out>/tool-results.jsonl`, so the check reads what
the served agent's tool returned, its freshness included.

Usage: python fake_openrouter.py <port> <out dir> <tool> <arguments JSON> <answer>
"""

from __future__ import annotations

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT, OUT, TOOL, ARGUMENTS, ANSWER = int(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]


def completion(message: dict, finish: str) -> dict:
    return {
        "id": f"fake-{time.time_ns()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "fake/scripted:free",
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        results = [m for m in request.get("messages", []) if m.get("role") == "tool"]
        if results:
            with (OUT / "tool-results.jsonl").open("a") as f:
                for m in results:
                    f.write(json.dumps({"content": m.get("content")}) + "\n")
            reply = completion({"role": "assistant", "content": ANSWER}, "stop")
        else:
            call = {"id": "call_1", "type": "function", "function": {"name": TOOL, "arguments": ARGUMENTS}}
            reply = completion({"role": "assistant", "content": None, "tool_calls": [call]}, "tool_calls")
        body = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
