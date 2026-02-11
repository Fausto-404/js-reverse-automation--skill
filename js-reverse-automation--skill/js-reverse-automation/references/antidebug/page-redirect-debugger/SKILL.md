---
name: js-reverse-automation-page-redirect-debugger
description: 页面跳转 JS 代码定位通杀方案：在跳转前触发 debugger 以定位调用源。仅在确认跳转定位需求时启用。
---

# 页面跳转JS代码定位通杀方案

用于在页面跳转前触发 `debugger`，定位跳转触发源。

## 先读这些信息
- 仅在确认存在强制跳转或需要定位跳转代码时启用。
- 会改变页面正常导航行为，定位完成后应关闭。

## 需要收集的输入
- 是否需要 onbeforeunload 断点定位跳转来源

<label>启用 onbeforeunload 断点：</label>
<input type="text" placeholder="yes / no" />

## 工作流程
1) 注册 `onbeforeunload`，在触发时断点定位代码。

## 产出
- 可直接注入的阻断片段：

```js
(() => {
  'use strict';

  window.onbeforeunload = () => {
    debugger;
    return false;
  };
})();
```

- 最终输出必须注明：`已启用技能: 页面跳转JS代码定位通杀方案`

## 交付前检查
- onbeforeunload 是否能定位调用栈
- 正常导航行为是否按预期恢复（调试结束后关闭）
