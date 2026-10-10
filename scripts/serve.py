import json
import pathlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
from dor.copilot.ask import ask

load_dotenv()
RES = json.loads(pathlib.Path("data/raw/access_results.json").read_text(encoding="utf-8"))
OUT = pathlib.Path("outputs")


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/dashboard.html"):
            self._send(200, (OUT / "dashboard.html").read_bytes(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path != "/ask":
            self._send(404, b"not found", "text/plain")
            return
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        out = ask(RES, str(body.get("q", ""))[:300], "ne" if body.get("lang") == "ne" else "en")
        self._send(200, json.dumps(out, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def log_message(self, *a):
        pass


print("serving on http://127.0.0.1:8000")
HTTPServer(("127.0.0.1", 8000), H).serve_forever()
