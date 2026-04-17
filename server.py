#!/usr/bin/env python3
"""
本地开发服务器：静态文件 + /api/blacklist 读写接口
用法：python3 server.py
然后访问 http://localhost:8080/analysis/
"""
import json
import os
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
BLACKLIST_FILE = ROOT / "data" / "blacklist.json"
PORT = 8080

LLM_BASE_URL = "http://openai.infly.tech/v1"
LLM_API_KEY  = "sk-61YW9qxz5fD6DmHA1JhvY9OgJR98bEaF0GWLS3XocwILylsu"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/api/blacklist":
            self._send_json(self._read_blacklist())
        elif p == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/blacklist":
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
        elif path == "/api/ai-names":
            self._handle_ai_names()
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

    def _handle_ai_names(self):
        """代理 LLM 流式请求，SSE 转发给浏览器"""
        # 确保响应结束后关闭连接
        self.close_connection = True

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception as e:
            self._send_json({"ok": False, "error": f"Invalid JSON: {e}"}, status=400)
            return

        # 优先使用前端传入的 key，为空时回退到服务器内置 key
        api_key = body.get("api_key", "").strip() or LLM_API_KEY
        model   = body.get("model", "deepseek-v3").strip()
        prompt  = body.get("prompt", "").strip()

        if not prompt:
            self._send_json({"ok": False, "error": "Prompt required"}, status=400)
            return

        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "max_tokens": 16000,
            "temperature": 0.8,
        }, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            f"{LLM_BASE_URL}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "apikey": api_key,          # infly 接口使用 apikey 头
            },
            method="POST",
        )

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._cors_headers()
        self.end_headers()

        def _write_err(msg):
            data = json.dumps({"error": msg}, ensure_ascii=False)
            try:
                self.wfile.write(f"data: {data}\n\ndata: [DONE]\n\n".encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for line in resp:
                    self.wfile.write(line)
                    self.wfile.flush()
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            _write_err(f"LLM API 错误 {e.code}: {err_body[:300]}")
        except urllib.error.URLError as e:
            _write_err(f"网络连接失败: {e.reason}")
        except Exception as e:
            _write_err(str(e))

    def log_message(self, fmt, *args):
        first = str(args[0]) if args else ""
        if "/api/" in first:
            print(f"[API] {fmt % args}")


if __name__ == "__main__":
    os.chdir(ROOT)
    print(f"服务启动：http://localhost:{PORT}/analysis/")
    print(f"黑名单文件：{BLACKLIST_FILE}")
    print("按 Ctrl+C 停止\n")
    HTTPServer(("", PORT), Handler).serve_forever()
