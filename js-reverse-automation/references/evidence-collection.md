# 证据收集规则

本文说明 JS 逆向自动化中的证据收集方法：网络捕获、软 Hook、源码定位和运行时 Hook 跟踪，并规定证据强度、记录方式与风险控制。

---

## 1. 网络捕获

### 适用场景

- 确认目标参数位于 URL、请求头、Cookie、JSON 请求体还是表单请求体。
- 页面动作触发多个相似请求，需要缩小到真正参与签名或加密的请求。
- 用户提供了 Optional Fetch Example，需要映射到真实浏览器请求。

### 证据优先级

1. 真实页面动作触发的网络记录。
2. 请求详情：方法、URL、请求头、请求体和响应。
3. 页面内观察代码输出：调用栈、序列化对象和函数参数。
4. 控制台日志与页面状态快照。

### 推荐流程

1. 打开目标页面并完成必要交互，确认请求确实发出。
2. 使用 chrome-devtools-mcp 的网络请求列表筛选候选请求。
3. 读取每个候选请求的详情，确认目标参数位置和请求体结构。
4. 请求较多时，按以下条件缩小范围：
   - 是否出现目标参数。
   - 请求触发时间是否接近用户动作。
   - 响应状态是否符合业务预期。
   - 请求体是否同时包含未加密明文和加密结果等相邻字段。
5. 锁定请求后立即记录：
   - 请求 URL。
   - HTTP 方法。
   - Content-Type。
   - 参数位置。
   - 关键请求头。
   - 触发动作。
6. 请求详情不足以定位源码时，再增加最小观察代码或最小 Hook。

### 成功标准

- 至少一个请求被明确标记为目标请求。
- 每个待分析参数的位置已知。
- 已记录足以支持后续源码定位的请求上下文。

### 失败信号

- 只能看到静态资源请求，看不到业务 API。
- 目标动作触发大量相似请求，无法区分签名参与者。
- 能看到请求，但无法确认参数经过哪一层序列化后出现。

### 处理策略

- 多请求竞争时只改变一个输入值，观察哪个请求字段同步变化。
- 序列化不透明时，对以下边界增加最小 Hook：
  - window.fetch
  - XMLHttpRequest.prototype.open
  - XMLHttpRequest.prototype.send
  - JSON.stringify
- 页面会刷新时，通过 evaluate_script 注入；需要在刷新前生效时，使用 navigate_page(initScript=...) 预注入。
- Hook 的目的只是记录“发送前最后一个可观察形态”，不能替代网络证据。

---

## 2. 软 Hook 规则

### 适用范围

- 网络证据已锁定目标请求，但仍缺少入口函数证据。
- 需要确认参数在某个函数调用前后是否发生变化。
- 需要确认返回值、this 绑定、异步行为或全局依赖。

### 最小 Hook 原则

- 先 Hook 通用边界，再 Hook 业务函数。
- 先记录后改写，默认不替换原函数。
- 每个 Hook 只增加一个观察点，避免多个 Hook 同时污染证据。
- 页面已加载时，优先使用 evaluate_script 注入。
- 页面将刷新或导航时，使用 navigate_page(initScript=...) 预注入。

### 推荐 Hook 顺序

1. window.fetch
2. XMLHttpRequest.prototype.open
3. XMLHttpRequest.prototype.send
4. JSON.stringify
5. 已明确匹配的业务函数
6. 必要时再补充 eval、Function 或 Promise 相关节点

### 每个 Hook 至少记录

- Hook 点路径。
- 匹配条件。
- 输入参数摘要。
- 返回值摘要。
- 调用栈摘要。
- 是否改变页面行为。
- 注入方式：evaluate_script 或 navigate_page(initScript=...)。

### 入口确认规则

业务函数 Hook 至少要证明以下一项：

- 明文输入与请求中的目标参数存在可验证映射。
- 函数返回值直接进入请求体、请求头或 Cookie。

只看到密码库内部调用、没有业务调用者上下文，不能认定为最终入口。

### 依赖提取规则

明确记录：

- this 绑定来源。
- 依赖的全局对象或闭包对象。
- 是否需要等待异步结果。
- 页面是否必须先完成启动流程。

这些信息最终写入 artifacts/phase3_dependencies.json 和 analysis_result.json。

