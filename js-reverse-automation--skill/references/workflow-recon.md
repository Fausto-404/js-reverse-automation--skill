# 工作流说明

本文档是 `SKILL.md` 背后的执行工作流。每个阶段都明确规定了输入、输出、成功门槛、失败门槛以及是否继续执行的规则。

## Phase 0: 输入校验与规范化
- 输入
  - 原始用户请求，包含 `Target URL`、`Parameters To Analyze`，以及 `Optional Fetch Example`。
- 输出
  - `artifacts/phase0_input.json`
- 成功条件
  - 必填字段存在。
  - URL 语法合法。
  - 参数列表在规范化后非空。
- 失败条件
  - 缺少必填字段。
  - URL 非法。
  - 参数列表为空。
- 是否继续
  - 只有 `scripts/check_inputs.py` 退出码为 `0` 时才继续。
- 失败处理
  - 立即停止工作流。
  - 输出结构化错误，包含 `phase=0`、`missing_fields` 和 `fix_hint`。

## Phase 1: 浏览器连接与链路复现

- 默认使用 `navigate_page(initScript=...)` 预注入 runtime probe，在页面任何 JS 执行前安装 Hook
- 如果目标页面需要先加载才能触发目标动作，则在页面加载后用 `evaluate_script` 补充注入

### Phase 1.5: 运行时 Hook 探针 + 健康检测
- 输入
  - 目标参数名
- 输出
  - `generated/runtime_hook_probe.js`
  - `window.__JSRA_TRACE__` dump JSON
- 成功条件
  - 探针成功注入页面（`window.__JSRA_TRACE__` 存在）
  - 重新触发目标动作后，`requests` 数组中出现包含目标参数的请求证据
  - 至少捕获到一条 fetch/XHR 请求证据和调用栈
- 运行时健康检测（不猜分类，只记证据）
  - `evaluate_script` 成功 → `probe_status=ok`
  - 超时 → `probe_status=timeout`，检查 console 有无 debugger 语句判断 `timeout_reason`
  - 返回错误 → `probe_status=crashed`
  - 部分 Hook 成功 → `probe_status=partial`
- 降级策略
  - `ok` → 正常流程
  - `partial` → 继续但标记缺失证据
  - `timeout/crashed` → 降级到静态分析，记录 `fallback_used=true`
- 失败条件
  - 探针注入失败（页面反调试阻断）
  - 触发目标动作后无任何请求证据
- 失败处理
  - 记录反调试症状，参考 `references/antidebug-patterns.md` 处理
  - 不阻断后续 Phase（降级到静态分析）

### Phase 2.5: Webpack/模块运行时解析
- 输入
  - Phase 1.5 的 Hook 调用栈证据
  - 页面模块系统检测结果
- 输出
  - `generated/module_probe.js`
  - `window.__JSRA_MODULES__` dump JSON
- 优先级链（按顺序尝试，不跳级）
  1. 先找真实 `__webpack_require__`（`window.__webpack_require__`、chunk array 的 runtime 属性）
  2. 再找 `webpackChunk*` 的 runtime push 机会（hook push 方法，等下次 chunk 加载时捕获）
  3. 再从已加载 module cache 搜索 export（如果 require 已捕获，遍历 `require.c`）
  4. 最后才离线解析 chunk factory（只生成 candidate，不直接当入口，必须和运行时证据交叉验证）
- 成功条件
  - 探针成功注入
  - 如果检测到 Webpack，`candidateExports` 非空
  - 候选出口与 Hook 调用栈交叉验证完成
- 失败条件
  - 未检测到模块系统（非 Webpack/Vite/Rollup 应用）
  - 检测到 Webpack 但无法捕获 `__webpack_require__`
- 失败处理
  - 降级到 `global_path` 或 `manual_observed_only` 策略
  - 记录模块系统类型和失败原因到 `module_runtime`
- 输入
  - `artifacts/phase0_input.json`
- 输出
  - `artifacts/phase1_trace.json`
- 成功条件
  - chrome-devtools-mcp 成功附着到真实浏览器标签页。
  - 目标页面成功加载。
  - 成功复现目标请求链路，或将 fetch 示例映射到真实请求。
  - 已通过网络证据锁定至少一个目标请求，并确认参数落点。
  - 如果存在多个相似请求，已用变量对比、请求详情或 Hook 证据缩小到首选请求。
  - 如果浏览器内成功、页面外失败，已记录可见的协议层差异或将其标记为待验证风险。
- 失败条件
  - 浏览器连接失败。
  - 页面无法加载，或被环境限制阻断。
  - 请求链路无法复现。
  - 只能得到源码关键词命中，无法回到真实请求。
