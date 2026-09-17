# 对抗运行时能力

本模块服务于已授权目标的动态分析，目标是增加可观察证据和入口存活能力，不承诺绕过验证码、WebAuthn、设备证明或跨域隔离。

## 能力顺序

1. `observe`：记录反调试、反 Hook、环境属性、动态代码、加载器和 Realm 信号。
2. `intervene`：只针对已观察到的动态 `debugger` 构造做最小干预。
3. 源码 tap：对明确选择的简单属性读取做保守插桩，先验证行为再扩大范围。
4. 差分：比较原始与干预结果；事件增加不是业务成功，必须继续核对目标请求和业务状态。

## 多探针组合

对抗探针和运行时加密探针可以同时注入。生成脚本会共享
`window.__JSRA_HOOK_REGISTRY__`，对同一 `fetch`、XHR 或 WebCrypto 方法按层组合，避免
后注入的探针覆盖前一个探针。外部代码重新赋值时，持久探针会记录
`patch.reconciled` 并重建组合链；`patch.reconcile_error` 才表示真正的重建失败。

运行时探针的 `captureRaw` 使用有界、循环引用安全的快照。需要稳定落盘时优先使用默认
预览模式；开启原始捕获也必须通过 `dump()` 或 JSON Schema 验证后再进入差分流程。

## 生成与读取

```bash
python3 scripts/emit_adversarial_runtime_probe.py \
  --output generated/adversarial_runtime_probe.js \
  --mode observe --properties "navigator.webdriver,navigator.userAgent,document.cookie"
```

完整性方法默认采用首段全量、后续采样和每方法预算，避免 `Object.getPrototypeOf`
等高频 API 挤掉真正的加密/网络证据。可按目标特征调整：

```bash
python3 scripts/emit_adversarial_runtime_probe.py \
  --output generated/adversarial_runtime_probe.js \
  --integrity-event-budget 256 \
  --integrity-sample-every 64 \
  --integrity-burst 16
```

被采样抑制的调用会记录在 `state.suppressed` 和
`state.suppressedByPath`，不计入 `dropped`；`dropped > 0` 仍表示事件环发生了真正丢弃。

页面中：

```js
window.__JSRA_ADVERSARIAL__.export()
window.__JSRA_ADVERSARIAL__.clear()
window.__JSRA_ADVERSARIAL__.uninstall()
```

## 证据类型

| 类型 | 用途 |
|---|---|
| `integrity.*` | 函数、原型或属性描述符完整性检查 |
| `dynamic.*` | eval/Function 动态代码 |
| `environment.*` | navigator、screen、document 等属性访问 |
| `realm.*` | iframe、Worker、SharedWorker 创建 |
| `loader.*` | script、WASM 等动态加载 |
| `patch.*` | 补丁安装、丢失、重挂载和恢复 |
| `intervention.*` | 发生过的明确干预 |

## 源码级保守插桩

```bash
node scripts/source_instrumentor.js \
  --input bundle.js --output generated/bundle.tap.js \
  --objects navigator,document,screen \
  --properties webdriver,userAgent,cookie
```

默认只改写简单的 member read，并跳过字符串、注释、赋值和方法调用。它不是通用 AST 等价变换；插桩后必须与原始脚本做异常、请求和关键输出对照。
