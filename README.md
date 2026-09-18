<h1 align="center">js-reverse-automation--skill</h1>
<p align="center">
  <code>前端JS逆向全流程自动化Skill</code>
</p>
<div align="center">

<p align="center">
  <a href="https://github.com/Fausto-404/js-reverse-automation--skill-test/releases">
    <img src="https://img.shields.io/github/v/release/Fausto-404/js-reverse-automation--skill?style=flat-square&label=release&color=blue&cacheSeconds=3600" alt="Release">
  </a>

  <a href="https://github.com/Fausto-404/js-reverse-automation--skill-test/stargazers">
    <img src="https://img.shields.io/github/stars/Fausto-404/js-reverse-automation--skill?style=flat-square&label=stars&color=brightgreen&cacheSeconds=3600" alt="GitHub Stars">
  </a>

  <a href="https://github.com/Fausto-404/js-reverse-automation--skill-test/network/members">
    <img src="https://img.shields.io/github/forks/Fausto-404/js-reverse-automation--skill?style=flat-square&label=forks&color=orange&cacheSeconds=3600" alt="GitHub Forks">
  </a>

  <a href="https://github.com/Fausto-404/js-reverse-automation--skill-test/releases">
    <img src="https://img.shields.io/github/downloads/Fausto-404/js-reverse-automation--skill/total?style=flat-square&label=downloads&color=success&cacheSeconds=3600" alt="Downloads">
  </a>
</p>

</div>

<p align="center">
  <strong>结合chrome-devtools-mcp的能力并加上Skill的规范，实现JSRPC+Flask+autoDecoder方案的前端JS逆向自动化分析，提升JS逆向的效率</strong>
</p>

<p align="center">
</p>

## 适用场景

- 登录参数加密（RSA/AES/SM2/SM4/MD5/自定义编码）
- 数据爬取时响应内容加密
- 请求签名（sign/token/enc）
- 需要将js逆向逻辑封装为可复用的代码
- 需要与 Burp 配合进行抓包、改包

## 解决传统 AI 逆向的四大痛点

本项目专注于 **实战工程落地** ，通过更轻量的架构打通逆向到实战的最后一公里：

* **从“死磕补环境”到“JSRPC 动态榨取”** ：
  不强求 AI 去补全复杂的浏览器上下文，而是指导 AI 建立 JSRPC 远程调用。直接将真实浏览器作为算法解析器，绕过混淆逻辑，0 成本获取加密结果。

* **从“孤岛式输出”到“全链路生产交付”** ：
  拒绝只停留在“看懂代码”阶段。AI 交付的不仅是解析思路，更是直接可运行的 **Python Flask 中转服务** 与 **Burp Suite (autoDecoder) 联动配置**，无缝接入渗透工作流。

* **从“单阶段盲跑”到“契约化阶段校验”** ：
  引入明确的 Phase 0-9 阶段划分，以 `analysis_result.json` 作为中间产物契约。在生成代码后强制触发本地验证器校验，大幅降低 AI 在复杂长文本下的幻觉与语法错误。

* **从“单次对话记忆”到“经验持续演进”** ：
  打破“新对话即白纸”的限制。利用 `references/evolution_matrix.json` 记忆库，允许 AI 跨任务沉淀对抗经验，实现技能包针对新型混淆与反调试的持续自我演进。

## 流程设计思路
针对js逆向中常用的远程调用法进行js逆向（如JSRPC+Mitmproxy、JSRPC+Flask等）中，初始配置阶段中面对的定位加密函数、编写注册代码、编写python代码等繁琐操作，通过引入AI的MCP和Skill技术进行赋能，让AI自动完成函数发现与注册代码生成，最终实现从“半自动”到“高自动”的跨越，人员全程只需下方指令，并最终配置一下burp即可完成JS逆向的全流程。
<img width="2064" height="1108" alt="image" src="https://github.com/user-attachments/assets/fc13f276-f667-486a-8506-221c0c55507e" />