- 是否继续
  - 只有存在针对目标参数的具体请求记录时才继续。
- 失败处理
  - 记录浏览器版本、标签页 URL、网络错误，以及代理或扩展限制是否阻断了本次执行。
  - 如果出现反调试症状，标注 `references/antidebug-patterns.md` 中疑似对应的规则类别。
  - 优先参考 `references/evidence-collection.md` 补足请求证据，不要直接跳到大范围源码搜索。
  - 如怀疑协议层约束，参考 `references/protocol-resilience.md` 先记录浏览器成功路径与页面外失败路径的差异。

## Phase 2: 参数入口发现
- 输入
  - `artifacts/phase0_input.json`
  - `artifacts/phase1_trace.json`
- 输出
  - `artifacts/phase2_entrypoints.json`
- 成功条件
  - 每个目标参数至少找到一个候选入口。
  - 每个候选入口都带有证据，例如调用栈、源码文件、对象路径或 hook 输出。
  - 首选入口能够解释参数从明文到发包前形态的至少两个连续观测点。
- 失败条件
  - 没有找到候选入口。
  - 只有启发式关键词命中，没有运行时证据。
  - 只能定位到通用加密库，无法回到业务调用方。
- 是否继续
  - 只有选出一个首选入口，或明确记录了歧义时才继续。
- 失败处理
  - 记录最后一个可观测的参数变更点。
  - 给出下一步探针建议，例如函数 hook、XHR/fetch 断点、加密库 hook 或反调试规则。
  - 优先参考 `references/evidence-collection.md` 中的源码定位和 Hook 调试规则。

## Phase 3: 调用路径与依赖提取
- 输入
  - `artifacts/phase2_entrypoints.json`
- 输出
  - `artifacts/phase3_dependencies.json`
- 成功条件
  - 已识别可调用的函数路径或 resolver 策略。
  - 已枚举必要依赖，包括对象路径、`this` 绑定、异步行为、预加载全局对象、模块或编解码器。
  - 已知输入形态和输出形态。
  - 如果使用了反检测 patch，已验证 patch 只影响观测或解锁链路，不影响最终生成产物形态。
  - 如果存在协议层约束，已区分哪些属于运行时必需条件，哪些只应记录为风险。
- 失败条件
  - 找到了函数，但仍无法可靠调用。
  - 缺少必要运行时上下文。
  - 依赖链不完整。
  - 只有 patch 后才能调用，但未能说明 patch 是否会污染最终代码生成逻辑。
- 是否继续
  - 只有当前数据足以生成确定性代码时才继续。
- 失败处理
  - 将该产物标记为 `partial`。
  - 记录尚未解决的运行时依赖。
  - 如涉及反检测验证，参考 `references/antidebug-patterns.md`。
  - 如涉及协议层约束，参考 `references/protocol-resilience.md`。

## Phase 4: 生成 `analysis_result.json`
- 输入
  - `artifacts/phase0_input.json`
  - `artifacts/phase1_trace.json`
  - `artifacts/phase2_entrypoints.json`
  - `artifacts/phase3_dependencies.json`
- 输出
  - `analysis_result.json`
- 成功条件
  - 所有必需的顶层区块都存在。
  - 每个目标参数都映射到了首选入口。
  - 诊断、风险和校验目标都已填充。
- 失败条件
  - 缺少强制区块。
  - schema 非法，或 action 元数据不一致。
- 是否继续
  - 只有 `analysis_result.json` 的顶层区块和参数契约完整时才继续（此时不做产物文件校验，产物校验在 Phase 7 执行）。
- 失败处理
  - 停止后续生成阶段。
  - 输出包含 JSON pointer 路径的 schema 错误列表。

## Phase 5: 生成 JSRPC 注入代码并完成环境注入
- 输入
  - `analysis_result.json`
- 输出
  - `artifacts/jsrpc_status.json`
  - `artifacts/flask_status.json`
  - `generated/jsrpc_inject.js`
  - `generated/flask_proxy.py`
- **Step 1: 生成代码**
  - **必须**使用 `scripts/emit_jsrpc_stub.py` 生成，禁止手动编写：
    - `python3 scripts/emit_jsrpc_stub.py --analysis analysis_result.json --output generated/jsrpc_inject.js`
  - **必须**使用 `scripts/emit_flask_proxy.py` 生成，禁止手动编写：
    - `python3 scripts/emit_flask_proxy.py --analysis analysis_result.json --output generated/flask_proxy.py`
