"""Run a development-only OpenCode permission probe with a loopback model fixture."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from runner import OpenCodePersonaRunner


class FixtureModel(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        names = [tool["function"]["name"] for tool in body.get("tools", [])]
        turns = sum(message["role"] == "tool" for message in body["messages"])
        observations.append({"turn": turns, "edit_exposed": "edit" in names})
        if turns == 0 and "edit" in names:
            delta = {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call_e8_probe",
                        "type": "function",
                        "function": {
                            "name": "edit",
                            "arguments": json.dumps(
                                {
                                    "filePath": "score.py",
                                    "oldString": "return True",
                                    "newString": "return score >= 0",
                                }
                            ),
                        },
                    }
                ]
            }
            finish = "tool_calls"
        else:
            delta = {
                "content": '{"status":"FAIL","summary":"Synthetic fixture fails.","findings":["score.py:2 accepts negative scores."]}'
            }
            finish = "stop"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for chunk, reason in ((delta, None), ({}, finish)):
            event = {
                "id": "e8-probe",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "qwen3:4b",
                "choices": [{"index": 0, "delta": chunk, "finish_reason": reason}],
            }
            self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
        self.wfile.write(b"data: [DONE]\n\n")


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("out", type=Path, help="New output directory for development-only evidence")
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=False)
observations = []
repo = Path(__file__).resolve().parents[2]
with (
    tempfile.TemporaryDirectory() as path,
    ThreadingHTTPServer(("127.0.0.1", 0), FixtureModel) as server,
):
    root = Path(path)
    workspace = root / "project"
    workspace.mkdir()
    target = workspace / "score.py"
    original = b"def validate_score(score):\n    return True\n"
    target.write_bytes(original)
    before = hashlib.sha256(original).hexdigest()
    agents = workspace / ".opencode" / "agents"
    agents.mkdir(parents=True)
    for agent in ("e8-reviewer-tp4", "e8-reviewer"):
        shutil.copyfile(repo / f".opencode/agents/{agent}.md", agents / f"{agent}.md")
    Thread(target=server.serve_forever, daemon=True).start()
    model = "ollama/qwen3:4b"
    env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ["HOME"],
        "OPENCODE_DISABLE_MODELS_FETCH": "1",
        "OPENCODE_DISABLE_AUTOUPDATE": "1",
        "npm_config_offline": "true",
        **{
            f"XDG_{key}_HOME": str(root / key.lower())
            for key in ("CONFIG", "DATA", "CACHE", "STATE")
        },
        "OPENCODE_CONFIG_CONTENT": json.dumps(
            {
                "enabled_providers": ["ollama"],
                "model": model,
                "agent": {agent: {"model": model} for agent in ("e8-reviewer-tp4", "e8-reviewer")},
                "provider": {
                    "ollama": {
                        "npm": "@ai-sdk/openai-compatible",
                        "name": "Loopback",
                        "options": {"baseURL": f"http://127.0.0.1:{server.server_port}/v1"},
                        "models": {"qwen3:4b": {"name": "Scripted loopback"}},
                    }
                },
            }
        ),
    }
    stage_a = args.out.resolve() / "stage-a.jsonl"
    stage_b = args.out.resolve() / "stage-b.jsonl"
    version = subprocess.check_output(["opencode", "--version"], text=True).strip()
    with patch.dict(os.environ, env, clear=True):
        verdict = OpenCodePersonaRunner(repo_root=workspace, timeout_seconds=60).review_tp4(
            requirement="Reject negative scores.",
            fixture_path="score.py",
            implementation_evidence=original.decode(),
            stage_a_capture_path=stage_a,
            stage_b_capture_path=stage_b,
        )
    after = hashlib.sha256(target.read_bytes()).hexdigest()
    assert before == after and verdict.status == "FAIL"
    print(
        json.dumps(
            {
                "mode": "development_only_scripted_model_native_enforcement",
                "opencode": version,
                "fixture_sha256_before": before,
                "fixture_sha256_after": after,
                "tool_exposure": observations,
                "review": {"status": verdict.status, "findings": verdict.findings},
            },
            indent=2,
        )
    )
