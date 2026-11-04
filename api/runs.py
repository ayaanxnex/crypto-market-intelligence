from http.server import BaseHTTPRequestHandler
import json
from pipeline.load import read_runs


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            body = json.dumps({"runs": read_runs(30)}, default=str).encode()
            code = 200
        except Exception as e:
            body = json.dumps({"error": str(e)[:250]}).encode()
            code = 502
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
