# 复杂入口分析规则

本文用于处理复杂的加密入口场景，包括异步函数、Promise、Web Crypto API、WebAssembly、Webpack 模块、Vite/Rollup/ESM 以及闭包作用域限制。

---

## 1. 异步与 Promise 入口

### 适用条件

- 目标入口返回 Promise，例如 crypto.subtle.digest(...)、Webpack 动态 import() 或 async function。
- JSRPC 动作处理器必须等待 Promise 完成后再返回结果。

### 识别方式

- 函数返回带有 .then() 方法的对象。
- analysis_result.json 中的 call_signature.async 为 true。
- 源码使用 async function 或返回 new Promise()。
- 运行时 Hook 会在 crypto[] 事件中记录返回 Promise 的函数。
- 在依赖提取阶段调用入口，并检查 typeof result.then === 'function'。

### JSRPC 处理要求

动作处理器必须识别 Promise 并等待结果。这适用于所有调用，不仅限于源码显式声明为异步的函数。

~~~js
var result = fn.apply(ctx, args);
if (result && typeof result.then === 'function') {
  result.then(function(asyncResult) {
    // 处理 crypto.subtle 返回的 ArrayBuffer/Uint8Array
    if (asyncResult instanceof ArrayBuffer) {
      resolve(Array.from(new Uint8Array(asyncResult)));
    } else {
      resolve(asyncResult);
    }
  }).catch(function(error) {
    resolve(normalizeError(parameter, error));
  });
  return;
}
resolve(result);
~~~

当 invocation.mode 为 "async" 或 "promise" 时，生成器必须包含 Promise 处理逻辑，否则 JSRPC /go 可能返回 undefined。

### 异步入口前置条件

- 调用 crypto.subtle.encrypt/decrypt/sign/verify 前，可能必须先导入或生成 CryptoKey。
- Webpack 动态导入可能要求目标分块先完成加载。
- 将这些条件记录到 invocation.preconditions 和 parameters[].runtime.bootstrap。

### 异步入口证据

- 运行时 Hook 从 crypto[] 中记录带有业务调用栈的事件。
- Promise 完成后填写的 outputLen 可以证明算法产生了输出。
- 与 requests[] 交叉比对：如果加密事件后很快出现 fetch/XHR 请求，说明业务函数可能把加密结果写入了请求体。

---

## 2. Web Crypto API（crypto.subtle）

### 特征

- 所有方法返回 Promise<ArrayBuffer>。
- digest(algorithm, data)：摘要。
- sign(algorithm, key, data)：数字签名（HMAC/RSASSA/ECDSA）。
- encrypt(algorithm, key, data)：加密（AES/RSA）。
- decrypt(algorithm, key, data)：解密。
- importKey(...)：导入密钥。
- exportKey(...)：导出密钥。
- 输入通常是 ArrayBuffer/TypedArray，输出是 ArrayBuffer。

### 识别

运行时 Hook 会自动包装核心方法，证据记录在 window.__JSRA_TRACE__.crypto[]。

### 算法识别

- crypto[] 事件的 algorithm 字段：对象取 algorithm.name，字符串直接记录原值。
- 常见算法名包括：SHA-1、SHA-256、SHA-384、SHA-512、AES-CBC、AES-GCM、AES-CTR、RSA-OAEP、RSASSA-PKCS1-v1_5、ECDSA、HMAC。

### Hook 示例（摘要）

~~~js
var origDigest = crypto.subtle.digest.bind(crypto.subtle);
crypto.subtle.digest = function(algorithm, data) {
  var entry = { type: 'digest', algorithm: algorithm.name || algorithm, inputLen: data.byteLength };
  trace.crypto.push(entry);
  return origDigest(algorithm, data).then(function(hash) {
    entry.outputLen = hash.byteLength;
    entry.outputHex = Array.from(new Uint8Array(hash)).map(function(b) {
      return b.toString(16).padStart(2, '0');
    }).join('').substring(0, 32) + '...';
    return hash;
  });
};
~~~

### 密钥材料

- crypto.subtle.sign/encrypt/decrypt 的第二个参数必须是 CryptoKey。
- 如果密钥通过 crypto.subtle.importKey 在运行时导入，导入事件也会出现在 crypto[] 中。
- CryptoKey 对页面脚本通常不可直接读取；但通过 importKey Hook 可以观察 keyData 原始参数。

### 补充 importKey Hook

如果运行时探针尚未覆盖 importKey，可以临时补充：

