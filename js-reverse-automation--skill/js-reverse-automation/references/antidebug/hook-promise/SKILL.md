---
name: js-reverse-automation-hook-promise
description: Hook Promise，将在控制台打印 Promise 的 resolve 参数，可快速定位异步回调位置。仅在需要定位 Promise 入口时启用。
---

# Hook Promise

用于在 Promise resolve 时输出参数与调用栈，帮助快速定位异步回调来源。

## 先读这些信息
- 仅在需要定位 Promise 入口/回调时启用。
- 该 hook 会增加控制台输出，可能影响性能与噪声水平。

## 需要收集的输入
- 无

## 工作流程
1) 包装 `Promise` 的 `resolve` 链路并打印参数与调用栈。
2) 确认不影响原始 Promise 行为。

## 产出
- 可直接注入的 hook 片段：

```js
(() => {
  'use strict';

  const OriginalPromise = Promise;

  Promise = function (callback) {
    if (!callback) {
      return new OriginalPromise(callback);
    }
    const originCallback = callback;
    callback = function (resolve, reject) {
      const originResolve = resolve;
      resolve = function (result) {
        if (result && !(result instanceof Promise)) {
          try {
            console.groupCollapsed('[Promise resolve]');
            console.log(result);
            console.trace();
            console.groupEnd();
          } catch (e) {}
        }
        return originResolve.apply(this, arguments);
      };
      return originCallback(resolve, reject);
    };
    return new OriginalPromise(callback);
  };

  Promise.prototype = OriginalPromise.prototype;
  Object.defineProperties(Promise, Object.getOwnPropertyDescriptors(OriginalPromise));
})();
```

- 最终输出必须注明：`已启用技能: Hook Promise`

## 交付前检查
- Promise 链路是否正常执行
- 日志输出是否可控
- 目标页面是否出现性能退化
