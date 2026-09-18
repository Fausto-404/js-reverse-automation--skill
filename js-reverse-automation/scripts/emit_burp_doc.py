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
    parser.add_argument("--status", default="", help="Optional Flask status JSON; uses the actual fallback port when present.")
    args = parser.parse_args()

    analysis = load_json(args.analysis)
    flask = analysis.get("flask", {})
    flask_server = analysis.get("flask_server", {})
    jsrpc = analysis.get("jsrpc", {})
    port = flask.get("port", flask_server.get("port", 5000))
    status = load_json(args.status, {}) if args.status else {}
    if status.get("status") == "started" and status.get("port"):
        port = status["port"]
    transforms = analysis.get("transforms") or []
    parameters = list(analysis.get("parameters", {}).keys())
    proxy_url = f"http://127.0.0.1:{port}{flask.get('route', '/autodecoder')}"
    encode_url = status.get("encode_url", f"http://127.0.0.1:{port}/encode")
    decode_url = status.get("decode_url", f"http://127.0.0.1:{port}/decode")
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
- 当前服务端口：`{port}`。如果服务启动时发生端口回退，文档优先使用 `artifacts/flask_status.json` 中的实际地址。
{transform_table}
## 配置原则

1. 仅匹配授权目标 URL。
2. 请求方向使用 `direction=request`，响应解密使用 `direction=response`。
3. 在 autoDecoder 页面直接粘贴完整 HTTP 请求/响应时，插件可能以 `application/octet-stream` 调用接口；代理会从内层报文自动识别真实 `Content-Type`，并返回完整改写后的报文。
4. 使用 `dataBody/dataHeaders` wrapper 时，`dataBody` 传 body，`dataHeaders` 传可选头部；JSON 请求也可用 `X-JSRA-Content-Type` 覆盖。
5. 首次联调前访问 `/health`。
6. 发生 `JSRA_ERROR` 时不要继续发送被破坏的请求。
7. 不要把页面抓到的公钥、模数或某次样本结果改写成 Python 加密实现。

## Burp autoDecoder 配置

### 截图所示的“接口加解密设置”页面

| 页面字段 | 配置值 |
|---|---|
| 解密接口 | `{decode_url}`（可与加密接口同时配置） |
| 加密接口 | `{encode_url}` |
| 请求方向 | 当前测试请求时选择“请求数据包” |
| 响应方向 | 当前测试响应时选择“响应数据包”；与“请求数据包”互斥 |
| 处理请求头 | 默认不选；只有签名依赖请求头时才启用 |
| 请求 base64 编码 | 只有原始请求体本身是 Base64 时才选 |
| 请求自动 base64 解码 | 只有服务端要求先解码 Base64 时才选 |
| Proxy、Repeater 等模块真实调试 | 联调时可选，用于观察返回的完整数据包 |

加密接口和解密接口可以同时配置。请求方向调试时，在“原始数据包”区域粘贴完整 HTTP 请求并选择“请求数据包”；响应方向调试时切换为“响应数据包”，再粘贴完整 HTTP 响应，两个方向不能同时选。对于截图中的整包模式，接口收到的是完整 HTTP 报文，外层常见 `Content-Type: application/octet-stream`；代理会解析内层 `Content-Type`、替换 body，并同步 `Content-Length`。对于 wrapper 模式，autoDecoder 通过 `dataBody` 传请求体，勾选“处理请求头”时额外传 `dataHeaders`，并传 `requestorresponse=request` 或 `response`。未处理请求头时整包模式返回完整改写报文，wrapper 模式返回改写后的 body；处理请求头时必须返回 `headers + "\\r\\n\\r\\n\\r\\n\\r\\n" + body`，这是 autoDecoder 的固定返回格式。

响应解密时使用已配置的 `{decode_url}`，切换为“响应数据包”后进行测试；如果当前只验证请求加密，也可以保留解密接口配置不使用。

### 响应体配置

| 页面字段 | 配置值 |
|---|---|
| 响应数据方向 | 选择“响应数据包” |
| 解密接口 | `{decode_url}` |
| 处理响应头 | 只有响应解密依赖响应头时才启用 |
| 响应 base64 编码 | 只有响应体传入接口前需要 Base64 编码时才选 |
| 响应自动 base64 解码 | 只有接口返回 Base64、需要由 autoDecoder 还原二进制响应时才选 |
| 响应请求标识 | `requestorresponse=response` |

响应方向启用请求头处理时，接口接收 `dataBody`、`dataHeaders` 和 `requestorresponse=response`，并返回 `响应头 + \\r\\n\\r\\n\\r\\n\\r\\n + 解密后的响应体`。未启用响应头处理时只返回解密后的响应体。

响应体验证：

```bash
curl --noproxy '*' -sS -X POST {decode_url} \\
  -H 'Content-Type: application/x-www-form-urlencoded' \\
  --data-urlencode 'dataBody=<原始响应体>' \\
  --data-urlencode 'dataHeaders=<可选的原始响应头>' \\
  --data-urlencode 'requestorresponse=response'
```

预期结果为解密后的响应体；启用响应头处理时，返回值必须包含四组 CRLF 分隔的响应头和响应体。

### 页面配置验证（标准 autoDecoder 协议）

```bash
curl --noproxy '*' -sS -X POST {encode_url} \\
  -H 'Content-Type: application/x-www-form-urlencoded' \\
  --data-urlencode 'dataBody=<原始请求体>' \\
  --data-urlencode 'requestorresponse=request'
```

勾选“处理请求头”时增加：

```bash
  --data-urlencode 'dataHeaders=<原始请求头>'
```

此时预期返回格式为：`原始请求头 + \\r\\n\\r\\n\\r\\n\\r\\n + 改写后的请求体`。

### 完整 HTTP 数据包调试

生成的 `/encode` 和 `/decode` 也支持直接提交完整 HTTP 数据包，便于脱离 Burp 页面调试；该模式会拆分请求头和请求体，并自动更新 `Content-Length`。整包验证示例：

```bash
curl --noproxy '*' -sS -X POST {encode_url} \\
  -H 'Content-Type: application/octet-stream' \\
  --data-binary $'POST /newlogin/login.do?appName=arena&fromSite=77 HTTP/1.1\\r\\nHost: 127.0.0.1:8123\\r\\nContent-Type: application/x-www-form-urlencoded\\r\\n\\r\\nloginId=admin&password2=123456'
```

预期返回完整 HTTP 请求，且只替换目标字段；若返回 `JSRA_ERROR`，先检查 JSRPC action 是否仍注册在当前浏览器页面。

### 兼容方式：dataBody/dataHeaders

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
