# 输出契约

## 最终交付格式

最终回复不得退化为“只返回候选 JSON”或“只报告入口已识别”。必须保留以下顺序：

1. `验证通过！现在输出最终结果。`
2. `JS 逆向分析完成` 与任务名称
3. `分析结果`：加密函数、加密方式、入口路径、置信度
4. `验证结果` 表：至少包含 `JSRPC`、`Flask 代理`、输入和输出
5. `验证命令`：可复制的 JSRPC curl、Flask curl，以及预期返回
6. `关闭服务命令`
7. `Burp autoDecoder 配置`
8. `生成的产物`

`对抗分析`、`runtime_health`、`adversarial_diff` 和能力边界只能作为追加章节，不能删除或改写上述交付项。

JSRPC 验证输出必须能证明完整链路：`plaintext`、最终目标 `route`、非空 `requestBody`（密文/签名）、HTTP 状态和最终业务 `response`。捕获层同时覆盖 `fetch` 与 `XMLHttpRequest`；对存在前置取钥匙/取签名请求的函数，必须按规范化 URL 路径选择最终请求。

## 运行时产物
| 产物 | 生成脚本 | 说明 |
|---|---|---|
| `artifacts/probe_dump.json` | `emit_runtime_hook_probe.py` | 运行时事件 |
| `artifacts/module_dump.json` | `emit_module_probe.py` | Webpack 模块 |
| `artifacts/evidence_graph.json` | `build_evidence_graph.py` | 事件关联图 |
| `artifacts/encryption_candidates.json` | `detect_encryption.py` | 候选发现 |
| `artifacts/encryption_candidates.verified.json` | `differential_verifier.py` | 差分验证 |
| `artifacts/static_candidates.json` | `ast_candidate_analyzer.js` | AST 分析 |
| `artifacts/source_analysis.json` | 人工分析 | 源码分析 |
| `artifacts/quarantine.json` | `quarantine.py` | 隔离报告 |
| `artifacts/validation_report.json` | `validate_artifacts.py` | 验证报告 |
| `artifacts/delivery_contract.json` | `check_delivery_contract.py` | JSRPC 地址、Burp 整包和 wrapper 回归报告 |
| `artifacts/browser_evidence.json` | `validate_browser_evidence.py` | action 级真实浏览器/JSRPC 结果验收 |
| `artifacts/adversarial_trace.json` | `adversarial_runtime_probe.js` | 对抗运行时事件、Patch、Realm 和健康状态 |
| `artifacts/adversarial_diff.json` | `adversarial_diff.py` | 基线与干预差分 |
| `artifacts/source_instrumentation_report.json` | `source_instrumentor.js` | 源码级保守插桩报告 |

## 生成产物
| 产物 | 生成脚本 | 说明 |
|---|---|---|
| `generated/jsrpc_inject.js` | `emit_jsrpc_stub.py` | JSRPC 注入 |
| `generated/flask_proxy.py` | `emit_flask_proxy.py` | Flask 代理 |
| `generated/burp-autodecoder.md` | `emit_burp_doc.py` | Burp 文档 |
| `generated/adversarial_runtime_probe.js` | `emit_adversarial_runtime_probe.py` | 对抗运行时探针 |

## analysis_result.json 契约

Schema 层只强制授权和目标信息：

- `authorization.confirmed=true`
- `target.url_pattern`
- `transforms` 或 `parameters` 至少存在一个

最终交付结果还必须尽可能提供以下运行信息；缺失时必须明确标记为
`unsupported`、`manual_observed_only` 或未完成，不能伪造成功：

- `skill`、`input`、`trace`、`parameters`
- `jsrpc`、`flask`、`burp`、`diagnostics`
- `entrypoint_discovery`、`module_runtime`、`invocation`
- `capability_boundary`、`runtime_trace`、`runtime_health`

分析结果不再携带交付版本号；协议兼容性由当前 Schema 和生成器共同定义。

## 候选不变量
- `verified=true` 必须有 verification 证据
- `confidence=high` 必须 `verified=true`
- 所有候选必须标记来源
- 失败验证保留为负证据

## strategy 值
`global_path`、`runtime_hook`、`webpack_export`、`async_crypto`、`initscript_hook`、`static_ast`、`source_analysis`、`adversarial_runtime`、`source_tap`、`manual_observed_only`、`unsupported`
