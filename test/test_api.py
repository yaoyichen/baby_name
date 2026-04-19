#!/usr/bin/env python3
"""
快速测试 LLM API 连通性
用法：python3 test/test_api.py
"""

import urllib.request
import urllib.error
import json
import time

BASE_URL = "http://openai.infly.tech/v1"
API_KEY  = "sk-61YW9qxz5fD6DmHA1JhvY9OgJR98bEaF0GWLS3XocwILylsu"
MODEL    = "claude-sonnet-4-5-20250929"   # sonnet 4.5 正确模型 ID

PROMPT = "用一句话（不超过20字）介绍你自己。"

def test_non_stream():
    print(f"\n{'='*50}")
    print(f"[非流式] 模型: {MODEL}")
    print(f"[非流式] Endpoint: {BASE_URL}/chat/completions")
    payload = {
        "model": MODEL,
        "stream": False,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 200,
    }
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "apikey": API_KEY},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            elapsed = time.time() - t0
            body = json.loads(resp.read())
            content = body["choices"][0]["message"]["content"]
            print(f"✅ 成功  耗时: {elapsed:.2f}s")
            print(f"   回复: {content}")
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.read().decode()[:300]}")
    except Exception as e:
        print(f"❌ 异常: {e}")


def test_stream():
    print(f"\n{'='*50}")
    print(f"[流式]   模型: {MODEL}")
    payload = {
        "model": MODEL,
        "stream": True,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 200,
    }
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "apikey": API_KEY},
        method="POST",
    )
    t0 = time.time()
    chunks = 0
    full = ""
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print("   接收流: ", end="", flush=True)
            for raw in resp:
                line = raw.decode().strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                    token = obj["choices"][0]["delta"].get("content", "")
                    if token:
                        full += token
                        chunks += 1
                        print(token, end="", flush=True)
                except Exception:
                    pass
        elapsed = time.time() - t0
        print(f"\n✅ 成功  共 {chunks} 个 chunk，耗时: {elapsed:.2f}s")
        print(f"   完整回复: {full}")
    except urllib.error.HTTPError as e:
        print(f"\n❌ HTTP {e.code}: {e.read().decode()[:300]}")
    except Exception as e:
        print(f"\n❌ 异常: {e}")


if __name__ == "__main__":
    print(f"测试 API: {BASE_URL}")
    print(f"模型: {MODEL}")
    test_non_stream()
    test_stream()
    print(f"\n{'='*50}")
    print("测试完成")