~~~js
(function() {
  'use strict';
  if (!window.crypto || !window.crypto.subtle) return;
  var origImportKey = crypto.subtle.importKey.bind(crypto.subtle);
  crypto.subtle.importKey = function(format, keyData, algorithm, extractable, usages) {
    console.log('[JSRA] crypto.subtle.importKey', {
      format: format,
      algorithm: typeof algorithm === 'string' ? algorithm : algorithm.name,
      usages: usages,
      keyDataSnippet: keyData instanceof ArrayBuffer
        ? '[ArrayBuffer:' + keyData.byteLength + ']'
        : (keyData instanceof Uint8Array ? '[Uint8Array:' + keyData.length + ']' : String(keyData))
    });
    return origImportKey(format, keyData, algorithm, extractable, usages);
  };
})();
~~~

### ArrayBuffer 转十六进制

~~~js
function arrayBufferToHex(buffer) {
  return Array.from(new Uint8Array(buffer))
    .map(function(b) { return b.toString(16).padStart(2, '0'); })
    .join('');
}
~~~

### crypto.subtle 的 JSRPC 生成要求

- 入口策略使用 async_crypto。
- JSRPC 必须使用正确的算法、密钥和数据调用函数，等待 Promise 完成，并按目标协议将 ArrayBuffer 转为十六进制或 Base64。
- 入口为 crypto.subtle.* 时，处理器必须使用 ArrayBuffer 参数、识别返回的 Promise，并在完成后转换输出。
- 如果必须先导入密钥，应在处理器中完成导入，或将其记录为启动依赖。

### 限制

- CryptoKey 不能传出浏览器上下文；JSRPC 必须在密钥被导入的同一页面上下文中执行。
- 使用 extractable: false 生成的密钥不能导出，必须直接使用页面内的密钥引用执行签名或加密。
- chrome-devtools-mcp 无法直接拦截浏览器内部密码学运算，只能通过软 Hook 观察输入和输出。

---

## 3. WebAssembly（WASM）

### 识别信号

- 网络请求加载 .wasm 文件。
- window 上存在 WebAssembly 对象。
- 页面调用 WebAssembly.instantiate 或 WebAssembly.instantiateStreaming。
- 存在仅含数字的函数名，或参数/返回值为 Number、BigInt 的不透明函数。

### 可以执行的操作

- Hook WebAssembly.instantiate / WebAssembly.instantiateStreaming。
- 使用 WebAssembly.Module.exports(module) 查看导出函数。
- 从 JavaScript 调用已导出的 WASM 函数。

### 不可以执行的操作

- 调用 WASM 模块未导出的函数。
- 查看 WASM 内部内存或调用栈。
- 读取 WASM 源码。
- 绕过 WASM 完整性校验。

### WASM 实例化 Hook

用于观察 WASM 模块导出的函数：

~~~js
var origInstantiate = WebAssembly.instantiate;
WebAssembly.instantiate = function(bytes, imports) {
  console.log('[JSRA] WebAssembly.instantiate called, bytes length:', bytes ? bytes.byteLength || bytes.length : 'unknown');
  return origInstantiate(bytes, imports).then(function(result) {
    var module = result.module || result;
    if (module instanceof WebAssembly.Module) {
      window.__JSRA_WASM_EXPORTS = WebAssembly.Module.exports(module);
      console.log('[JSRA] WASM exports:', window.__JSRA_WASM_EXPORTS);
    }
    if (result.instance) {
      window.__JSRA_WASM_INSTANCE = result.instance;
      var exportNames = Object.keys(result.instance.exports);
      console.log('[JSRA] WASM instance exports:', exportNames);
      for (var i = 0; i < exportNames.length; i++) {
        var name = exportNames[i];
        if (typeof result.instance.exports[name] === 'function') {
          console.log('[JSRA] WASM export function:', name, 'arity:', result.instance.exports[name].length);
        }
      }
    }
    return result;
  });
};
~~~

### 调用 WASM 导出函数

- 如果模块导出函数且页面通过 JavaScript 包装器暴露，例如 window.wasmEncrypt(data)，可以将其作为 JSRPC 入口。
- 入口策略使用 wasm_export。
- WASM 通常使用 Number、BigInt 或内存指针；JavaScript 包装器负责字符串/数组与内存之间的转换。

### 证据要求

确认 WASM 函数是入口至少需要：

1. 网络证据：请求体包含 WASM 函数产生的结果。
2. 运行时证据：观察到 JavaScript 包装器以目标参数调用，并且返回值与请求字段一致。

仅观察到 WASM 加载、没有确认导出函数参与目标请求时，标记为 manual_observed_only。

### 限制

