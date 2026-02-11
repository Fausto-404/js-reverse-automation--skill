 ---
name: jsrpc-injection-template
description: 作为主技能 `js-reverse-automation` 的补充资源，提供通用 JSRPC 注入模板，用于定位签名/加密函数入口并对外注册 action。用于生成适配不同 JS 加密场景的 JSRPC 代码。
---

# JSRPC 注入工具模板（补充资源）

> 本文件是主技能 `js-reverse-automation` 的补充模板，配合 `skill.md` 使用。

## 目标
- 统一生成可迁移的 JSRPC 注入代码
- 支持全局函数、对象方法、动态定位
- 兼容同步/异步 Promise 返回
- 支持输入输出规范化与错误兜底

## 输入
- `actionName`：JSRPC 注册的 action 名称
- `entry`：目标函数入口定位方式
- `bindThis`：需要绑定的上下文对象（可选）
- `async`：是否返回 Promise
- `normalizeInput/normalizeOutput`：输入/输出标准化函数

## 输出
- 可直接注入的 JSRPC 代码段

## 代码模板
```js
// 1) 建立 JSRPC 连接
var client = new Hlclient("ws://127.0.0.1:12080/ws?group=fausto&name=burp");

// 2) 配置区
var JSRPC_CONFIG = {
    actionName: "generate_sign",
    entry: {
        type: "global", // global | object | resolver
        path: "signFunction",
        resolver: null
    },
    bindThis: null,
    async: false,
    normalizeInput: function(param) { return param; },
    normalizeOutput: function(result) { return result; },
    onError: function(err) { return "ERROR_" + Date.now(); }
};

// 3) 工具函数
function getByPath(root, path) {
    if (!root || !path) return null;
    var parts = path.split(".");
    var cur = root;
    for (var i = 0; i < parts.length; i++) {
        cur = cur[parts[i]];
        if (!cur) return null;
    }
    return cur;
}

function resolveEntry(config) {
    if (config.entry.type === "global") return window[config.entry.path];
    if (config.entry.type === "object") return getByPath(window, config.entry.path);
    if (config.entry.type === "resolver" && typeof config.entry.resolver === "function") {
        return config.entry.resolver();
    }
    return null;
}

// 4) 注入入口
client.regAction(JSRPC_CONFIG.actionName, function(resolve, param) {
    try {
        var fn = resolveEntry(JSRPC_CONFIG);
        if (typeof fn !== "function") throw new Error("签名/加密函数未找到");

        var input = JSRPC_CONFIG.normalizeInput(param);
        var ctx = JSRPC_CONFIG.bindThis || null;
        var result = fn.call(ctx, input);

        if (JSRPC_CONFIG.async && result && typeof result.then === "function") {
            result.then(function(res) {
                resolve(JSRPC_CONFIG.normalizeOutput(res));
            }).catch(function(err) {
                resolve(JSRPC_CONFIG.onError(err));
            });
            return;
        }

        resolve(JSRPC_CONFIG.normalizeOutput(result));
    } catch (error) {
        resolve(JSRPC_CONFIG.onError(error));
    }
});
```

## 适配示例
### A. 全局函数
```js
JSRPC_CONFIG.entry = { type: "global", path: "signFunction" };
```

### B. 对象方法
```js
JSRPC_CONFIG.entry = { type: "object", path: "crypto.sign" };
JSRPC_CONFIG.bindThis = window.crypto;
```

### C. 动态定位
```js
JSRPC_CONFIG.entry = {
    type: "resolver",
    resolver: function() {
        return window.__SIGN_FN__ || (window.crypto && window.crypto.sign);
    }
};
```

### D. Promise 异步
```js
JSRPC_CONFIG.async = true;
```

## 注意事项
- 保证入口函数定位稳定
- 处理 `this` 绑定与异步返回
- 输入输出需要可复现
- 失败要有兜底，避免 JSRPC 调用中断