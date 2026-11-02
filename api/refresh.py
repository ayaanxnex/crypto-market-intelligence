
from http.server import BaseHTTPRequestHandler
import json
from api._shared import refresh, serialize_latest


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            result = refresh()
            result["snapshot"] = serialize_latest()
            body = json.dumps(result, default=str).encode()
            code = 200
        except Exception as e:
            body = json.dumps({
                "error": str(e)[:500]
            }).encode()
            code = 502

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
