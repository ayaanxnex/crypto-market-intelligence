from http.server import BaseHTTPRequestHandler
import json
from pipeline.load import database_health
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body=json.dumps(database_health()).encode();self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