## 核心能力
这不是“找到一个加密函数”的工具，而是一条从真实浏览器取证、对抗运行时分析，到 JSRPC/Flask/Burp 交付的完整逆向链路。

| 能力方向 | 核心亮点 |
| --- | --- |
| **真实入口发现** | 通过 MCP 连接真实浏览器，触发并跟踪加密/签名链路；Hook 捕获 fetch、XHR、crypto、WebSocket、CryptoJS、JSEncrypt、sm2、sm3、sm4 的调用与参数流转；同时解析 Webpack `__webpack_require__` 和 module cache。 |
| **候选定位与验证** | 采用 8 维候选评分、真实样本验证、主动调用和请求字段指纹差分，持续收敛到可复现的真实入口；用 SHA-256 证据图关联 producer→consumer 数据流。 |
| **运行时对抗分析** | 观测反调试、反 Hook、完整性校验、环境属性、动态代码、多 Realm、响应链和加载器事件；通过持久 Hook、统一编排、外部替换重建和安全卸载保持取证能力。 |
| **JSVMP 与重度混淆** | 以源码级保守属性 tap 关联插桩位置、运行时热点和调用结果；结合基线/干预差分分析控制流与加密运行时行为，并支持控制台清理、历史导航、存储访问和页面关闭等信号观测。 |
| **浏览器证据闭环** | 绑定 tab/document 会话身份，管理浏览器动作生命周期；使用 `validate_browser_evidence.py` 验证明文、最终请求体、路由、HTTP 状态和业务响应，形成可追溯的动作级证据。 |
| **自动化交付** | 自动管理 JSRPC 与 Flask 服务，生成注入代码并完成浏览器注册验证；输出 Burp autoDecoder 配置，覆盖完整 HTTP 报文、包装模式、请求/响应方向、端口回退和可复制验证命令。 |

**最终产物**：明文、密文/签名、最终请求、服务端响应、JSRPC 注入代码、Flask 代理、Burp autoDecoder 配置和验证报告。

## 项目结构
```latex
js-reverse-automation/
├── SKILL.md                          # 入口文件（精简版）
├── workflow/
│   └── pipeline.md                   # 详细工作流（Phase 0-9）
├── constraints/
│   └── rules.md                      # 约束规则
├── references/                       # 参考规范与知识库（按需加载）
│   ├── output-contract.md            # 输入输出契约
│   ├── capability-boundaries.md      # 能力边界说明
│   ├── architecture.md               # 架构说明
│   ├── security-model.md             # 安全模型
│   ├── antidebug-patterns.md         # 反调试模式与 Patch
│   ├── browser-session-contract.md   # 浏览器会话与证据契约
│   ├── advanced-entrypoints.md       # 复杂入口场景（Webpack/异步/WASM）
│   ├── evidence-collection.md        # 取证方法（Hook/源码/网络）
│   └── evolution_matrix.json         # 跨任务经验记忆库
├── schemas/                          # JSON Schema 定义
│   ├── analysis_result.schema.json
│   ├── candidates.schema.json
│   ├── probe_dump.schema.json
│   └── adversarial_trace.schema.json
├── scripts/                          # 自动化工具脚本
│   ├── common.py                     # 共享工具库
│   ├── check_inputs.py               # 输入校验
│   ├── emit_runtime_hook_probe.py    # 运行时 Hook 探针生成
│   ├── emit_adversarial_runtime_probe.py # 对抗运行时探针生成
│   ├── source_instrumentor.js        # 保守源码级属性插桩
│   ├── adversarial_diff.py            # 原始/干预差分
│   ├── emit_module_probe.py          # Webpack 模块探针生成
│   ├── build_evidence_graph.py       # 证据图构建
│   ├── detect_encryption.py          # 加密函数候选评分
│   ├── differential_verifier.py      # 差分验证
│   ├── emit_jsrpc_stub.py            # JSRPC 注入代码生成
│   ├── emit_flask_proxy.py           # Flask 代理生成
│   ├── emit_burp_doc.py              # Burp 文档生成
│   ├── manage_services.py            # 服务管理（JSRPC/Flask 启停）
│   ├── validate_artifacts.py         # 四层校验
│   ├── validate_browser_evidence.py # action 级浏览器/JSRPC 证据校验
│   ├── quarantine.py                 # 隔离报告
│   ├── doctor.py                     # 依赖检查
│   ├── env_patcher.py                # 环境补丁
│   ├── classify_anticrawl.py         # 反爬分类
│   ├── identify_crypto.py            # 加密算法识别
│   ├── hook_templates.py             # Hook 模板库
│   ├── ast_candidate_analyzer.js     # AST 静态分析
│   └── JsEnv_Dev.js                  # Hlclient WebSocket 客户端库
├── generated/                        # AI 运行生成的中间代码/配置产物
│   ├── jsrpc_inject.js               # JSRPC 浏览器端注入代码
│   ├── flask_proxy.py                # Flask 本地代理服务
│   ├── burp-autodecoder.md           # Burp autoDecoder 配置文档
│   └── runtime_hook_probe.js         # 运行时 Hook 探针脚本
└── artifacts/                        # 运行时的动态状态与报告产物
    ├── phase0_input.json             # 校验后的输入
    ├── probe_dump.json               # 运行时事件数据
    ├── module_dump.json              # Webpack 模块发现结果
    ├── evidence_graph.json           # 事件关联图
    ├── encryption_candidates.json    # 加密函数候选评分
    ├── validation_report.json        # 四层校验报告
    ├── quarantine.json               # 隔离报告
    ├── jsrpc_status.json             # JSRPC 服务状态
    ├── flask_status.json             # Flask 服务状态
    └── browser_evidence.json         # action 级真实调用证据验收
```