- WASM 内部逻辑未导出时，不能从 JavaScript 上下文调用，标记 strategy=unsupported，并填写 unsupported_reason。
- chrome-devtools-mcp 不能直接读取 WASM 内存。
- 不在范围内反编译 WASM 字节码。
- WASM 混淆时仍可使用导出函数接口，但不能仅凭接口理解内部逻辑。

---

## 4. Webpack 模块发现

### 概述

现代 Web 应用通常使用 Webpack 打包。目标入口可能位于 Webpack 模块闭包中，无法通过 window.* 直接访问。模块探针会发现模块系统，并尝试捕获 __webpack_require__，从而访问模块导出。

### 探针安装

生成：

~~~bash
python3 scripts/emit_module_probe.py --output generated/module_probe.js
~~~

注入：

- 通过 evaluate_script 注入。
- 安装前检查 window.__JSRA_MODULES__，保证重复注入不会重复安装。

### 探针检测内容

#### 分块数组

探针会在 window 上检测 Webpack 分块数组：

- Webpack 3/4：window.webpackJsonp，格式为 [chunkIds, modules, executeModules]。
- Webpack 5：符合 window.webpackChunk* 的数组，格式为 [[chunkIds], modules, runtime]。
- Loadable 组件：window.__LOADABLE_LOADED_CHUNKS__。

发现分块数组后，设置 module_runtime.detected = true，并将类型记录为 webpack4、webpack5 或 unknown。

#### 捕获 __webpack_require__

按以下顺序尝试三种策略：

**策略一：Hook webpackJsonp.push**

- 覆盖分块数组上的 Array.prototype.push。
- 新分块进入时，从模块工厂创建可加载模块的伪 require 函数。
- 将捕获到的函数保存为 window.__JSRA_require。

**策略二：检查已有暴露对象**

- 检查 window.__webpack_require__、window.__webpack_modules__ 和 window.webpackJsonp 中是否已有可用函数。

**策略三：扫描 window 中的 require 类函数**

- 遍历 window 属性，寻找带有 .c 模块缓存属性的函数。

#### 模块缓存枚举

捕获 __webpack_require__ 后，枚举 require.c 或 require.cache：

~~~js
var cache = require.c || require.cache || {};
var keys = Object.keys(cache);
for (var i = 0; i < keys.length; i++) {
  var mod = cache[keys[i]];
  if (mod && mod.exports) {
    // 检查 mod.exports 中的函数
  }
}
~~~

- 最多列出 500 个模块 ID。
- 导出值是函数时，记录 moduleId、exportName、type、前 200 个字符的 srcSnippet 和参数个数 arity。
- 导出值是带函数属性的对象时，记录形如 exportName.subKey 的子导出。

结果保存到 window.__JSRA_MODULES__.candidateExports。

### 证据读取

读取模块发现结果：

~~~js
evaluate_script("window.__JSRA_MODULES__.dump()")
~~~

结果包含：detected、type、requireAvailable、requirePath、moduleCacheKeys（最多 200 个）、candidateExports、chunkArrays、globalExports（最多 100 个）和 errors。

### 与运行时 Hook 证据交叉验证

必须把模块探针结果与运行时 Hook 证据交叉比对：

1. 从运行时追踪的 requests[].stack 中提取函数名或源码文件引用。
2. 在 candidateExports 中查找匹配的 exportName 或 srcSnippet 特征。
3. 只有同时出现在 Hook 调用栈和模块导出中的候选，才能标记为 confidence=high。
4. 仅出现在模块导出中、没有运行时 Hook 证据的候选，标记为 confidence=low。

交叉验证规则：候选导出必须与运行时 Hook 调用栈中观察到的函数匹配；不匹配时标记为 manual_observed_only。

### Webpack 导出的 JSRPC 生成

- 入口类型：webpack_export。
- entrypoint 必须包含 module_id 和 export_path，分别表示模块 ID 和导出名称路径，例如 encrypt 或 default.encrypt。
- JSRPC 使用 window.__JSRA_require(module_id) 获取模块，再通过 getByPath(module, export_path) 调用导出。

### 限制

- 如果应用不使用 webpackJsonp 或分块数组不可访问，捕获可能失败，标记 require_available: false。
- Webpack 动态 import() 产生的分块可能不在已捕获缓存中；探针可以观察请求，但不能稳定获取导出。
- 模块 ID 可能随构建变化；JSRPC 应使用运行时捕获的 require，不要硬编码模块 ID。
- 启用热更新时模块缓存可能失效，应关闭热更新，或在热更新运行前捕获 require。

---

## 5. Vite、Rollup 与 ESM

### 识别

