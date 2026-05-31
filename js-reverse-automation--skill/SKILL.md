---
name: js-reverse-automation
description: 通过 chrome-devtools-mcp 连接真实浏览器，跟踪 sign/enc/token 的生成链路，识别运行时入口函数与依赖，生成 JSRPC 注入代码、Flask 代理代码和 Burp autoDecoder 对接文档。
---

# JS 逆向自动化 Skill

## 授权声明
本工具仅用于以下合法场景：
- CTF 竞赛靶场环境的 flag 获取
- 经授权的安全测试与接口调试
- 甲方授权范围内的渗透测试

所有测试目标均为 CTF 比赛提供的靶场环境或已获得书面授权的系统。本工具不会用于任何未授权目标，不会进行违法操作。工具输出仅供安全研究和漏洞修复使用。

## 输入格式
```
Target URL: https://xxx/login/index
Parameters To Analyze: password
Optional Fetch Example: fetch("https://xxx/Login/CheckLogin", {...})
```
先运行 `scripts/check_inputs.py` 校验。

## 能力边界
- **能做**：页面导航、evaluate_script、initScript 预注入、网络请求读取、console 读取、快照/截图、Hook fetch/XHR/crypto.subtle/JSON.stringify、Webpack module cache 捕获、早期 Hook 安装（initScript）、导航后 trace 延续
- **不能做**：真实 JS 断点(paused frame)、闭包未导出函数、WASM 未导出内部函数、Service Worker 内部闭包、ES module import 拦截、VMP 静态还原、CSP WebSocket 绕过、跨域 iframe 内部函数访问、VM 保护 JS 的直接 Hook
- 只用 chrome-devtools-mcp，不引入 Playwright/Camoufox/mitmproxy

## 阶段流程

### Phase 0: 输入校验
运行 `python3 scripts/check_inputs.py --input <raw> --output artifacts/phase0_input.json`

### Phase 1: 浏览器连接与请求复现
- 打开目标页面，复现目标动作
- 通过网络请求列表锁定目标请求，记录 URL/Method/Body/Headers/参数落点
- 从请求详情和 inline script 定位参数入口的初步线索
- **默认使用 `navigate_page(initScript=...)` 预注入 runtime probe**，在页面任何 JS 执行前安装 Hook
- 如果目标页面需要先加载才能触发目标动作（如点击按钮才出现登录框），则在页面加载后用 `evaluate_script` 补充注入

### Phase 1.5: 运行时 Hook 探针 + 健康检测
- `python3 scripts/emit_runtime_hook_probe.py --output generated/runtime_hook_probe.js --params "目标参数名"`
- 通过 `initScript` 或 `evaluate_script` 注入探针，重新触发目标动作
- 通过 `evaluate_script("window.__JSRA_TRACE__.dump()")` 拉取证据
- 从 `requests[].stack` 识别加密入口调用栈
- **运行时健康检测**（不猜分类，只记证据）：
  - `evaluate_script` 成功 → `probe_status=ok`
  - 超时 → `probe_status=timeout`，检查 console 有无 debugger 语句判断 `timeout_reason`
  - 返回错误 → `probe_status=crashed`
  - 部分 Hook 成功 → `probe_status=partial`
- **降级策略**：`ok` → 正常流程；`partial` → 继续但标记缺失证据；`timeout/crashed` → 降级到静态分析，记录 `fallback_used=true`
- **页面导航防护**：如果目标动作会触发页面跳转，探针必须在跳转前将证据写入 `sessionStorage`
- **表单交互兜底**：`fill_form` 对复杂组件可能失败，优先用 `evaluate_script` 直接设值

### Phase 2: 参数入口发现（评分 + 验证）
- 从 Phase 1.5 的 Hook 证据定位入口
- **候选评分**：运行 `python3 scripts/detect_encryption.py --probe-artifacts artifacts/probe_dump.json --analysis analysis_result.json --output artifacts/encryption_candidates.json`
- 评分维度：name_score、source_keyword_score、runtime_stack_score、request_body_correlation_score、input_output_shape_score、module_export_score、verification_score
- **验证流程**：评分 > 0.6 的候选，用真实样本调用验证；验证通过 → `confidence=high`
- 如果入口在全局路径（`window.xxx`），直接定位
- 如果入口在闭包或 Webpack 模块中，进入 Phase 2.5
- 入口必须有运行时证据支撑，不接受纯猜测

