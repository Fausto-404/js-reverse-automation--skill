# js-reverse-automation--skill
结合chrome-devtools-mcp的能力并加上Skill的规范，实现JSRPC+Flask+autoDecoder方案的前端JS逆向自动化分析，提升JS逆向的效率

## 适用场景

- 需要快速落地前端签名/加密参数逆向
- 需要将js逆向逻辑封装为可复用的代码
- 需要与 Burp 配合进行抓包、改包

## 流程设计思路
针对js逆向中常用的远程调用法进行js逆向（如JSRPC+Mitmproxy、JSRPC+Flask等）中，初始配置阶段中面对的定位加密函数、编写注册代码、编写python代码等繁琐操作，通过引入AI的MCP和Skill技术进行赋能，让AI自动完成函数发现与注册代码生成，最终实现从“半自动”到“高自动”的跨越，人员全程只需下方指令，并最终配置一下burp即可完成JS逆向的全流程。
<img width="2064" height="1108" alt="image" src="https://github.com/user-attachments/assets/fc13f276-f667-486a-8506-221c0c55507e" />

## 核心能力
- 基于 MCP 连接真实浏览器，触发并跟踪js加密/签名链路
- 自动定位 `sign / enc / token` 等关键参数生成入口
- 自动生成 JSRPC 注入与注册代码
- 自动生成 Python Flask 代理代码
- 输出 Burp `autoDecoder` 对接说明，支持端到端联调
- 支持AntiDebug_Breaker的11项反调试能力

## 项目结构
```latex
js-reverse-automation--skill/
├── README.md # 项目说明、使用方式、更新说明和结构说明。
├── SKILL.md # Skill 主控文件。只负责定义任务如何被触发、必须输入什么、流程怎么分阶段、输出和验收怎么要求。
├── agents/
│   └── openai.yaml # Skill 的 agent 入口配置。负责定义默认提示词、默认输入格式和执行约束。
├── artifacts/ # 运行期目录，用来承接流程中间产物和最终校验报告。预期会出现的文件如下：
│   ├── artifacts/phase0_input.json # 规范化后的输入
│   ├── artifacts/phase1_trace.json # 浏览器链路复现结果
│   ├── artifacts/phase2_entrypoints.json # 参数入口识别结果
│   ├── artifacts/phase3_dependencies.json # 依赖、上下文和调用方式提取结果
│   └── artifacts/validation_report.json # 最终校验报告
├── references/
│   ├── references/workflow-recon.md # 阶段流程说明书。
│   ├── references/output-contract.md # 输入输出契约说明书。
│   ├── references/failure-recovery.md # 失败恢复和诊断格式说明书。
│   ├── references/validation-checklist.md # 验收标准说明书。
│   └── references/antidebug/
│       ├── references/antidebug/debugger-loop.md # 处理无限 debugger、eval、Function 类问题。
│       ├── references/antidebug/console-detect.md # 处理控制台检测、日志篡改、清屏等问题。
│       ├── references/antidebug/timer-check.md # 处理时间差、性能计时、Promise 时序检测。
│       ├── references/antidebug/env-detect.md # 处理窗口大小、webdriver、UA、DevTools 检测等环境识别问题。
│       ├── references/antidebug/proxy-guard.md # 处理跳转、关闭页面、history、代理拦截等链路阻断问题。
│       └── references/antidebug/dynamic-alias.md # 处理动态别名、wrapper、resolver 型入口和不稳定路径。
└── scripts/
    ├── scripts/check_inputs.py # 输入校验器。
    ├── scripts/emit_analysis_result.py # 统一分析产物生成器。
    ├── scripts/emit_jsrpc_stub.py # JSRPC 代码生成器。
    ├── scripts/emit_flask_proxy.py # Flask 代理生成器。
    ├── scripts/emit_burp_doc.py # Burp autoDecoder 文档生成器。
    └── scripts/validate_artifacts.py # 全链路校验器。
```

## 使用示意
这边演示使用的是codex5.3（其他平台同理）

1、下载skills放置在codex的skills目录中，mac端的路径为`/Users/用户名/.codex/skills/`
<img width="880" height="296" alt="image" src="https://github.com/user-attachments/assets/0740b150-1508-46f1-bd76-2c6c9afa3bca" />


2、将chrome-devtools-mcp服务写进 Codex 的配置

 ```
 codex mcp add chrome-devtools -- npx -y chrome-devtools-mcp@latest
 ```
<img width="2464" height="216" alt="image" src="https://github.com/user-attachments/assets/0a3bd8c8-9029-4d8c-9f50-f91fb5ac4e4e" />

3、修改 Codex 的配置文件MAC的在`~/.codex/config.toml`，添加如下字段