## 使用示意
1. 安装 Python 运行依赖

```bash
python3 -m pip install -r requirements.txt
```

2. 安装 MCP 服务

```bash
# Claude Code
claude mcp add chrome-devtools -- npx -y chrome-devtools-mcp@latest
# Codex
codex mcp add chrome-devtools -- npx -y chrome-devtools-mcp@latest
# Gemini
gemini mcp add chrome-devtools npx -y chrome-devtools-mcp@latest
```
3. 将 `js-reverse-automation` 目录放入 Skill 目录，然后输入：

```
# 第一次建议带上jsrpc路径，后续流程会更稳
Target URL: https://xxx.com/login
Parameters To Analyze: password
Optional Fetch Example: fetch("https://xxx.com/api/login", {"body":"...","method":"POST"})
```
等待运行完成【第一次使用会生成产物文件夹】，按输出结果，验证有效性以及配置 Burp 即可。

## 效果检验
1. 获取输入所需信息【参考如图1、2、3】
<img width="2182" height="1444" alt="image" src="https://github.com/user-attachments/assets/a0edb08b-ef21-4059-bae5-d9a255a69d30" />
2. 按照模版编写提示词并输入给支持 MCP 的模型进行验证
<img width="1810" height="1264" alt="image" src="https://github.com/user-attachments/assets/7703c06a-0f42-4c8d-b2c9-6d18172c1194" />
4. 等待输出结果
<img width="1380" height="1462" alt="image" src="https://github.com/user-attachments/assets/9419df5c-f876-41ac-bdba-60d13a603445" />
4. 依据结果输出测试即可
<img width="2216" height="1612" alt="image" src="https://github.com/user-attachments/assets/557946b1-1f68-4ba7-8b6a-f794d0858b18" />
5. 使用完后记得按照指示关闭jsrpc和flask！！！

## 实战案例
包括但不限于：
- xx大学：MD5（全局函数） ✅
- xx大学：SM2 国密 + DOM 公钥 ✅
- xx网：RSA-2048 + JSEncrypt 懒加载 ✅
- xx游：RSA-1024 + Webpack 闭包 ✅
- 某音乐：AES & RSA 组合 + params / encSecKey 类结构 ✅
- 某理工学院：RSA-1024 + React 组件 encodePass ✅
- xx鱼：RSA-1024 + 全局 miniLogin.rsaPassword ✅
- xx神：RSA-1024 + 模块内部加密（源码分析） ✅