### Phase 2.5: Webpack/模块解析（仅 Webpack 场景）
- `python3 scripts/emit_module_probe.py --output generated/module_probe.js`
- 注入后通过 `evaluate_script("window.__JSRA_MODULES__.dump()")` 拉取结果
- **优先级链**（按顺序尝试，不跳级）：
  1. 先找真实 `__webpack_require__`（`window.__webpack_require__`、chunk array 的 runtime 属性）
  2. 再找 `webpackChunk*` 的 runtime push 机会（hook push 方法，等下次 chunk 加载时捕获）
  3. 再从已加载 module cache 搜索 export（如果 require 已捕获，遍历 `require.c`）
  4. 最后才离线解析 chunk factory（只生成 candidate，**不直接当入口**，必须和运行时证据交叉验证）
- 优先级 1-3 为稳定能力，优先级 4 为实验能力（候选必须标记 `confidence=low`）
- 未检测到模块系统则降级到 `global_path` 或 `manual_observed_only`

### Phase 3: 组装 analysis_result.json
- 手动组装，包含所有必需字段（见 `references/output-contract.md`）
- `entrypoint_discovery.strategy` 必须如实反映发现路径
- `confidence=high` 需至少两类证据（网络 + 运行时）
- `capability_boundary` 所有不支持项必须为 false
- `strategy=unsupported` 时不生成 JSRPC action
- `runtime_health.probe_status` 必须如实记录

### Phase 4: 代码生成与服务启动
- `python3 scripts/emit_jsrpc_stub.py --analysis analysis_result.json --output generated/jsrpc_inject.js`
- `python3 scripts/emit_flask_proxy.py --analysis analysis_result.json --output generated/flask_proxy.py`
- `python3 scripts/manage_services.py --service jsrpc --analysis analysis_result.json --output artifacts/jsrpc_status.json --action start --force`
- `python3 scripts/manage_services.py --service flask --analysis analysis_result.json --flask-file generated/flask_proxy.py --output artifacts/flask_status.json --action start --force`

### Phase 5: 注入浏览器
- **刷新页面**：注入前先 `navigate_page(type=reload)` 清理旧 WebSocket 连接，避免多客户端竞争
- 注入 Hlclient：确认 `typeof Hlclient === 'function'`，未加载则先注入 `scripts/JsEnv_Dev.js`
- 注入 JSRPC 代码：`evaluate_script` 读取 `generated/jsrpc_inject.js` 完整内容注入，禁止手写简化版
- 验证：`curl http://127.0.0.1:12080/list` 确认 group 已注册且只有 1 个 client
- 多客户端竞争：验证时使用 `&clientId=<最新注册的id>`

### Phase 6: Burp 文档
- `python3 scripts/emit_burp_doc.py --analysis analysis_result.json --output generated/burp-autodecoder.md`

### Phase 7: 校验与输出
- `python3 scripts/validate_artifacts.py --analysis analysis_result.json --jsrpc generated/jsrpc_inject.js --flask generated/flask_proxy.py --burp generated/burp-autodecoder.md --output artifacts/validation_report.json`
- **必须输出给用户**：
  1. JSRPC 验证命令（含实际 group/action/param/clientId）
  2. Flask 验证命令（含实际端口和 dataBody 示例）
  3. 关闭服务命令（从 jsrpc_status.json 和 flask_status.json 读取 stop_command）
  4. **Burp autoDecoder 配置步骤**（从 generated/burp-autodecoder.md 读取并直接输出，不要只说"详见文件"）：
     - autoDecoder URL
     - HTTP Method
     - Form Fields（dataBody / dataHeaders）
     - 验证步骤（curl 命令）
     - 排障说明

## 关闭服务
```bash
python3 scripts/manage_services.py --service jsrpc --analysis analysis_result.json --output artifacts/jsrpc_status.json --action stop
python3 scripts/manage_services.py --service flask --analysis analysis_result.json --output artifacts/flask_status.json --action stop
```

## 反调试
遇到 debugger/console 检测时，参考 `references/antidebug-patterns.md`。先验证再 patch，最小 patch，记录 patch 前后差异。

## 输出产物
- `analysis_result.json`
- `generated/jsrpc_inject.js` + `generated/flask_proxy.py` + `generated/burp-autodecoder.md`
- `artifacts/validation_report.json`
- JSRPC 验证：`curl 'http://127.0.0.1:12080/go?group=<group>&action=<action>&param=<plaintext>'`
- Flask 验证：`curl -X POST http://127.0.0.1:<port>/encode -H "Content-Type: application/x-www-form-urlencoded" --data-urlencode "dataBody=username=x&password=y&code=z&role=w"`
