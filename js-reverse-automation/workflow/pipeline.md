# 工作流

## 环境准备
```bash
python3 -m pip install -r requirements.txt
python3 scripts/doctor.py --ci
```

## Phase 0: 输入校验
将用户提供的三行输入先整理为一个 JSON 文件（例如 `artifacts/raw_input.json`）：

```json
{
  "target_url": "https://xxx/login",
  "parameters": ["password"],
  "fetch_example": "fetch(\"https://xxx/api/login\", {})"
}
```

再执行：

```bash
python3 scripts/check_inputs.py --input artifacts/raw_input.json --output artifacts/phase0_input.json
```

## Phase 0.5: Fetch Example 预分析（如果有）
当用户提供 Fetch Example 时，**必须先分析**：
- 提取目标请求 URL（如 `loginByPassword`）
- 提取加密后的密码格式（Base64/Hex/长度）
- 识别加密算法（RSA/SM2/AES/MD5）
- 确定参数落点（body/query/header）

```bash
python3 scripts/identify_crypto.py --output-sample "<加密后的密码>"
```

**预分析结果用于指导后续流程，但不能跳过网络捕获。**

## Phase 1: 浏览器连接
- 打开目标页面
- 读取浏览器连接状态并锁定当前 `tabId`、URL 和文档身份；断线、刷新、跨文档导航后重新绑定，不复用旧元素引用或旧调用栈。
- 通过 `navigate_page(initScript=...)` 预注入 Hook
- 记录 URL/Method/Body/Headers/参数落点

## Phase 1.5: 运行时 Hook
```bash
python3 scripts/emit_runtime_hook_probe.py --output generated/runtime_hook_probe.js
```
- 注入探针 → 触发目标动作 → 导出证据
- 健康检测：ok/timeout/crashed/partial
- 降级：timeout/crashed → 静态分析

## Phase 1.6: 对抗运行时探测
```bash
python3 scripts/emit_adversarial_runtime_probe.py \
  --output generated/adversarial_runtime_probe.js \
  --mode observe --properties "navigator.webdriver,navigator.userAgent,document.cookie"
```
- 先以 `observe` 模式记录反调试、反 Hook、环境属性、动态代码、响应解析、Worker/WebSocket/WASM/iframe 和脚本加载信号。
- 只有确认存在具体对抗信号时才使用 `--mode intervene`；不默认修改时间、随机数或全局环境。
- `window.__JSRA_ADVERSARIAL__.uninstall()` 用于恢复已记录的函数/属性 Patch。
- 基线与干预结果可用 `adversarial_diff.py` 比较；事件增加不等于目标请求成功。

## Phase 2: Webpack/模块解析
```bash
python3 scripts/emit_module_probe.py --output generated/module_probe.js
```
- 优先级：`__webpack_require__` → `webpackChunk*` push → module cache → 离线解析

## Phase 2.1: 静态 AST 分析（可选）
```bash
node scripts/ast_candidate_analyzer.js --input bundle.js --output artifacts/static_candidates.json
```

## Phase 2.2: 源码级属性 tap
```bash
node scripts/source_instrumentor.js \
  --input bundle.js --output generated/bundle.tap.js \
  --objects navigator,document,screen --properties webdriver,userAgent,cookie
```
- 只改写显式选择的简单 member read；跳过字符串、注释、赋值和方法调用。
- 先验证原始/插桩脚本的异常、请求和关键输出，再扩大范围。

## Phase 2.5: 证据图构建
```bash
python3 scripts/build_evidence_graph.py --probe artifacts/probe_dump.json --modules artifacts/module_dump.json --output artifacts/evidence_graph.json
```

## Phase 3: 候选发现
```bash
python3 scripts/detect_encryption.py --probe-artifacts artifacts/probe_dump.json --output artifacts/encryption_candidates.json
```
- 8 维评分：name、source_keyword、runtime_stack、request_correlation、input_output_flow、module_export、cross_source、verification

## Phase 3.5: 差分验证
```bash
python3 scripts/differential_verifier.py emit --analysis analysis_result.json --candidates artifacts/encryption_candidates.json --output generated/differential_verifier.js
# 浏览器执行后
python3 scripts/differential_verifier.py apply --candidates artifacts/encryption_candidates.json --results artifacts/differential_verification_results.json --output artifacts/encryption_candidates.verified.json
```

