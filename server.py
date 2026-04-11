#!/usr/bin/env python3
"""
本地开发服务器：静态文件 + /api/blacklist 读写接口
用法：python3 server.py
然后访问 http://localhost:8080/analysis/
"""
import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
BLACKLIST_FILE = ROOT / "data" / "blacklist.json"
PORT = 8080


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if urlparse(self.path).path == "/api/blacklist":
            self._send_json(self._read_blacklist())
        else:
            super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path == "/api/blacklist":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                if not isinstance(data, list):
                    raise ValueError("expected list")
                BLACKLIST_FILE.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self._send_json({"ok": True, "count": len(data)})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=400)
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _read_blacklist(self):
        if not BLACKLIST_FILE.exists():
            return []
        try:
            return json.loads(BLACKLIST_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            print(f"[API] {fmt % args}")


if __name__ == "__main__":
    os.chdir(ROOT)
    print(f"服务启动：http://localhost:{PORT}/analysis/")
    print(f"黑名单文件：{BLACKLIST_FILE}")
    print("按 Ctrl+C 停止\n")
    HTTPServer(("", PORT), Handler).serve_forever()
