# 首发地址
【AI赋能】MCP+Skill能力下的前端JS逆向自动化落地

作者：Fausto

https://xz.aliyun.com/news/91527

文章转载自 先知社区
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
## 使用示意
这边演示使用的是codex5.3（其他平台同理）

1、下载skills放置在codex的skills目录中，mac端的路径为`/Users/用户名/.codex/skills/`
<img width="822" height="290" alt="image" src="https://github.com/user-attachments/assets/400d26de-8571-412a-bf5c-894ba8041fbd" />

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
1、目标网址（完整 URL）： 
2、需要分析的加密参数名（如 sign / enc / token）： 
3、可复现请求示例（优先给 fetch/抓包原始请求）： 
4、环境限制（浏览器版本、是否需要代理/插件、是否允许注入）：
```

<img width="1546" height="410" alt="image" src="https://github.com/user-attachments/assets/bdc49469-5a09-4ac4-871a-02cdd78d1bdb" />
8、等待程序运行完成即可
<img width="1494" height="1258" alt="image" src="https://github.com/user-attachments/assets/f50dfe64-8690-42e9-8230-25056b5a84bf" />

## 效果检验

1、启动JSRPC
<img width="2204" height="1358" alt="image" src="https://github.com/user-attachments/assets/b7927337-f959-4c70-8c13-f477d491a784" />

2、在浏览器开发者工具的Console中，执行JSRpc项目中的 JsEnv_Dev.js文件内容。
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

