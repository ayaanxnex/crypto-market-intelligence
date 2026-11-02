from http.server import BaseHTTPRequestHandler
import json
from api._shared import serialize_latest,refresh
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            data=serialize_latest()
            if not data.get("coins"): refresh();data=serialize_latest()
            body=json.dumps(data,default=str).encode();code=200
        except Exception as e:body=json.dumps({"error":str(e)[:250]}).encode();code=502
        self.send_response(code);self.send_header("Content-Type","application/json");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