```
[mcp_servers.chrome-devtools]
command = "npx"
args = ["-y", "chrome-devtools-mcp@latest"]
```

<img width="1848" height="892" alt="image" src="https://github.com/user-attachments/assets/b2f8a0a9-2ab1-44a1-baf6-5b57d20076b5" />

4、检测是否生效
<img width="2524" height="722" alt="image" src="https://github.com/user-attachments/assets/0dfd71ad-7b03-4eb3-a99a-8c11990dcf72" />

5、启动mcp服务，当看到打开浏览器后MCP服务就配置好了。

```
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --remote-debugging-address=0.0.0.0
```

<img width="2374" height="996" alt="image" src="https://github.com/user-attachments/assets/7a2336ee-1d7a-4ead-99c3-9faa00bc18bc" />
6、在codex客户端中使用该skills
<img width="2126" height="1548" alt="image" src="https://github.com/user-attachments/assets/5b63f167-e2c2-4686-b28f-3558f18f6012" />
7、输入所需要的信息

```
    Target URL: 
    Parameters To Analyze: 
    Environment Constraints: 
    Optional Fetch Example:
```
<img width="1546" height="876" alt="image" src="https://github.com/user-attachments/assets/a7359fdb-949c-40da-9c63-ea1e47b4be32" />

8、等待程序运行完成即可
<img width="1736" height="1016" alt="image" src="https://github.com/user-attachments/assets/76874d70-06c7-4a42-8cdf-de64e75e9c49" />


## 效果检验

1、启动JSRPC
<img width="1354" height="354" alt="image" src="https://github.com/user-attachments/assets/2be18d21-18b8-4594-b1ff-25e9126e5348" />



2、在浏览器开发者工具的Console中，执行`js-reverse-automation/scripts/JsEnv_Dev.js`文件中内容。
<img width="1980" height="1332" alt="image" src="https://github.com/user-attachments/assets/d2d7a299-f354-459c-b624-9d7d95abe130" />

3、在控制台注入AI生成的jsrpc_inject_hr_ncu_password.js。

<img width="1746" height="1320" alt="image" src="https://github.com/user-attachments/assets/b00c2261-ee26-4b88-a408-e0faaba84079" />

4、测试jsrpc调用函数是否正常，可以看到是没问题的。

```
http://127.0.0.1:12080/go?group=fausto&action=generate_password_md5&param=111111
```

<img width="2402" height="1056" alt="image" src="https://github.com/user-attachments/assets/5da1563a-84d7-4d6f-b83e-81106bed90a5" />

5、运行flask_proxy_hr_ncu.py

<img width="1744" height="1322" alt="image" src="https://github.com/user-attachments/assets/9b70a477-2b12-464d-8450-822320556c95" />

6、测试Flask是否可以正常加密，可以看到也是没问题的。

```
curl -X POST http://127.0.0.1:8888/encode \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "dataBody=username=111111&password=111111&code=1234&role=000002"
```

<img width="2508" height="1092" alt="image" src="https://github.com/user-attachments/assets/a9001881-b303-4c6c-a4bf-03f32576e44b" />

7、最后根据Burp autoDecoder 配置说明配置burp的autoDecoder插件，也成功加密了参数，整体成功运行完成
<img width="2382" height="1314" alt="image" src="https://github.com/user-attachments/assets/f3af2dd7-fe79-424a-be12-cea763c33e16" />

## 引用工具
- JsRpc：https://github.com/jxhczhl/JsRpc 
- autoDecoder：https://github.com/f0ng/autoDecoder 
- chrome-devtools-mcp：https://github.com/ChromeDevTools/chrome-devtools-mcp/ 
- AntiDebug：https://github.com/0xsdeo/AntiDebug_Breaker
## 更新日志

### 2026-02-03
- 优化项目结构，支持直接导入 Claude、Codex、Trae 等支持 Skills 的平台（`agents/` 目录可按需调整）。

### 2026-02-11
- 新增 11 个反调试补充技能，完善对复杂目标的反调试对抗能力。

### 2026-03-10
+ 将 Skill 重构为“主控文件 + 参考规则 + 生成器 + 校验器 + 中间产物”架构，**输出质量更稳定、更高可用**
+ 新增统一中间产物 `analysis_result.json`
+ 新增输入校验器、分析产物生成器、JSRPC 生成器、Flask 生成器、Burp 文档生成器、统一校验器
+ 新增流程文档、输出契约、失败恢复、验收清单
+ 将 `references/antidebug` 从嵌套子 Skill 重构为参考规则集合
+ 明确 `artifacts/` 作为阶段产物和校验报告目录
