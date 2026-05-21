# 定时检查规则

当目标站点利用耗时、Promise 时序或性能探针来检测调试状态时，使用此规则。

## 现象
- 只有在单步调试时流程才会中断。
- Promise 回调或 timer handler 在调试状态下走向不同。
- `performance.now`、`Date.now` 或 interval 差值控制了请求是否发出。

## 处理方式
- 在 patch 之前先捕获与定时相关的证据。
- 如有必要，规范化时间 API，或 hook Promise 的 resolve 过程，以暴露真实分支目标。
- 记录定时规避方案是否影响了可复现性。

## 需要记录的证据
- 使用了哪种计时原语
- 观测到的阈值
- 通过规避手段解锁了哪个分支或回调

## 风险说明
- 时间规范化可能掩盖真实的竞争条件。它应只用于跟踪过程，而不是默认静默启用。

## 可直接注入的 Hook 片段

### 1. Hook Promise resolve

适用场景：
- 想快速定位异步回调入口
- 需要知道哪个 Promise resolve 产出了关键参数

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

## 使用后检查
- Promise 链路是否仍然正常执行
- 是否成功看到 resolve 参数和调用栈
- 页面是否出现明显性能退化
