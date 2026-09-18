<h1 align="center">js-reverse-automation--skill</h1>
<p align="center">
  <code>前端JS逆向全流程自动化Skill</code>
</p>
<div align="center">

<p align="center">
  <a href="https://github.com/Fausto-404/js-reverse-automation--skill-test/releases">
    <img src="https://img.shields.io/github/v/release/Fausto-404/js-reverse-automation--skill-test?style=flat-square&label=release&color=blue&cacheSeconds=3600" alt="Release">
  </a>

  <a href="https://github.com/Fausto-404/js-reverse-automation--skill-test/stargazers">
    <img src="https://img.shields.io/github/stars/Fausto-404/js-reverse-automation--skill-test?style=flat-square&label=stars&color=brightgreen&cacheSeconds=3600" alt="GitHub Stars">
  </a>

  <a href="https://github.com/Fausto-404/js-reverse-automation--skill-test/network/members">
    <img src="https://img.shields.io/github/forks/Fausto-404/js-reverse-automation--skill-test?style=flat-square&label=forks&color=orange&cacheSeconds=3600" alt="GitHub Forks">
  </a>

  <a href="https://github.com/Fausto-404/js-reverse-automation--skill-test/releases">
    <img src="https://img.shields.io/github/downloads/Fausto-404/js-reverse-automation--skill-test/total?style=flat-square&label=downloads&color=success&cacheSeconds=3600" alt="Downloads">
  </a>
</p>

</div>

<p align="center">
  <strong>结合chrome-devtools-mcp的能力并加上Skill的规范，实现JSRPC+Flask+autoDecoder方案的前端JS逆向自动化分析，提升JS逆向的效率</strong>
</p>

<p align="center">
</p>

## 更新日志

### v2.2.1（2026-09-18）

本版本包含 v2.2.0 的对抗运行时能力，并继续强化真实浏览器联调、证据可靠性和 JSRPC/Flask/Burp 交付链。提升面向通用逆向流程，不针对单一靶题写死。

#### v2.2.0 能力基线

- **对抗运行时**：观察反调试、完整性校验、环境属性、动态代码和多 Realm/加载器行为，并通过持久 Hook 保持运行时观测能力。
- **JSVMP 运行时分析**：提供保守的源码级属性 tap，输出插桩位置与运行时热点，辅助处理虚拟机保护和重度混淆代码。
- **状态差分**：建立基线与干预后的差分报告，区分新增有效证据、错误增长和真正的业务成功。
- **组合稳定性**：对抗探针与加密运行时探针使用统一 Hook 编排，支持叠加、外部替换后的重建以及安全卸载。
- **证据可靠性**：原始捕获使用有界、循环引用安全的快照，避免 CryptoJS、JSEncrypt 等对象导致导出失败。
- **传输覆盖**：统一覆盖 fetch 与 XMLHttpRequest 的最终请求捕获，并清理成功调用后的超时计时器。

#### v2.2.1 能力增强

- **浏览器会话契约**：绑定 tab 与 document 身份，将导航、断线、超时和暂停后的旧引用标记为失效，避免把端口可达或旧页面日志误判为成功。
- **控制流观测与受控干预**：增加控制台清理、历史导航、存储访问和页面关闭等干扰信号的观测；仅在明确的干预模式下阻断指定历史导航或关闭动作，并支持分层安装与回滚卸载。
- **真实动作证据验收**：按 action 验证明文、最终请求体、最终路由、HTTP 状态和业务响应，只有证据链完整时才报告可交付成功。
- **JSRPC 结果兼容**：兼容外层 JSRPC 响应中以 JSON 字符串承载的历史 `data` 结构，避免请求已成功但证据解析失败。
- **交付契约回归**：增加对 `/go` 端点规范化、完整 HTTP 报文、`application/octet-stream` 外层封装、`Content-Length` 重建、包装模式和通用字段变换的回归检查。
- **Burp/Flask 联调稳定性**：强化完整请求报文和包装请求两种模式的输出约束，保持请求数据包与响应数据包互斥选择，同时允许分别配置解密接口和加密接口，并支持端口占用时的可验证回退。
- **失败状态收敛**：区分“服务可连接”“动作已触发”“请求链成功”和“业务证据通过”，避免仅凭 JSRPC 注册、HTTP 200 或端口监听给出过度结论。

本版本的最终交付格式保持稳定：继续输出明文、密文/签名、JSRPC、Flask、Burp autoDecoder 配置和可复制验证命令；对抗观测作为证据补充，不改变交付接口。

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
- 基于 MCP 连接真实浏览器，触发并跟踪js加密/签名链路
- 运行时 Hook 探针：自动捕获 fetch/XHR/crypto/WebSocket/CryptoJS/JSEncrypt/sm2/sm3/sm4 调用栈和参数流转
- Webpack 模块解析：自动发现 `__webpack_require__`，搜索 module cache 中的加密函数
- 候选评分系统：8 维度评分 + 真实样本验证，降低误判
- 差分验证：主动调用候选函数，比对请求字段指纹，确保准确性
- 证据图构建：SHA-256 指纹关联 producer→consumer，追踪数据流
- 全自动服务管理：JSRPC 服务器自动发现/启动，Flask 代理自动启停
- 一键注入：代码生成 + 浏览器注入 + 注册验证全自动
- Burp 无缝对接：生成 autoDecoder 配置文档，支持端到端联调
- 完整验证交付：JSRPC 结果必须包含明文、最终请求 route、密文/签名、服务端响应和可复制验证命令；对抗信息作为补充证据展示
- 对抗运行时探针：反调试、反 Hook、动态代码、环境属性、响应链和加载器事件
- 源码级保守插桩：针对 JSVMP/混淆代码的属性读取 tap 与热点分析
- 持久 Hook 与差分：检测 Hook 丢失、恢复观测能力，并比较基线/干预行为
- 浏览器会话契约：绑定 tab/document 身份，区分断线、超时、暂停、导航后的未知状态，避免只凭端口或注册日志误报成功
- 控制流观测：按需记录控制台清理、历史导航、存储访问和关闭页面等干扰信号，并支持可回滚的受控干预
- action 证据验收：使用 `validate_browser_evidence.py` 检查明文、最终请求体、路由、HTTP 状态和业务响应是否齐全

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

## 能力概览

- 证据驱动的运行时 Hook、请求字段关联和候选差分验证
- 反调试、完整性、环境属性、动态代码、多 Realm 和加载器观测
- JSVMP 场景的保守源码属性 tap 与运行时热点关联
- JSRPC、Flask 和 Burp autoDecoder 的完整交付链路
- 端口占用自动回退、状态文件身份校验和失败关闭保护
