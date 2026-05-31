# Advanced Entrypoint Rules

This document consolidates rules for complex entrypoint scenarios: async/Promise-based functions, Web Crypto API, WebAssembly, Webpack module discovery, Vite/Rollup/ESM, and closure limitations.

---

## 1. Async and Promise-Based Entrypoints

### When to Apply
- The target entrypoint returns a Promise (e.g., `crypto.subtle.digest(...)`, Webpack dynamic `import()`, or any `async function`).
- The JSRPC action handler must wait for the Promise to resolve before returning the result.

### Detection
- Function returns an object with `.then()` method
- `call_signature.async: true` in `analysis_result.json`
- Source code uses `async function` or returns `new Promise()`
- The runtime hook probe automatically detects Promise-returning functions in `crypto[]` entries.
- During Phase 3 dependency extraction, test-call the entrypoint and check `typeof result.then === 'function'`.

### JSRPC Handler Requirement
The action handler must detect Promise results and await them. This applies to ALL calls, not just declared-async ones (some sites don't mark async in source).

```js
var result = fn.apply(ctx, args);
if (result && typeof result.then === 'function') {
  result.then(function(asyncResult) {
    // Handle ArrayBuffer/Uint8Array from crypto.subtle
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
```

If `invocation.mode` is `"async"` or `"promise"`, the stub generator MUST include Promise handling logic. Failure to do so will cause the JSRPC `/go` endpoint to return `undefined`.

### Preconditions for Async Entrypoints
- Some async functions require specific preconditions before they can be called:
  - A `CryptoKey` object must be imported/generated before calling `crypto.subtle.encrypt/decrypt/sign/verify`.
  - A Webpack dynamic import may require the chunk to be loaded first.
- Record these in `invocation.preconditions` and in `parameters[].runtime.bootstrap`.

### Evidence for Async Entrypoints
- The runtime hook probe captures `crypto[]` entries with `stack` frames that trace back to the business caller.
- The `outputLen` field (filled after the Promise resolves) confirms the algorithm produced output.
- Cross-reference with `requests[]` entries: if a `fetch/XHR` request appears shortly after the crypto event, the business caller likely chains the crypto result into the request body.

---

## 2. Web Crypto API (`crypto.subtle`)

### Characteristics
- All methods return `Promise<ArrayBuffer>`
- `digest(algorithm, data)` -- hash
- `sign(algorithm, key, data)` -- digital signature (HMAC/RSASSA/ECDSA)
- `encrypt(algorithm, key, data)` -- encryption (AES/RSA)
- `decrypt(algorithm, key, data)` -- decryption
- `importKey(...)` -- key import
- `exportKey(...)` -- key export
- Input: `ArrayBuffer`/`TypedArray`; Output: `ArrayBuffer`

### Detection
The runtime hook probe (`runtime_hook_probe.js`) automatically hooks all four core methods. Evidence is recorded in `window.__JSRA_TRACE__.crypto[]`.

### Algorithm Identification
- The `algorithm` field in `crypto[]` entries is extracted as `algorithm.name` if it is an object, or as the raw string.
- Common algorithm names: `SHA-1`, `SHA-256`, `SHA-384`, `SHA-512`, `AES-CBC`, `AES-GCM`, `AES-CTR`, `RSA-OAEP`, `RSASSA-PKCS1-v1_5`, `ECDSA`, `HMAC`.

### Hook (digest example from runtime probe)
```js
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
```

### Key Material
- `crypto.subtle.sign/encrypt/decrypt` require a `CryptoKey` object as the second argument.
- If the key is imported at runtime via `crypto.subtle.importKey`, the import call will also appear in `crypto[]` entries.
- The key cannot be directly read from JS context (it is opaque). However, the `importKey` call's raw key data (the `keyData` argument) IS observable via a hook on `crypto.subtle.importKey`.

### Adding an importKey Hook
If the runtime probe does not already hook `importKey`, add it manually:

```js
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
```

### ArrayBuffer to Hex Conversion
```js
function arrayBufferToHex(buffer) {
  return Array.from(new Uint8Array(buffer))
    .map(function(b) { return b.toString(16).padStart(2, '0'); })
    .join('');
}
```

### JSRPC Generation for crypto.subtle
- The entrypoint strategy should be `"async_crypto"`.
- The JSRPC stub must:
  1. Call the crypto function with the correct algorithm, key, and data.
  2. Await the Promise.
  3. Convert `ArrayBuffer` results to a hex string or Base64 string (as required by the target protocol).
- When entrypoint is `crypto.subtle.*`, the handler:
  - Calls the function with ArrayBuffer args
  - Detects the returned Promise
  - Converts output ArrayBuffer to hex string before resolving
- If the key must be imported first, the stub should include the import step in the handler or record it as a bootstrap dependency.

### Limitations
- `CryptoKey` objects are not transferable outside the browser context. The JSRPC handler must run in the same page context where the key was imported.
- If the key is generated via `crypto.subtle.generateKey` with `extractable: false`, it cannot be exported. The JSRPC handler must call `sign/encrypt` directly with the in-page key reference.
- `chrome-devtools-mcp` cannot intercept the internal crypto operations; it can only observe the inputs and outputs via soft hooks.

---

## 3. WebAssembly (WASM)

### Detection Signs
- Network requests for `.wasm` files.
- `WebAssembly` object on `window`.
- `WebAssembly.instantiate` or `WebAssembly.instantiateStreaming` calls in the page.
- Functions with numeric-only names or opaque signatures that accept/return `Number` or `BigInt` types.

### What We Can Do
- Hook `WebAssembly.instantiate` / `WebAssembly.instantiateStreaming`
- Inspect `WebAssembly.Module.exports(module)` to list exported functions
- Call exported WASM functions from JS

### What We Cannot Do
- Call functions NOT exported from the WASM module
- Inspect WASM internal memory or call stack
- Read WASM source code
- Bypass WASM integrity checks

### Hook for WASM Instantiation
To observe which functions the WASM module exports:

```js
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
```

### Calling WASM Exported Functions
- If the WASM module exports a function and it is accessible via a JS wrapper (e.g., `window.wasmEncrypt(data)`), it can be used as a JSRPC entrypoint.
- The entrypoint strategy should be `"wasm_export"`.
- Input and output types must be handled carefully:
  - WASM functions typically accept and return `Number`, `BigInt`, or memory pointers.
  - The JS wrapper function usually handles the conversion between JS strings/arrays and WASM memory.

### Evidence Requirements
- To confirm a WASM function as the entrypoint:
  1. Network evidence: the request body contains output from the WASM function.
  2. Runtime evidence: the JS wrapper function is observed to be called with the target parameter, and the return value matches the request body field.
- If only the WASM module loading is observed but no exported function is confirmed as the entrypoint, mark as `manual_observed_only`.

### Limitations
- **Cannot call unexported WASM internal functions.** If the crypto logic is inside the WASM module but not exported, there is no way to invoke it from JS context. Mark as `strategy=unsupported` with `unsupported_reason: "WASM internal function not exported"`.
- **Cannot read WASM memory directly from `chrome-devtools-mcp`.** Memory inspection requires `Debugger.getWasmBytecode` which is not available.
- **Cannot reverse WASM bytecode.** Static analysis of compiled WASM is out of scope.
- If the WASM module is obfuscated, the exported function interface is still usable, but understanding internal logic is not possible.

---

## 4. Webpack Module Discovery

### Overview
Many modern web applications bundle code with Webpack. The target entrypoint may be inside a Webpack module closure, not accessible via `window.*` paths. The module probe (`module_probe.js`) discovers the module system and attempts to capture `__webpack_require__` to enable module export access.

### Probe Installation

**Generation:**
```
python3 scripts/emit_module_probe.py --output generated/module_probe.js
```

**Injection:**
- Via `evaluate_script`.
- Idempotent: checks `window.__JSRA_MODULES__` before installing.

### What the Probe Detects

#### Chunk Arrays
The probe detects Webpack chunk arrays on `window`:
- **Webpack 3/4:** `window.webpackJsonp` (Array) -- Chunk format: `[chunkIds, modules, executeModules]`
- **Webpack 5:** `window.webpackChunk*` pattern (Array, keys starting with `webpackChunk`) -- Chunk format: `[[chunkIds], modules, runtime]`
- **Loadable components:** `window.__LOADABLE_LOADED_CHUNKS__`

If chunk arrays are found, `module_runtime.detected = true` and `module_runtime.type` is set to `"webpack4"`, `"webpack5"`, or `"unknown"`.

#### `__webpack_require__` Capture
Three strategies are attempted in order:

**Strategy 1: Hook `webpackJsonp.push`**
- Overrides `Array.prototype.push` on the chunk array.
- When new chunks are pushed, creates a fake `require` function that can load modules from the chunk's module factory.
- Sets `window.__JSRA_require` to the captured require function.

**Strategy 2: Check if already exposed**
- Checks `window.__webpack_require__`, `window.__webpack_modules__`, `window.webpackJsonp` for an existing require function.

**Strategy 3: Scan window for require-like functions**
- Iterates all `window` keys, looking for functions with a `.c` (module cache) property, which is a signature of `__webpack_require__`.

#### Module Cache Enumeration
Once `__webpack_require__` is captured, the probe enumerates its module cache (`require.c` or `require.cache`):

```js
var cache = require.c || require.cache || {};
var keys = Object.keys(cache);
for (var i = 0; i < keys.length; i++) {
  var mod = cache[keys[i]];
  if (mod && mod.exports) {
    // Check Object.keys(mod.exports) for functions
  }
}
```

- Lists up to 500 module IDs.
- For each cached module, inspects `exports`:
  - If an export is a `function`, records `moduleId`, `exportName`, `type: "function"`, `srcSnippet` (first 200 chars of `.toString()`), and `arity`.
  - If an export is an `object` with function properties, records sub-exports as `exportName.subKey`.

Results are stored in `window.__JSRA_MODULES__.candidateExports`.

### Evidence Retrieval

**Dump module discovery results:**
```js
evaluate_script("window.__JSRA_MODULES__.dump()")
```

Returns JSON with: `detected`, `type`, `requireAvailable`, `requirePath`, `moduleCacheKeys` (up to 200), `candidateExports`, `chunkArrays`, `globalExports` (up to 100), `errors`.

### Cross-Referencing with Runtime Hook Evidence

The module probe results must be cross-referenced with Phase 1.5 runtime hook evidence:
1. From `requests[].stack` in the runtime trace, identify function names or source file references.
2. In `candidateExports`, look for matching `exportName` values or `srcSnippet` patterns.
3. Only candidates that appear in BOTH the hook call stack AND the module exports should be marked as `confidence=high`.
4. Candidates found only in module exports but not in any hook evidence should be marked as `confidence=low`.

**Cross-Validation Rule:** Candidate exports must match functions seen in runtime hook call stacks. No match = `manual_observed_only`.

### JSRPC Generation for Webpack Exports

- Entrypoint type: `"webpack_export"`
- Required fields in `entrypoint`:
  - `module_id`: the module ID from `candidateExports[].moduleId`
  - `export_path`: the export name path (e.g., `"encrypt"` or `"default.encrypt"`)
- The JSRPC stub uses `window.__JSRA_require(module_id)` to get the module, then calls `getByPath(module, export_path)`.

### Limitations
- **Capture may fail.** If the app does not use `webpackJsonp` or the chunk array is not accessible, `require` cannot be captured. Mark as `require_available: false`.
- **Dynamic imports.** Webpack dynamic `import()` creates separate chunks that may not be in the captured cache. The probe can observe the request but cannot reliably capture the imported module's exports.
- **Module ID instability.** Module IDs may change between builds. The JSRPC stub should use the `require` function captured at runtime, not hardcoded IDs.
- **Hot Module Replacement (HMR).** If HMR is active, module cache may be invalidated. Disable HMR or capture the require before HMR runs.

---

## 5. Vite, Rollup, and ESM

### Detection
- `<script type="module">` tags in the document -- indicates ESM usage
- Vite: `import.meta.hot`, `window.__vite_plugin_meta__`
- Rollup: `window.__rollup_plugin__`

If detected, `module_runtime.type` is set to `"vite"` or `"rollup"`.

### Global Export Detection
Even in Vite/Rollup apps, many libraries expose globals. The module probe's `detectGlobalExports()` scans `window` for:
- Functions with crypto-related names: `CryptoJS`, `JSEncrypt`, `md5`, `sha256`, `sha1`, `aes`, `Base64`, `encrypt`, `decrypt`, `sign`, `verify`, `hash`, `hmac`.
- Objects with function properties that match crypto patterns.

These are stored in `window.__JSRA_MODULES__.globalExports`.

### Limitations
- ES modules use native `import/export` -- no global `require`
- **Cannot intercept native ES module resolution.** The browser's module loader is internal; there is no hook point for `import` resolution. `chrome-devtools-mcp` cannot observe or modify module loading.
- **Dynamic imports.** `import()` returns a Promise with the module namespace. The probe can observe the network request for the module file but cannot capture the module's exports unless they are also exposed globally.
- **Import maps.** Vite uses import maps (`<script type="importmap">`) for bare specifier resolution. These are visible in the DOM but do not provide runtime access to module internals.
- **SSR (Server-Side Rendering).** If the crypto logic runs on the server (e.g., Next.js SSR), it is not accessible from the browser context.
- Can only observe: global objects, module script requests, DOM elements
- **Cannot** call `import()` dynamically and reliably capture exports

### Strategy for Vite/Rollup Apps
1. Check `globalExports` for crypto libraries exposed on `window`.
2. If found, use `global_path` strategy with the global object path.
3. If not found, check if the target parameter flows through `fetch/XHR` (captured by the runtime hook probe) and trace back from the request body using the source location rules.
4. If the entrypoint is inside an ES module closure with no global export, mark as `manual_observed_only` and document the observed behavior for manual reproduction.

---

## 6. Closure-Scoped Functions

### What We Can Do
- If function is exported through module system -> use Webpack capture
- If function flows through fetch/XHR/crypto hook -> trace via call stack
- If function is on `window` -> direct path lookup

### What We Cannot Do
- Call functions in closures that are not exported
- Reconstruct lexical scope from outside
- Access variables captured by closures

### Acceptable Workarounds
1. **Hook the boundary:** If the closure calls `fetch`, `XMLHttpRequest.send`, or `JSON.stringify`, hook these outer boundaries to intercept the data.
2. **Hook crypto APIs:** If the closure uses `crypto.subtle`, `CryptoJS`, or `JSEncrypt`, hook these libraries to capture inputs and outputs.
3. **Resolver strategy:** If the closure exposes the function through a dynamic resolver (e.g., a function that returns the target function), capture the resolver.
4. **Webpack module access:** If the closure is a Webpack module, use the module probe to capture `__webpack_require__` and access the export.

### When to Mark as Unsupported
If none of the above workarounds can access the function, mark:
```json
{
  "entrypoint_discovery": {
    "strategy": "unsupported",
    "confidence": "high",
    "unsupported_reason": "Entrypoint is inside a closure with no exported reference, no hookable boundary, and no module system access."
  }
}
```

### Never Do This
- Do not claim an unexported closure function is callable.
- Do not generate a JSRPC action for a function that cannot be resolved at runtime.
- Do not guess the closure's internal structure from static source analysis alone.

---

## 7. Strategy Selection Guide

| Scenario | Strategy | JSRPC Action? |
|---|---|---|
| Function on `window.xxx.yyy` | `global_path` | Yes |
| Function identified via soft hook call stack | `runtime_hook` | Yes |
| Function in Webpack module cache | `webpack_export` | Yes (requires captured require) |
| Async function (crypto.subtle, Promise) | `async_crypto` | Yes (must handle Promise) |
| Function exported from WASM module | `wasm_export` | Yes |
| Evidence exists but entrypoint not confirmed | `manual_observed_only` | No (output evidence for manual use) |
| Function inaccessible (unexported closure, WASM internal, SW internal) | `unsupported` | No (output `unsupported_reason`) |

---

## 8. Confidence Requirements for Advanced Scenarios

| Scenario | Minimum for `high` Confidence |
|---|---|
| `async_crypto` | Network evidence (request body) + `crypto[]` event with matching algorithm and caller stack |
| `webpack_export` | Network evidence + `candidateExports` match + cross-reference with runtime hook stack |
| `wasm_export` | Network evidence + observed JS wrapper call with matching input/output |
| `global_path` | Network evidence + observed function call via `evaluate_script` |
| `runtime_hook` | Network evidence + hook-captured stack that frames through the business function |