### 风险控制

- 默认不要冻结大量原型。
- 不要为了方便观察而全局替换所有密码学 API。
- Hook 导致业务分支改变时，先回退到更小范围，再继续分析。

---

## 3. 源码定位

### 核心原则

- 先从请求详情、页面内调用栈和序列化节点回溯，再进行关键词搜索。
- 先找“参数最后一次发生变化的位置”，再找“最深层算法位置”。
- 只接受有证据支持的源码定位结果，不接受纯文本匹配结论。

### 定位优先级

1. 请求详情、页面内 Error().stack 或观察代码捕获的调用栈。
2. 发送前对象构造或序列化位置。
3. 与参数同名或相邻的源码片段。
4. 密码库调用位置。

### 推荐流程

1. 从目标请求开始，确认请求方法、请求体和相关脚本线索。
2. 在请求构造处加入最小观察代码：
   - 观察 fetch / XHR send。
   - 观察 JSON.stringify。
   - 在页面内输出 Error().stack。
3. 页面刷新或导航时：
   - 使用 navigate_page(initScript=...) 预注入。
   - 重新触发目标动作并记录序列化前对象。
4. 标记参数的三个关键位置：
   - 明文入口。
   - 处理或加密位置。
   - 发送前最终写入位置。
5. 只有其中至少两个位置被证据串联后，才能输出首选入口。

### 候选入口接受标准

- 能解释参数从明文到密文的变化。
- 能定位可调用函数或稳定解析器。
- 能解释 this 绑定、参数签名和必要依赖。

### 常见误判

- 只匹配到参数名，但变量只是中间副本。
- 只匹配到 md5、aes 或 sha，但它并不服务于目标请求。
- 只看到包装函数，没有继续确认真实执行点。

### 输出要求

- source_hint 尽量落到具体 bundle 位置或对象路径。
- evidence 至少包含以下一项：
  - 页面内调用栈。
  - Hook 捕获的输入参数和返回值。
  - 序列化前对象快照。
  - 参数值对照实验结果。

---

## 4. 运行时 Hook 跟踪

### 概述

运行时 Hook 使用预注入探针，在网络、密码学和序列化层捕获证据，是入口发现的重要证据源。

### 探针安装

生成：

~~~bash
python3 scripts/emit_runtime_hook_probe.py --output generated/runtime_hook_probe.js --params "target_param1,target_param2"
~~~

注入方式：

- 页面已加载时使用 evaluate_script。
- 页面会刷新或导航时使用 navigate_page(initScript=...)。

幂等性：

- 探针安装前检查 window.__JSRA_TRACE__，重复注入应安全地跳过。

### 探针捕获内容

探针在以下边界安装软 Hook，并将证据写入 window.__JSRA_TRACE__。

#### 4.1 网络请求（requests[]）

- Hook 点：window.fetch、XMLHttpRequest.prototype.open、XMLHttpRequest.prototype.send。
- 每条记录包括：
  - type：fetch 或 xhr。
  - url：请求 URL。
  - method：HTTP 方法。
  - headers：摘要后的请求头。
  - bodySnippet：截断后的请求体。
  - timestamp：Date.now()。
  - stack：通过 Error().stack 捕获的调用栈，最多 10 帧。

#### 4.2 密码学事件（crypto[]）

- Hook 点：crypto.subtle.digest、sign、encrypt、decrypt。
- 每条记录包括：
  - type：digest、sign、encrypt 或 decrypt。
  - algorithm：算法名称。
  - inputLen：输入字节数。
  - outputLen：Promise 完成后的输出字节数。
  - outputHex：摘要结果前 32 个十六进制字符，仅用于 digest。
  - timestamp：Date.now()。
  - stack：调用栈，最多 10 帧。

#### 4.3 序列化事件（serializers[]）

- Hook 点：FormData.append、FormData.set、URLSearchParams.append、URLSearchParams.set、URLSearchParams.toString、JSON.stringify。
- 每条记录包括：
  - type：序列化方法名。
  - name：字段名。
  - valueSnippet 或 resultSnippet：截断后的值。
  - keys：JSON.stringify 对象的键，最多 20 个。
  - timestamp：Date.now()。
  - stack：JSON.stringify 和 URLSearchParams.toString 的调用栈。

