# 架构

## 设计
- chrome-devtools-mcp：页面交互、网络、Console
- 本地 JSRA Engine：逆向分析
- 可选 Burp MCP：流量重放

## 证据模型
```json
{
  "event_id": "evt-1",
  "trace_id": "trace-1",
  "parent_event_id": null,
  "type": "crypto.encrypt",
  "function": "JSEncrypt.encrypt",
  "input_fingerprint": "sha256:...",
  "output_fingerprint": "sha256:...",
  "stack": [],
  "timestamp": 0
}
```

## 置信度
- `high`：真实运行时 + 差分验证
- `medium`：多源证据一致
- `low`：启发式匹配
