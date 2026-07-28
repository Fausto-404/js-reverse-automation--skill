# 输出契约

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

## 生成产物
| 产物 | 生成脚本 | 说明 |
|---|---|---|
| `generated/jsrpc_inject.js` | `emit_jsrpc_stub.py` | JSRPC 注入 |
| `generated/flask_proxy.py` | `emit_flask_proxy.py` | Flask 代理 |
| `generated/burp-autodecoder.md` | `emit_burp_doc.py` | Burp 文档 |

## analysis_result.json 必需字段
- `skill`、`input`、`trace`、`parameters`
- `jsrpc`、`flask`、`burp`、`diagnostics`
- `entrypoint_discovery`、`module_runtime`、`invocation`
- `capability_boundary`、`runtime_trace`、`runtime_health`

## 候选不变量
- `verified=true` 必须有 verification 证据
- `confidence=high` 必须 `verified=true`
- 所有候选必须标记来源
- 失败验证保留为负证据

## strategy 值
`global_path`、`runtime_hook`、`webpack_export`、`async_crypto`、`initscript_hook`、`static_ast`、`source_analysis`、`manual_observed_only`、`unsupported`
