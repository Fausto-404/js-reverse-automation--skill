# 实操请参考先知社区原文链接
https://xz.aliyun.com/news/91527
# js-reverse-automation--skill
结合chrome-devtools-mcp的能力并加上Skill的规范，实现JSRPC+Flask+autoDecoder方案的前端JS逆向自动化分析，提升JS逆向的效率
# 流程设计
针对远程调用法进行js逆向（如JSRPC+Mitmproxy、JSRPC+Flask等）中，初始配置阶段中面对的定位加密函数、编写注册代码、编写python代码等繁琐操作，通过引入AI的MCP和Skill技术进行赋能，让AI自动完成函数发现与注册代码生成，最终实现从“半自动”到“高自动”的跨越，人员全程只需下方指令，并最终配置一下burp即可完成JS逆向的全流程。
<img width="2064" height="1108" alt="image" src="https://github.com/user-attachments/assets/fc13f276-f667-486a-8506-221c0c55507e" />

# 20260203更新
优化该项目的结构，可以直接导入Claude、Codex、trae等支持Skills的模型和平台（按需修改agent下的文件）

# 20260211更新
新增 11 个补充技能目录，覆盖 AntiDebug_Breaker 的核心反调试与加密观察能力：
- Bypass Debugger
- hook log
- Hook table
- hook clear
- hook close
- hook history
- Fixed window size
- Hook Promise
- 页面跳转JS代码定位通杀方案
- Hook CryptoJS
- Hook JSEncrypt RSA

识别到需要的反调试技能可使用https://github.com/0xsdeo/AntiDebug_Breaker插件进行反调试对抗
