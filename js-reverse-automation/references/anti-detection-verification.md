# 反检测验证规则

本规则只解决一个问题：目标站点的反调试、环境检测或 console 干扰，是否真的阻断了 Phase 1-3 的证据链。

## 基本原则
- 先验证，再 patch。
- 只做最小 patch。
- patch 的目标是恢复观测能力或解除链路阻断，不是重写页面环境。

## 验证顺序
1. 记录未 patch 时的原始现象。
2. 判断问题类型：
   - `debugger` / 动态代码构造
   - console 清理或日志抑制
   - 时间差或 Promise 时序
   - viewport / webdriver / UA / DevTools 检测
   - 跳转、关闭页面、history 干扰
3. 只选择一条最小规则进行验证。
4. 比较 patch 前后差异：
   - 请求是否恢复
   - Hook 是否开始产生日志
   - 调用栈是否变得可见
   - 页面是否引入新异常

## 接受条件
- patch 之后新增了可用于 Phase 2-3 的明确证据。
- 能说明 patch 的影响面和残余风险。
- patch 没有改变最终需要生成的 JSRPC / Flask / Burp 代码形态。

## 禁止行为
- 未验证就同时启用多条反调试规则。
- 为了提高“看起来能跑”的概率，广泛伪造环境。
- 把仅用于调试的 patch 误写成最终生成产物的依赖。

## 与精确规则的关系
- `debugger` 或动态构造问题：读取 `references/antidebug/debugger-loop.md`
- console 干扰：读取 `references/antidebug/console-detect.md`
- 定时与异步时序：读取 `references/antidebug/timer-check.md`
- 环境检测：读取 `references/antidebug/env-detect.md`
- 导航或代理阻断：读取 `references/antidebug/proxy-guard.md`
- 动态包装与 resolver：读取 `references/antidebug/dynamic-alias.md`
