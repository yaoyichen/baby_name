#!/usr/bin/env python3
"""
本地开发服务器：静态文件 + API 接口
用法：python3 server.py
然后访问 http://localhost:8080/analysis/

API 端点：
  GET  /api/blacklist           读黑名单
  POST /api/blacklist           写黑名单
  POST /api/ai-names            LLM 流式代理（SSE）
  POST /api/rebuild             重新生成 all_chars.json（无需重启服务）
  GET  /data/all_chars.json     自动检测 full_wuxing_dict.json 是否更新，若有则先重建
"""
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT            = Path(__file__).parent
BLACKLIST_FILE  = ROOT / "data" / "blacklist.json"
WUXING_JSON     = ROOT / "data" / "full_wuxing_dict.json"
ALL_CHARS_JSON  = ROOT / "data" / "all_chars.json"
LOOKUP_JSON     = ROOT / "data" / "lookup_chars.json"
GENERATE_SCRIPT = ROOT / "src" / "generate_all_chars.py"
LOOKUP_SCRIPT   = ROOT / "src" / "generate_lookup.py"
PORT = 8080

LLM_BASE_URL = "http://openai.infly.tech/v1"
LLM_API_KEY  = "sk-61YW9qxz5fD6DmHA1JhvY9OgJR98bEaF0GWLS3XocwILylsu"


def _needs_rebuild() -> bool:
    """判断 all_chars.json 是否需要重建（源文件比输出文件新）"""
    if not ALL_CHARS_JSON.exists():
        return True
    if not WUXING_JSON.exists():
        return False
    return WUXING_JSON.stat().st_mtime > ALL_CHARS_JSON.stat().st_mtime


def _run_script(script: Path, label: str) -> tuple[bool, str]:
    """运行单个生成脚本，返回 (成功, 摘要信息)"""
    if not script.exists():
        return False, f"找不到脚本：{script}"
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT),
        )
        if result.returncode == 0:
            out = result.stdout.strip().splitlines()
            return True, out[-1] if out else f"{label}完成"
        else:
            return False, result.stderr.strip()[:500] or "未知错误"
    except subprocess.TimeoutExpired:
        return False, f"{label}超时（>120s）"
    except Exception as e:
        return False, str(e)


def _do_rebuild() -> tuple[bool, str]:
    """重建 all_chars.json 和 lookup_chars.json，返回 (成功, 信息)"""
    ok1, msg1 = _run_script(GENERATE_SCRIPT, "字库重建")
    if not ok1:
        return False, msg1
    ok2, msg2 = _run_script(LOOKUP_SCRIPT, "查名字库重建")
    if not ok2:
        return True, f"{msg1}（查名字库更新失败：{msg2}）"
    return True, f"{msg1} | {msg2}"


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

        elif p == "/data/all_chars.json":
            # 自动检测 full_wuxing_dict.json 是否比 all_chars.json 新，若是则重建
            if _needs_rebuild():
                print("[rebuild] full_wuxing_dict.json 已更新，自动重建 all_chars.json…")
                ok, msg = _do_rebuild()
                if ok:
                    print(f"[rebuild] ✓ {msg}")
                else:
                    print(f"[rebuild] ✗ 重建失败：{msg}")
            # 继续正常静态文件服务
            super().do_GET()

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

        elif path == "/api/rebuild":
            # 主动触发重建（前端按钮调用）
            ok, msg = _do_rebuild()
            if ok:
                # 返回新生成的 all_chars.json 和 lookup_chars.json，前端可直接热更新
                try:
                    chars  = json.loads(ALL_CHARS_JSON.read_text(encoding="utf-8"))
                    lookup = json.loads(LOOKUP_JSON.read_text(encoding="utf-8")) if LOOKUP_JSON.exists() else []
                    self._send_json({"ok": True, "msg": msg, "count": len(chars), "chars": chars, "lookup": lookup})
                except Exception as e:
                    self._send_json({"ok": True, "msg": msg, "count": 0, "chars": [], "lookup": []})
            else:
                self._send_json({"ok": False, "error": msg}, status=500)

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
        self.close_connection = True

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception as e:
            self._send_json({"ok": False, "error": f"Invalid JSON: {e}"}, status=400)
            return

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
                "apikey": api_key,
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
        if "/api/" in first or "/data/all_chars" in first:
            print(f"[{self.command}] {fmt % args}")


if __name__ == "__main__":
    os.chdir(ROOT)
    # 启动时若源文件比输出新，自动重建一次
    if _needs_rebuild():
        print("检测到 full_wuxing_dict.json 有更新，正在重建字库…")
        ok, msg = _do_rebuild()
        print(f"  {'✓' if ok else '✗'} {msg}")
    print(f"\n服务启动：http://localhost:{PORT}/analysis/")
    print(f"黑名单文件：{BLACKLIST_FILE}")
    print(f"字库源文件：{WUXING_JSON}（修改后浏览器点击「重新生成字库」即可热更新）")
    print("按 Ctrl+C 停止\n")
    HTTPServer(("", PORT), Handler).serve_forever()
