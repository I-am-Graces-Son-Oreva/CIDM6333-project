import importlib.util
import json
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DEFAULT_THRESHOLD = 0.30
_RECALL = None


def _load_recall():
    global _RECALL
    if _RECALL is None:
        path = (
            Path(__file__).resolve().parents[2]
            / "evolution-07"
            / "lab"
            / "recall.py"
        )
        spec = importlib.util.spec_from_file_location(
            "e7_recall_service",
            path,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _RECALL = module
    return _RECALL


class _Handler(BaseHTTPRequestHandler):
    server_version = "E7MemoryService/1.0"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/recall":
            self.send_error(404)
            return

        question = parse_qs(parsed.query).get("question", [""])[0]
        try:
            data = _load_recall().query(
                question,
                top_k=self.server.top_k,
                threshold=self.server.threshold,
                today=self.server.today,
                store_path=self.server.store_path,
                ledger_path=self.server.ledger_path,
            )
        except Exception as exc:
            self.send_error(500, str(exc))
            return

        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class MemoryService(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, address, private_dir, threshold=DEFAULT_THRESHOLD,
                 today=None, top_k=3):
        super().__init__(address, _Handler)
        self.private_dir = Path(private_dir)
        self.store_path = self.private_dir / "fixture-memory.jsonl"
        self.ledger_path = (
            self.private_dir / "fixture-memory-ledger.jsonl"
        )
        self.threshold = threshold
        self.today = today or date.today().isoformat()
        self.top_k = top_k


def start_service(private_dir, port=0, threshold=DEFAULT_THRESHOLD,
                  today=None, top_k=3):
    return MemoryService(
        ("127.0.0.1", port),
        private_dir,
        threshold=threshold,
        today=today,
        top_k=top_k,
    )
