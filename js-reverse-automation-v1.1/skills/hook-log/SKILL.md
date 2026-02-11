---
name: js-reverse-automation-hook-log
description: 防止 js 重写 console.log/trace/groupCollapsed 等方法或替换 console 对象，以保持可观测性。仅在确认 console 被篡改时启用。
---

# hook log

用于保护 `console` 关键方法不被重写，防止站点通过覆盖 `console.log/trace` 等手段隐藏调试输出。

## 先读这些信息
- 仅在确认 console 被篡改或清空输出时启用。
- 该方法会影响全局 `console` 可写性，可能被反检测脚本注意到。
- 默认不影响业务逻辑，只保护调试观测能力。

## 需要收集的输入
- 被篡改的 console 方法列表（如 `log`, `trace`）
- 是否允许拦截 `window.console` 重新赋值

<label>被篡改的方法（可选）：</label>
<input type="text" placeholder="log, trace, groupCollapsed, groupEnd" />

<label>是否拦截 console 重新赋值：</label>
<input type="text" placeholder="yes / no" />

## 工作流程
1) 以最小粒度保护：先保护 `log/trace/groupCollapsed/groupEnd`。
2) 使用 `Proxy` 拦截 set 操作，阻止覆盖。
3) 使用 `Object.defineProperty` 保护 `window.console` 不被替换。
4) 若仍被覆盖，回退为冻结 `console`（更强但更易被检测）。

## 产出
- 可直接注入的保护片段：

```js
(() => {
  'use strict';

  const readonlyProps = ['log', 'trace', 'groupCollapsed', 'groupEnd'];
  const readonlyConsole = new Proxy(console, {
    set(t, k, v, r) {
      if (readonlyProps.includes(k)) {
        console.groupCollapsed(`%cBlocked overwrite: console.${String(k)}`, 'color: #ff6348;', v);
        console.trace();
        console.groupEnd();
        return true;
      }
      return Reflect.set(t, k, v, r);
    }
  });

  Object.defineProperty(window, 'console', {
    configurable: true,
    enumerable: false,
    get() {
      return readonlyConsole;
    },
    set(v) {
      console.groupCollapsed('%cBlocked overwrite: window.console', 'color: #ff6348;', v);
      console.trace();
      console.groupEnd();
    }
  });
})();
```

- 最终输出必须注明：`已启用技能: hook log`

## 交付前检查
- 站点是否还能正常输出日志
- `console.log` 等方法是否仍可用
- 是否触发站点完整性/反篡改校验