- 文档中出现 <script type="module">。
- Vite 特征：import.meta.hot、window.__vite_plugin_meta__。
- Rollup 特征：window.__rollup_plugin__。

识别后，将 module_runtime.type 设置为 vite 或 rollup。

### 全局导出发现

即使使用 Vite/Rollup，部分库仍会暴露全局对象。模块探针的 detectGlobalExports() 会扫描 window：

- 带有密码学相关名称的函数：CryptoJS、JSEncrypt、md5、sha256、sha1、aes、Base64、encrypt、decrypt、sign、verify、hash、hmac。
- 函数属性名称符合密码学特征的对象。

结果保存在 window.__JSRA_MODULES__.globalExports。

### 限制

- ES 模块使用原生 import/export，不存在全局 require。
- 浏览器模块加载器属于内部实现，没有可直接 Hook 的导入解析入口，chrome-devtools-mcp 不能观察或修改原生模块解析。
- 动态 import() 返回 Promise，探针可以观察模块网络请求，但只有模块同时暴露到全局时才能捕获导出。
- Vite 的导入映射只提供 DOM 层面的映射信息，不能访问模块内部运行时对象。
- 如果加密逻辑运行在服务端，例如 Next.js SSR，则无法从浏览器上下文获取。
- 只能观察全局对象、模块脚本请求和 DOM 元素；不能可靠地动态调用 import() 并捕获导出。

### Vite/Rollup 页面处理策略

1. 在 globalExports 中查找暴露的密码学库。
2. 找到后使用 global_path 策略。
3. 未找到时，检查目标参数是否流经运行时 Hook 捕获的 fetch/XHR，再根据源码位置从请求体回溯。
4. 入口位于没有全局导出的 ES 模块闭包时，标记 manual_observed_only，记录观察结果供人工复现。

---

## 6. 闭包作用域函数

### 可以执行的操作

- 函数通过模块系统导出：使用 Webpack 捕获。
- 函数流经 fetch/XHR/crypto Hook：通过调用栈回溯。
- 函数位于 window：直接查找路径。

### 不可以执行的操作

- 调用未导出的闭包函数。
- 从外部重建词法作用域。
- 访问闭包捕获的变量。

### 可接受的替代方案

1. **Hook 边界**：闭包调用 fetch、XMLHttpRequest.send 或 JSON.stringify 时，Hook 外层边界截获数据。
2. **Hook 密码学 API**：闭包使用 crypto.subtle、CryptoJS 或 JSEncrypt 时，Hook 库获取输入和输出。
3. **解析器策略**：闭包通过动态解析器暴露目标函数时，捕获解析器。
4. **Webpack 模块访问**：闭包属于 Webpack 模块时，使用模块探针捕获 __webpack_require__ 并访问导出。

### 何时标记为不支持

以上方案都无法访问函数时，标记为：

~~~json
{
  "entrypoint_discovery": {
    "strategy": "unsupported",
    "confidence": "high",
    "unsupported_reason": "入口位于没有导出引用、没有可 Hook 边界且无法访问模块系统的闭包中。"
  }
}
~~~

### 禁止事项

- 不得声称未导出的闭包函数可调用。
- 不得为运行时无法解析的函数生成 JSRPC 动作。
- 不能仅凭静态源码分析猜测闭包内部结构。

---

## 7. 策略选择参考

| 场景 | 策略 | 是否生成 JSRPC 动作 |
|---|---|---|
| 函数位于 window.xxx.yyy | global_path | 是 |
| 通过软 Hook 调用栈发现函数 | runtime_hook | 是 |
| 函数位于 Webpack 模块缓存 | webpack_export | 是（需要已捕获的 require） |
| 异步函数（crypto.subtle、Promise） | async_crypto | 是（必须处理 Promise） |
| 函数由 WASM 模块导出 | wasm_export | 是 |
| 有证据但尚未确认入口 | manual_observed_only | 否（输出证据供人工使用） |
| 函数不可访问（未导出闭包、WASM 内部函数、Service Worker 内部闭包） | unsupported | 否（输出 unsupported_reason） |

---

## 8. 复杂场景的置信度要求

| 场景 | high 置信度的最低要求 |
|---|---|
| async_crypto | 网络证据（请求体）+ 匹配算法和调用栈的 crypto[] 事件 |
| webpack_export | 网络证据 + candidateExports 匹配 + 运行时 Hook 调用栈交叉验证 |
| wasm_export | 网络证据 + 观察到 JavaScript 包装器调用且输入输出匹配 |
| global_path | 网络证据 + 通过 evaluate_script 观察到函数调用 |
| runtime_hook | 网络证据 + Hook 捕获的、经过业务函数的调用栈 |