- **Step 2: 启动服务**
  - JSRPC 服务器：
    - 运行 `python3 scripts/start_jsrpc.py --analysis analysis_result.json --output artifacts/jsrpc_status.json`
    - 脚本自动：检查端口 → 已在跑则输出 PID + stop_command → 未跑则用 configured binary_path 启动 → 路径无效则提示用户
    - 成功状态：`already_running` 或 `started`（均含 `pid` 和 `stop_command`）
  - Flask 代理：
    - 运行 `python3 scripts/start_flask.py --analysis analysis_result.json --flask-file generated/flask_proxy.py --output artifacts/flask_status.json`
    - 成功状态：`started`
    - 记录 PID 和 stop_command 供结束时使用
- **Step 3: 注入浏览器**
  - 页面上必须已加载 `Hlclient`（`typeof Hlclient === 'function'`）。如未加载，先注入 `scripts/JsEnv_Dev.js` 中的 Hlclient 定义。
  - 通过 `evaluate_script` 将生成的 JSRPC 代码注入到页面。
  - 注入后通过 `curl http://127.0.0.1:12080/list` 验证 group 已注册。
  - **多客户端竞争**：`/list` 可能返回多个 clientId（旧 WebSocket 连接残留）。验证时必须使用 `&clientId=<最新注册的id>` 参数，避免命中已失效的旧连接。Flask 代理已自动查询 `/list` 获取有效 clientId。
- 成功条件
  - JSRPC 服务器在监听。
  - action 注册存在。
  - 入口解析逻辑与分析结果一致。
  - Flask 代理在监听且 /healthz 返回 200。
- 失败条件
  - JSRPC 二进制找不到（需要用户提供路径）。
  - 没有 action 注册。
  - 入口路径缺失，或与分析结果不一致。
- 是否继续
  - 只有通过产物校验后才继续。
- 失败处理
  - 将 jsrpc_status.json 中的 status 和 hint 输出给用户。
  - 保留已生成文件，在校验结果中精确标出缺失项。

## Phase 6: 生成 Burp 对接文档
- 输入
  - `analysis_result.json`
- 输出
  - 生成的 Burp autoDecoder 文档
- **必须**使用 `scripts/emit_burp_doc.py` 生成，禁止手动编写：
  - `python3 scripts/emit_burp_doc.py --analysis analysis_result.json --output generated/burp-autodecoder.md`
- 成功条件
  - 文档中包含代理 URL、HTTP 方法、请求表单字段和返回契约。
  - 文档中存在验证步骤和失败说明。
- 失败条件
  - 缺少端点，或缺少必需表单字段。
  - 没有验证步骤或排障章节。
- 是否继续
  - 只有文档通过校验后才继续。
- 失败处理
  - 保留已生成文档，并记录缺失章节。

## Phase 7: 校验与诊断
- 输入
  - `analysis_result.json`
  - 生成的 JSRPC 文件
  - 生成的 Flask 代理文件
  - 生成的 Burp 文档
- 输出
  - `artifacts/validation_report.json`
- 成功条件
  - 所有必需产物检查都通过。
  - 已记录警告、残余风险和测试命令。
- 失败条件
  - 任一必需检查失败。
- 是否继续
  - `yes`，进入 Phase 8，记录成功或失败经验。
- 失败处理
  - 将校验报告作为 Phase 7 状态对象写出。
  - 包含 phase id、失败文件、失败规则以及建议的下一步动作。
  - 继续进入 Phase 8，以便沉淀失败策略并执行记忆失效降级。

## Phase 8: 经验沉淀与对抗库演进

- 输入
  - `artifacts/phase0_input.json`
  - `analysis_result.json`
  - `artifacts/validation_report.json`
- 输出
  - 更新后的 `references/evolution_matrix.json`
- 成功条件
  - 成功提取域名特征、最新成功 Action 命名并写入或更新 `domains`。
  - 若任务期间触发了 `references/antidebug-patterns.md` 规则或发生了修复重试，成功提取代码特征、阻断关键字并归纳写入 `behavioral_features`。更新对应的 `updated_at` 时间戳，并使 `success_count` 加 1。
  - 成功沉淀可复用 STE 经验：`strategic_principle`（战略原则）、`tactical_manual`（战术手册）和 `applicable_scenarios`（适用场景）。
  - 若属于历史成功策略本次失效的情况，成功将该方案移入 `failed_attempts`。
- 失败条件
  - 覆写导致历史其他域名的记忆丢失。
  - 写入中途进程中断导致 JSON 文件损坏。
- 是否继续
  - `no`（工作流终点）。
- 失败处理
  - 记录合并错误日志，保持原记忆文件不损坏。