#### 4.4 选择性 JSON.stringify Hook

- 只有待序列化对象包含目标参数或敏感字段时才记录。
- 敏感字段包括 sign、token、enc、password、signature、hash、key、nonce、timestamp、ts、data、encrypt、decrypt。
- 这样可以避免无关序列化调用造成日志洪泛。

### 读取证据

导出全部证据：

~~~js
evaluate_script("window.__JSRA_TRACE__.dump()")
~~~

返回包含 requests、crypto、serializers、errors 的 JSON 字符串。

清空证据缓存：

~~~js
evaluate_script("window.__JSRA_TRACE__.clear()")
~~~

### 使用证据发现入口

1. 从 requests[].stack 中寻找加密或签名函数调用帧，这些帧指向业务调用者，而不仅是密码库。
2. 与序列化事件交叉比对：如果 serializers[] 显示 JSON.stringify 或 URLSearchParams.toString 处理了关注字段，调用栈可以定位请求体组装位置。
3. 将密码学算法和请求体对应：crypto[] 中的 digest 或 encrypt 事件，应与请求体中的密文长度和算法相匹配。
4. 从调用栈提取最外层业务函数，排除 fetch、XMLHttpRequest 和密码库内部函数，作为候选入口。

### 运行时跟踪的证据标准

- 高置信度：至少一条经过业务函数的 requests[] 调用栈，以及一条与目标参数相关的 crypto[] 或 serializers[] 事件。
- 中置信度：至少一条 bodySnippet 中出现目标参数的 requests[] 记录，即使调用栈未明确指向业务函数。
- 仅有密码库内部调用、没有业务调用者上下文，不能达到高置信度。

### 失败处理

| 现象 | 处理方式 |
|---|---|
| 探针注入失败（被反调试阻断） | 记录反调试现象，参阅反调试规则，降级到静态分析 |
| 触发目标动作后没有 requests[] | 确认动作确实执行，并检查探针是否注入到正确执行上下文 |
| crypto[] 为空但请求体包含密文 | 可能使用非 Subtle 密码库，使用 CryptoJS/JSEncrypt Hook 规则 |
| stack 全部匿名或已混淆 | 使用源码定位规则，将调用栈与 bundle 行号关联 |

### 风险提示

- 探针不能替代网络证据，只能补充网络证据。
- 探针使用软包装，不应替换原函数或破坏页面功能。
- Hook 造成计时变化时，先记录未启用 Hook 的基线，再记录启用后的观察结果。
- 探针不会自动跨页面导航持久化，页面刷新后需要通过 initScript 重新注入。

---

## 5. 跨场景证据标准

### 证据层级

1. 网络证据：请求 URL、方法、请求体、请求头和响应，强度最高。
2. 运行时 Hook 证据：调用栈、密码学事件和序列化事件，强度较高。
3. 源码证据：bundle 位置、对象路径和关键词匹配，仅作为辅助。

### 置信度要求

| 置信度 | 最低证据 |
|---|---|
| high | 网络证据 + 运行时/调用栈/模块证据，至少两类 |
| medium | 单一证据源（网络或运行时） |
| low | 仅有关键词搜索或源码模式 |

### 可计入证据的内容

- 运行时探针产生的 requests[]，且调用栈经过业务函数。
- 能将算法和输出长度与实际密文对应的 crypto[] 事件。
- 显示参数在请求发送前被序列化的 serializers[] 事件。
- evaluate_script 捕获并指向业务调用者的 Error().stack。
- 能将明文映射到密文的 Hook 输入/输出对。
- 只改变一个输入值后，能证明哪个请求字段随之变化的实验结果。

### 不可单独计入证据的内容

- 没有运行时关联的源码关键词匹配。
- 没有业务调用者上下文的密码库函数匹配。
- 存在于全局对象上、但目标动作期间从未被观察到调用的路径。
- 没有调用栈、Hook 或网络确认的疑似入口。

### 记录要求

每条证据必须包含：

- 来源类型：网络、Hook、调用栈、序列化、密码学或实验。
- 时间戳或序列号。
- 足以复现观察的上下文：URL、方法、Hook 点路径和调用栈。
- 观察发生时是否启用了补丁或 Hook。