## 引用工具
- JsRpc：https://github.com/jxhczhl/JsRpc 
- autoDecoder：https://github.com/f0ng/autoDecoder 
- chrome-devtools-mcp：https://github.com/ChromeDevTools/chrome-devtools-mcp/ 

## 更新日志

### v2.2（2026-09-18）
从“扩展观测与结果验证”进一步升级为“可持续对抗、可证明成功、可直接交付”的完整闭环，面向通用浏览器逆向流程提供统一能力支撑。
- **运行时对抗能力升级**：统一观测反调试、完整性校验、环境属性、动态代码、多 Realm 与加载器行为；通过持久 Hook 和统一编排器支持探针叠加、外部替换后的重建以及安全卸载，提升复杂混淆环境下的持续取证能力。
- **JSVMP 与重度混淆分析升级**：增加保守的源码级属性 tap，建立插桩位置、运行时热点和调用结果之间的关联；结合基线/干预差分，形成静态分析与运行时行为的联合证据。
- **真实浏览器会话升级**：绑定 tab 与 document 身份，管理导航、断线、超时和暂停等会话生命周期；观测控制台清理、历史导航、存储访问和页面关闭等控制流信号，并支持可回滚的受控干预。
- **成功判定升级**：新增 action 级证据闭环，覆盖明文、最终请求体、最终路由、HTTP 状态和业务响应；建立服务状态、动作状态、请求状态和业务状态的分层验证模型，形成可追溯的成功判定。
- **传输与证据可靠性升级**：最终请求捕获统一覆盖 fetch 与 XMLHttpRequest；原始对象采用有界、循环引用安全的快照；兼容历史 JSRPC 外层字符串数据，提升 CryptoJS、JSEncrypt 等复杂对象和响应封装场景下的证据完整性。
- **JSRPC/Flask/Burp 交付升级**：覆盖完整 HTTP 报文和包装请求模式，校验 `/go` 端点规范化、`application/octet-stream` 封装、`Content-Length` 重建和通用字段变换；保持请求/响应数据包互斥选择，同时支持分别配置解密接口与加密接口、端口占用回退和可复制验证命令。

### v2.1 (2026-07-28)
- **证据驱动**：SHA-256 指纹关联、证据图构建、差分验证，从"可能对"变成"确认对"
- **扩展 Hook**：WebSocket/Request/TextEncoder/btoa/CryptoJS/JSEncrypt/sm2/sm3/sm4，覆盖更多加密场景
- **降级策略链**：5 级降级，不轻易放弃，模块内部加密也能处理
- **四层验证**：Schema + 静态 + 候选不变量 + 跨文件一致性
- **Token 优化**：SKILL.md 精简 84%，参考资料按需加载，初始加载总 token 约减少 95%
- **新增工具**：反爬分类、加密算法识别、Hook 模板库、环境补丁、AST 分析、隔离报告

### v2.0 (2026-05-31)
- **架构优化**：阶段流程从 Phase 0-9 精简为 Phase 0-8，消除冗余步骤，token 消耗减少约**40%**
- **全自动化**：JSRPC 自动发现/启动、Flask 自动启停、浏览器自动注入，**全程只需配置 Burp**
- **更强入口定位**：运行时 Hook 探针 + Webpack 模块解析 + 7 维度候选评分，提供更强大、更快速的入口定位能力，**对模型要求降低**
- **更稳定输出**：capability_boundary 显式声明不支持场景、runtime_health 健康检测、候选验证机制

### v1版本更新记录
- 2026-05-21: 引入 Phase 9 经验沉淀与对抗库演进
- 2026-04-10: 补强请求复现、参数入口定位、反检测验证能力
- 2026-03-19: 添加对抗 AI 识别为高风险操作的能力
- 2026-03-10: 重构为"主控文件 + 参考规则 + 生成器 + 校验器"架构
- 2026-02-11: 新增 11 个反调试补充技能
- 2026-02-03: 优化项目结构，支持 Claude/Codex/Trae 平台
