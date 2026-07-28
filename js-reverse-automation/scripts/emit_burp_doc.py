#!/usr/bin/env python3
"""Generate Burp autoDecoder integration documentation from analysis_result.json.

Usage:
  python3 scripts/emit_burp_doc.py --analysis analysis_result.json --output generated/burp-autodecoder.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import load_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Burp autoDecoder integration guide.")
    parser.add_argument("--analysis", required=True, help="Path to analysis_result.json.")
    parser.add_argument("--output", required=True, help="Output markdown file path.")
    args = parser.parse_args()

    analysis = load_json(args.analysis)
    flask = analysis.get("flask", {})
    flask_server = analysis.get("flask_server", {})
    jsrpc = analysis.get("jsrpc", {})
    port = flask.get("port", flask_server.get("port", 5000))
    transforms = analysis.get("transforms") or []
    parameters = list(analysis.get("parameters", {}).keys())
    proxy_url = f"http://127.0.0.1:{port}{flask.get('route', '/autodecoder')}"
    jsrpc_port = analysis.get("jsrpc_server", {}).get("port", 12080)
    group = jsrpc.get("group", "jsra")
    action = jsrpc.get("action_name", "encode_password")
    sample_data_body = "&".join(f"{p}=<plaintext>" for p in parameters)

    # Build transform table if transforms exist
    if transforms:
        rows = "\n".join(
            f"| {t.get('id')} | {t.get('direction')} | {t.get('location')} | "
            f"{t.get('content_type', 'auto')} | `{t.get('path', '')}` | `{t.get('action')}` |"
            for t in transforms
        )
        transform_table = f"""
## 转换项

| ID | 方向 | 位置 | 内容类型 | 路径 | JSRPC Action |
|---|---|---|---|---|---|
{rows}
"""
    else:
        transform_table = ""

    content = f'''# Burp autoDecoder 配置（JSRA）

> 重要：此代理不实现加密/解密算法。它只通过 JSRPC 远程调用当前浏览器页面已验证的真实函数。若真实入口、运行时证据或 JSRPC 不可用，代理会返回 `JSRA_ERROR`，不得继续发送请求。

## 本地服务

- Health：`http://127.0.0.1:{port}/health`
- Healthz：`http://127.0.0.1:{port}/healthz`
- 转换接口：`http://127.0.0.1:{port}/autodecoder?direction=request`
- 响应接口：`http://127.0.0.1:{port}/autodecoder?direction=response`
{transform_table}
## 配置原则

1. 仅匹配授权目标 URL。
2. 请求方向使用 `direction=request`，响应解密使用 `direction=response`。
3. 将原始 body 作为 HTTP POST body 发送。
4. JSON 请求应传递原始 Content-Type；可使用 `X-JSRA-Content-Type` 覆盖。
5. 首次联调前访问 `/health`。
6. 发生 `JSRA_ERROR` 时不要继续发送被破坏的请求。
7. 不要把页面抓到的公钥、模数或某次样本结果改写成 Python 加密实现。

## Burp autoDecoder 配置

### 方式一：dataBody/dataHeaders（推荐）

Burp autoDecoder 插件使用 `dataBody` 和 `dataHeaders` 表单字段：

```
POST {proxy_url} HTTP/1.1
Content-Type: application/x-www-form-urlencoded

dataBody=<原始请求体>&dataHeaders=<原始请求头>
```

- `dataBody`：原始请求体（JSON 或 form-urlencoded）
- `dataHeaders`：原始请求头（可选，用于传递 Cookie、Authorization 等）

### 方式二：直接 POST

```
POST {proxy_url}?direction=request HTTP/1.1
Content-Type: <原始 Content-Type>

<原始请求体>
```

## 验证步骤

1. 在目标页面加载 `JsEnv_Dev.js` 和生成的 `jsrpc_inject.js`。
2. 确认浏览器 Console 出现 JSRPC connected，以及已注册的 action。
3. 用一个受控样本调用 JSRPC：
   ```bash
   curl 'http://127.0.0.1:{jsrpc_port}/go?group={group}&action={action}&param=test123'
   ```
4. 验证 Flask 代理：
   ```bash
   curl -X POST {proxy_url} \\
     -H "Content-Type: application/x-www-form-urlencoded" \\
     --data-urlencode "dataBody={sample_data_body}"
   ```
5. 确认返回值与 JSRPC 调用结果一致。

## 故障排查

- `JSRA_ERROR: ...:EvidenceMissing:...`：没有真实运行时证据或候选入口不可用；重新注入探针、导出证据并运行差分验证。
- `JSRA_ERROR: ...:RuntimeError:...`：页面真实函数执行失败；检查页面状态、依赖、DOM 和存储前置条件。
- `JSRA_ERROR` / HTTP 502：JSRPC 连接、响应格式或页面入口失败；不要发送该请求，先恢复浏览器和 JSRPC。
'''

    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
