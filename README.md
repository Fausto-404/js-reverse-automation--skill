<h1 align="center">js-reverse-automation--skill </h1>
<p align="center">
  <code>前端JS逆向全流程自动化Skills</code> 
</p>
<div align="center">

<p align="center">
  <a href="https://github.com/Fausto-404/js-reverse-automation--skill/releases">
    <img src="https://img.shields.io/github/v/release/Fausto-404/js-reverse-automation--skill?style=flat-square&label=release&color=blue&cacheSeconds=3600" alt="Release">
  </a>

  <a href="https://github.com/Fausto-404/js-reverse-automation--skill/stargazers">
    <img src="https://img.shields.io/github/stars/Fausto-404/js-reverse-automation--skill?style=flat-square&label=stars&color=brightgreen&cacheSeconds=3600" alt="GitHub Stars">
  </a>

  <a href="https://github.com/Fausto-404/js-reverse-automation--skill/network/members">
    <img src="https://img.shields.io/github/forks/Fausto-404/js-reverse-automation--skill?style=flat-square&label=forks&color=orange&cacheSeconds=3600" alt="GitHub Forks">
  </a>

  <a href="https://github.com/Fausto-404/js-reverse-automation--skill/releases">
    <img src="https://img.shields.io/github/downloads/Fausto-404/js-reverse-automation--skill/total?style=flat-square&label=downloads&color=success&cacheSeconds=3600" alt="Downloads">
  </a>
</p>

</div>

<p align="center">
  <strong>结合chrome-devtools-mcp的能力并加上Skill的规范，实现JSRPC+Flask+autoDecoder方案的前端JS逆向自动化分析，提升JS逆向的效率</strong>
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
- 基于 MCP 连接真实浏览器，触发并跟踪js加密/签名链路
- 运行时 Hook 探针：自动捕获 fetch/XHR/crypto 调用栈和参数流转
- Webpack 模块解析：自动发现 `__webpack_require__`，搜索 module cache 中的加密函数
- 候选评分系统：7 维度评分 + 真实样本验证，降低误判
- 全自动服务管理：JSRPC 服务器自动发现/启动，Flask 代理自动启停
- 一键注入：代码生成 + 浏览器注入 + 注册验证全自动
- Burp 无缝对接：生成 autoDecoder 配置文档，支持端到端联调

## 项目结构
```latex
js-reverse-automation/
├── SKILL.md                          # 主控文件
├── references/                       # 参考规范与知识库
│   ├── output-contract.md            # 输入输出契约
│   ├── workflow-recon.md             # 阶段流程说明
│   ├── evidence-collection.md        # 取证方法（Hook/源码/网络）
│   ├── advanced-entrypoints.md       # 复杂入口场景（Webpack/异步/WASM）
│   ├── antidebug-patterns.md         # 反调试模式与 Patch
│   ├── capability-boundaries.md      # 能力边界说明
│   └── evolution_matrix.json         # 跨任务经验记忆库
├── scripts/                          # 自动化工具脚本
│   ├── check_inputs.py               # 输入校验
│   ├── emit_runtime_hook_probe.py    # 运行时 Hook 探针生成
│   ├── emit_module_probe.py          # Webpack 模块探针生成
│   ├── detect_encryption.py          # 加密函数候选评分
│   ├── emit_jsrpc_stub.py            # JSRPC 注入代码生成
│   ├── emit_flask_proxy.py           # Flask 代理生成
│   ├── emit_burp_doc.py              # Burp 文档生成
│   ├── manage_services.py            # 服务管理（JSRPC/Flask 启停）
│   ├── validate_artifacts.py         # 全链路校验
│   └── JsEnv_Dev.js                  # Hlclient WebSocket 客户端库
├── generated/                        # AI 运行生成的中间代码/配置产物
│   ├── jsrpc_inject.js               # JSRPC 浏览器端注入代码
│   ├── flask_proxy.py                # Flask 本地代理服务
│   ├── burp-autodecoder.md           # Burp autoDecoder 配置文档
│   └── runtime_hook_probe.js         # 运行时 Hook 探针脚本
└── artifacts/                        # 运行时的动态状态与报告产物
    ├── phase0_input.json             # 校验后的输入
    ├── encryption_candidates.json    # 加密函数候选评分
    ├── validation_report.json        # 全链路校验报告
    ├── jsrpc_status.json             # JSRPC 服务状态
    └── flask_status.json             # Flask 服务状态
```

## 使用示意
1. 安装 MCP 服务

```bash
# Claude Code
claude mcp add chrome-devtools -- npx -y chrome-devtools-mcp@latest
# Codex
codex mcp add chrome-devtools -- npx -y chrome-devtools-mcp@latest
# Gemini
gemini mcp add chrome-devtools npx -y chrome-devtools-mcp@latest
```
2. 将 `js-reverse-automation` 目录放入 Skill 目录，然后输入：

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
2. 按照模版编写提示词并输入给claude【本次使用的是去除安全限制的claude + mimo-v2.5验证，旨在验证降低模型要求，skills实现效果不变】
<img width="1810" height="1264" alt="image" src="https://github.com/user-attachments/assets/7703c06a-0f42-4c8d-b2c9-6d18172c1194" />
3. 等待输出结果
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

案例后续会更新到案例库，敬请期待....

## 引用工具
- JsRpc：https://github.com/jxhczhl/JsRpc 
- autoDecoder：https://github.com/f0ng/autoDecoder 
- chrome-devtools-mcp：https://github.com/ChromeDevTools/chrome-devtools-mcp/ 

## 更新日志
### v1版本更新记录
- 2026-05-21: 引入 Phase 9 经验沉淀与对抗库演进
- 2026-04-10: 补强请求复现、参数入口定位、反检测验证能力
- 2026-03-19: 添加对抗 AI 识别为高风险操作的能力
- 2026-03-10: 重构为"主控文件 + 参考规则 + 生成器 + 校验器"架构
- 2026-02-11: 新增 11 个反调试补充技能
- 2026-02-03: 优化项目结构，支持 Claude/Codex/Trae 平台
### v2.0 (2026-05-31)
- **架构优化**：阶段流程从 Phase 0-9 精简为 Phase 0-8，消除冗余步骤，token 消耗减少约**40%**
- **全自动化**：JSRPC 自动发现/启动、Flask 自动启停、浏览器自动注入，**全程只需配置 Burp**
- **更强入口定位**：运行时 Hook 探针 + Webpack 模块解析 + 7 维度候选评分，提供更强大、更快速的入口定位能力，**对模型要求降低**
- **更稳定输出**：capability_boundary 显式声明不支持场景、runtime_health 健康检测、候选验证机制
