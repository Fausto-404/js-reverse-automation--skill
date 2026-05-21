# 代理防护规则

当请求复现或插桩流程被导航防护、代理假设或页面生命周期陷阱阻断时，使用此规则。

## 现象
- `window.close`、`history.back`、redirect hook 或 unload handler 打断了跟踪流程。
- 只有在配置代理后请求才失败。
- 页面跳转后，扩展或注入脚本被阻断。

## 处理方式
- 只中和那些阻止完成跟踪的防护逻辑。
- 记录这些防护是否改变了请求时序或页面导航状态。
- 将代理或扩展相关限制保留在诊断信息中。

## 需要记录的证据
- 防护类型（`close`、`history`、`redirect`、`proxy`、`extension`）
- 来源提示
- 处理后请求复现是否成功

## 风险说明
- 导航防护 patch 可能改变页面状态。条件允许时，应在移除 patch 后重新验证请求链路。

## 可直接注入的 Hook 片段

### 1. 阻止 `window.close`

```js
(() => {
  'use strict';
  window.close = function () {};
})();
```

### 2. 阻止 `history.go` / `history.back`

```js
(() => {
  'use strict';
  window.history.go = function () {};
  window.history.back = function () {};
})();
```

### 3. 在页面跳转前打断定位调用源

适用场景：
- 页面即将跳转
- 需要在跳转瞬间定位来源代码

```js
(() => {
  'use strict';

  window.onbeforeunload = () => {
    debugger;
    return false;
  };
})();
```

## 使用后检查
- 页面是否不再被强制关闭或回退
- 跳转前是否能稳定命中断点
- 调试结束后是否及时移除这些 patch