## Phase 4: 组装 analysis_result.json
- 包含所有必需字段（见 `references/output-contract.md`）
- `entrypoint_discovery.strategy` 如实反映发现路径
- `confidence=high` 需至少两类证据

## Phase 5: 代码生成
```bash
python3 scripts/emit_jsrpc_stub.py --analysis analysis_result.json --candidates artifacts/encryption_candidates.verified.json --output generated/jsrpc_inject.js
python3 scripts/emit_flask_proxy.py --analysis analysis_result.json --output generated/flask_proxy.py
python3 scripts/check_delivery_contract.py \
  --proxy generated/flask_proxy.py \
  --output artifacts/delivery_contract.json
python3 scripts/manage_services.py --service jsrpc --analysis analysis_result.json --output artifacts/jsrpc_status.json --action start --force
python3 scripts/manage_services.py --service flask --analysis analysis_result.json --flask-file generated/flask_proxy.py --output artifacts/flask_status.json --action start --force
```

## Phase 6: 注入浏览器
- 通过 Chrome DevTools MCP 导航到目标根页面，不使用静态 HTTP 请求代替真实页面。
- 用 `evaluate_script` 依次注入 `JsEnv_Dev.js` 和 `generated/jsrpc_inject.js`；若使用运行时探针，先注入探针再注入 JSRPC。
- 验证：`curl http://127.0.0.1:12080/list` 只能证明服务端口可访问，不能代替 action 级 smoke test。
- 调用 JSRPC 后必须检查 `plaintext`、最终 `request.url`、`requestBody`、`status` 和最终 `response`；仅出现函数名或候选分数不得判定通过。
- 将真实 action 结果保存为 `artifacts/jsrpc_smoke.json`，执行 `python3 scripts/validate_browser_evidence.py --input artifacts/jsrpc_smoke.json --output artifacts/browser_evidence.json`；能取得桥接状态时加 `--require-session`。验证失败时不得进入“验证通过”的正式输出。
- Flask 验证必须额外提交一份外层 `application/octet-stream` 的完整 HTTP 报文，确认返回完整报文、目标字段已替换且 `Content-Length` 正确；同时保留 `dataBody` wrapper 回归。
- 标准捕获层同时覆盖 `fetch` 与 `XMLHttpRequest`；若成功响应会触发页面跳转，在分析配置中使用 `capture.suppress_page_success=true`，只抑制 `fetch` 测试页面的后续跳转，仍记录真实响应。XHR 成功响应只采集不改写。

### 可复制验证命令

```bash
curl -sS --get \
  --data-urlencode group=jsra \
  --data-urlencode action=<action_name> \
  --data-urlencode 'param={"parameter":"<parameter>","value":"<plaintext>"}' \
  http://127.0.0.1:12080/go | python3 -m json.tool
```

预期 `data` 中同时出现 `plaintext`、`requestBody`、`response` 和 `status`；若缺少任一项，应继续补运行时捕获或标记为未完成。

## Phase 7: Burp 文档
```bash
python3 scripts/emit_burp_doc.py --analysis analysis_result.json --status artifacts/flask_status.json --output generated/burp-autodecoder.md
```

## Phase 8: 校验
```bash
python3 scripts/validate_artifacts.py --analysis analysis_result.json --candidates artifacts/encryption_candidates.verified.json --generated generated/ --report artifacts/validation_report.json
```

## Phase 9: 经验沉淀
- 更新 `references/evolution_matrix.json`
- 保留标准最终报告结构，在其中追加本轮对抗信号、探针健康和差分结论。

## 入口发现失败时的处理
1. 全局函数搜索 → React/Vue 组件 → Webpack require → 运行时 Hook
2. initScript Hook → 搜索 RSA 实例
3. 静态 AST 分析
4. 源码分析 + Python 实现
5. 标记为 `unsupported`，生成隔离报告

## 关闭服务
```bash
python3 scripts/manage_services.py --service jsrpc --analysis analysis_result.json --output artifacts/jsrpc_status.json --action stop
python3 scripts/manage_services.py --service flask --analysis analysis_result.json --output artifacts/flask_status.json --action stop
```
