# 验收清单

本文档是该 Skill 最终的 Done 门禁。

## Done 标准

当输入完整时，只有以下文件全部存在，工作流才算完成：
- `analysis_result.json`
- generated JSRPC injection file
- generated Flask proxy file
- generated Burp autoDecoder document
- `artifacts/validation_report.json`
- `references/evolution_matrix.json`

## `analysis_result.json`
- 必须能被解析为 JSON。
- 必须满足 `references/output-contract.md` 中定义的契约。
- 必须包含每一个请求参数。
- 必须包含足够的运行时元数据，以便解析并调用入口函数。
- 必须包含诊断信息和残余风险说明。
- Phase 1-3 的证据必须能回溯到真实请求，而不是纯源码关键词搜索。

## JSRPC 校验
- 生成文件中包含配置好的 action 名。
- 生成文件中包含入口解析逻辑。
- 生成文件中的 sync 或 async 处理必须与 `analysis_result.json` 保持一致。
- 生成文件必须支持传统手工测试方式：`/go?...&param=111111`。
- 成功时必须直接返回字符串结果，而不是 `{ok, parameter, result}` 结构。
- 失败时必须返回可识别的字符串错误前缀，例如 `__JSRPC_ERROR__:`。

## Flask 校验
- 生成文件必须能在 Python 3 下解析。
- `GET /healthz` 必须存在。
- `POST <route>` 必须存在。
- 请求改写逻辑必须覆盖每一个目标参数。
- JSRPC endpoint、group 和 action 必须与 `analysis_result.json` 对齐。

## Burp 校验
- 文档必须包含：
  - 本地代理 URL
  - HTTP 方法
  - 表单字段 `dataBody` 和 `dataHeaders`
  - 返回契约
  - 分步验证流程
  - 排障说明

## 失败输出要求
- 校验报告必须包含：
  - `status`
  - `checks`
  - `failures`
  - `warnings`
  - `next_actions`
- 每一项失败检查都必须标明文件，以及缺失或非法的规则。

## Phase 9 经验库校验
- `references/evolution_matrix.json` 必须能被解析为 JSON。
- 必须保留历史 `domains` 和 `behavioral_features` 中与当前任务无关的记录。
- 当前任务结束后必须更新当前注册主域名对应的 action、route 或失败降级记录。
- 命中特征时必须维护 STE 结构：`strategic_principle`、`tactical_manual`、`applicable_scenarios`。
- 并发或异常中断不得导致 JSON 空文件、截断文件或历史记忆丢失。

## 残余风险说明

如果所有强制检查都通过，警告不会阻断 Done，但在相关情况下仍必须列出：
- 使用了反调试规则
- 运行时 bootstrap 仍依赖手工维护的浏览器状态
- 入口函数依赖启发式 resolver，而不是稳定的对象路径
- 为了调查而启用了最小环境 patch，但该 patch 未进入最终生成代码
