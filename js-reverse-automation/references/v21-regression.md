# v2.1 回归对照（版本号保持 2.2.0）

本对照在本地 `encrypt-labs` 混淆入口 `/` 上执行，输入为 `admin / probe-wrong`，用于触发加密请求但避免跳转成功页。

| 能力 | v2.1 | 当前 2.2.0 | 结论 |
|---|---:|---:|---|
| AES 请求触发 | 通过 | 通过 | 不回退 |
| CryptoJS AES 定位 | 通过 | 通过 | 不回退 |
| 网络字段关联 | 通过 | 通过 | 不回退 |
| `captureRaw` 导出 | 循环引用失败 | 安全快照可 JSON 导出 | 提升 |
| 对抗探针 | 无 | 环境/动态代码/完整性/Realm/Hook 健康 | 新增 |
| 对抗探针 + 加密探针叠加 | 不适用 | 无丢失、无重建错误 | 新增且稳定 |
| 外部重写 Hook 后恢复 | 无组合重建 | `patch.reconciled` 后恢复 | 提升 |

关键实测结果：

- v2.1 `dump()` 在 CryptoJS 原始对象上报 `Converting circular structure to JSON`。
- 当前 2.2.0 同时挂载两个探针时，AES 仍产生 `network.fetch`、`network.field` 和 `CryptoJS.AES.encrypt` 证据。
- 当前组合测试 `patch.lost=0`、`patch.reconcile_error=0`、`runtime_dump_ok=true`。
- 主动替换 `window.fetch` 后，当前版本产生一次 `patch.reconciled`，并恢复组合 Hook。

该对照证明的是混淆代码分析、证据导出和探针组合能力；不等同于验证码、WebAuthn、设备证明或跨域 Realm 已被绕过。
