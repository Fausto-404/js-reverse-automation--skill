# Evidence Collection Rules

This document consolidates all evidence collection methods for the js-reverse-automation skill: network capture, soft hooks, source location, and runtime hook tracing. Each section preserves the original rules, patterns, and risk notes.

---

## 1. Network Capture

### When to Use
- Need to confirm whether the target parameter appears in URL, Header, Cookie, JSON body, or form body.
- The page action triggers multiple similar requests; must narrow down to the one actually involved in signing or encryption.
- User provided `Optional Fetch Example`, but need to map it to the corresponding real browser request.

### Evidence Priority
1. Network records triggered by real page actions
2. Request details: method, URL, headers, payload, response
3. In-page observation code output: call stacks, serialized objects, or function arguments
4. Console logs and page state snapshots

### Recommended Flow
1. Open the target page, complete necessary interactions, ensure the request is actually sent.
2. Use chrome-devtools-mcp network request list to filter candidate requests.
3. Read details for each candidate request, confirm the target parameter location and request body shape.
4. If there are many similar requests, narrow down by:
   - Whether the target parameter appears
   - Whether the request trigger time is close to the user action
   - Whether the response status matches business expectations
   - Whether the request body contains adjacent fields of unencrypted plaintext and encrypted result
5. Once the request is locked, immediately record:
   - Request URL
   - HTTP method
   - Content-Type
   - Parameter location
   - Key Headers
   - Trigger action
6. If request details alone are insufficient for source location, proceed to minimal observation code or minimal hooks.

### Success Criteria
- At least one request is explicitly marked as the target request.
- The location of each parameter to analyze is known.
- Request context sufficient to support subsequent source location has been recorded.

### Failure Signals
- Can only see static resource requests, not business APIs.
- The target action triggers many highly similar requests, but cannot distinguish which one participates in signing.
- Requests exist, but cannot confirm where the target parameter appears after which serialization layer.

### Handling Strategies
- For multi-request competition scenarios, add a single-variable experiment: change only one input value, then see which request field changes synchronously.
- For opaque serialization scenarios, add minimal hooks to:
  - `window.fetch`
  - `XMLHttpRequest.prototype.open`
  - `XMLHttpRequest.prototype.send`
  - `JSON.stringify`
- These observation points are injected via `evaluate_script`; if the page will refresh, use `navigate_page(initScript=...)` to pre-inject before the next navigation.
- The purpose of hooks is only to record the "last observable form before sending", not to replace network evidence.

---

## 2. Soft Hooks (Hook Debugging Rules)

### Applicable Scope
- Network evidence has locked the target request, but entrypoint function evidence is still missing.
- Need to confirm whether a parameter changes before and after a certain function call.
- Need to confirm return values, `this` binding, async behavior, or global dependencies.

### Minimal Hook Principles
- Hook general boundaries first, then business functions.
- Record first, rewrite later; by default, do not replace the original function.
- Add only one observation point per hook; avoid multiple hooks polluting evidence together.
- When the page is already loaded, prefer `evaluate_script` to inject observation code.
- If the page will refresh or navigate, use `navigate_page(initScript=...)` to pre-inject before the next navigation.

### Recommended Hook Order
1. `window.fetch`
2. `XMLHttpRequest.prototype.open`
3. `XMLHttpRequest.prototype.send`
4. `JSON.stringify`
5. Explicitly matched business functions
6. If necessary, supplement with `eval` / `Function` / Promise related nodes

### Each Hook Must Record At Minimum
- Hook point path
- Match condition
- Input argument summary
- Return value summary
- Call stack summary
- Whether it changes page behavior
- Injection method: `evaluate_script` or `navigate_page(initScript=...)`

### Entrypoint Confirmation Rules
- Business function hooks must prove at least one of the following:
  - The plaintext input has a verifiable mapping to the target parameter in the request
  - The function return value directly enters the request body, Header, or Cookie
- If only internal crypto library calls are seen without caller context, it is not sufficient to认定 as the final entrypoint.

### Dependency Extraction Rules
- Explicitly record:
  - Where `this` binding comes from
  - Which global objects or closure objects are depended upon
  - Whether async waiting is needed
  - Whether the page needs to complete a bootstrap first
- This information must ultimately go into `artifacts/phase3_dependencies.json` and `analysis_result.json`.

### Risk Control
- Do not freeze large numbers of prototypes by default.
- Do not globally replace all crypto APIs for convenience of observation.
- Once a hook causes a business branch change, first roll back to a smaller scope before continuing.

---

## 3. Source Location

### Core Principles
- First backtrack from request details, in-page call stacks, and serialization nodes, then do keyword search.
- First find "the last location where the parameter changed", then find "the deepest algorithm point".
- Only accept source location results with evidence; do not accept pure text matching conclusions.

### Location Priority
1. Script clues from request details, in-page `Error().stack`, or observation-code-captured stack frames
2. Pre-send object construction or serialization point
3. Source code snippets with the same name as or adjacent to the parameter
4. Crypto library call sites

### Recommended Flow
1. Start from the target request, first read request details, confirm request method, request body, and related script clues.
2. Add minimal observation code to the request construction point:
   - Observe `fetch` / XHR `send`
   - Observe `JSON.stringify`
   - Output `Error().stack` in-page
3. If the page has refreshed or will navigate:
   - Use `navigate_page(initScript=...)` to pre-inject observation code
   - Re-trigger the target action and record the pre-serialization object
4. Identify three key positions of the parameter:
   - Plaintext entry point
   - Processing or encryption point
   - Final write point before sending
5. Only when at least two of these three positions are chained by evidence can the preferred entrypoint be output.

### Candidate Entrypoint Acceptance Criteria
- Can explain the target parameter's change from plaintext to ciphertext.
- Can locate a callable function or stable resolver.
- Can explain `this` binding, parameter signature, and necessary dependencies.

### Common Misjudgments
- Only matched the parameter name, but the variable is just an intermediate copy.
- Only matched `md5` / `aes` / `sha`, but it does not directly serve the target request.
- Only saw wrapper functions, did not continue to confirm the real execution point.

### Output Requirements
- `source_hint` should尽量 land on a specific bundle location or object path.
- `evidence` must contain at least one of:
  - In-page call stack
  - Hook-captured input arguments and return values
  - Pre-serialization object snapshot
  - Parameter value comparison experiment results

---

## 4. Runtime Hook Tracing

### Overview
Runtime hook tracing uses a pre-injected probe (`runtime_hook_probe.js`) to capture runtime evidence at the network, crypto, and serialization layers. It is the primary evidence source for Phase 1.5 and supplements Phase 2 entrypoint discovery.

### Probe Installation

**Generation:**
```
python3 scripts/emit_runtime_hook_probe.py --output generated/runtime_hook_probe.js --params "target_param1,target_param2"
```

**Injection:**
- Via `evaluate_script` if the page is already loaded.
- Via `navigate_page(initScript=...)` if the page will refresh or navigate.

**Idempotency:**
- The probe checks `window.__JSRA_TRACE__` before installing; double-install is safe (no-op).

### What the Probe Captures

The probe installs soft hooks on the following boundaries and records evidence into `window.__JSRA_TRACE__`:

#### 4.1 Network Requests (`requests[]`)
- **Hook points:** `window.fetch`, `XMLHttpRequest.prototype.open`, `XMLHttpRequest.prototype.send`
- **Evidence per entry:**
  - `type`: `"fetch"` or `"xhr"`
  - `url`: request URL
  - `method`: HTTP method
  - `headers`: summarized request headers (for fetch)
  - `bodySnippet`: truncated request body
  - `timestamp`: `Date.now()`
  - `stack`: call stack captured via `Error().stack` (up to 10 frames)

#### 4.2 Crypto Events (`crypto[]`)
- **Hook points:** `crypto.subtle.digest`, `crypto.subtle.sign`, `crypto.subtle.encrypt`, `crypto.subtle.decrypt`
- **Evidence per entry:**
  - `type`: `"digest"`, `"sign"`, `"encrypt"`, or `"decrypt"`
  - `algorithm`: algorithm name (string or `.name` property)
  - `inputLen`: input byte length
  - `outputLen`: output byte length (filled after Promise resolves)
  - `outputHex`: first 32 hex chars of digest output (for `digest` only)
  - `timestamp`: `Date.now()`
  - `stack`: call stack (up to 10 frames)

#### 4.3 Serializer Events (`serializers[]`)
- **Hook points:** `FormData.prototype.append`, `FormData.prototype.set`, `URLSearchParams.prototype.append`, `URLSearchParams.prototype.set`, `URLSearchParams.prototype.toString`, `JSON.stringify`
- **Evidence per entry:**
  - `type`: serializer method name
  - `name`: field name (for FormData/URLSearchParams)
  - `valueSnippet` or `resultSnippet`: truncated value
  - `keys`: object keys (for JSON.stringify, up to 20)
  - `timestamp`: `Date.now()`
  - `stack`: call stack (for JSON.stringify and URLSearchParams.toString)

#### 4.4 Selective JSON.stringify Hook
- `JSON.stringify` is only logged when the object being serialized contains keys matching the watched parameter list (`TARGET_PARAMS` + `SENSITIVE_KEYS`).
- `SENSITIVE_KEYS` includes: `sign`, `token`, `enc`, `password`, `signature`, `hash`, `key`, `nonce`, `timestamp`, `ts`, `data`, `encrypt`, `decrypt`.
- This prevents log flooding from unrelated serialization calls.

### Evidence Retrieval

**Dump all evidence:**
```js
evaluate_script("window.__JSRA_TRACE__.dump()")
```
Returns a JSON string containing `requests`, `crypto`, `serializers`, `errors`.

**Clear evidence buffer:**
```js
evaluate_script("window.__JSRA_TRACE__.clear()")
```

### Using Evidence for Entrypoint Discovery

1. **Identify crypto entry from call stack:** In `requests[].stack`, look for frames that reference encryption/signing functions. These frames point to the business-level caller, not just the crypto library.
2. **Cross-reference with serializer events:** If `serializers[]` shows `JSON.stringify` or `URLSearchParams.toString` being called with watched keys, the `stack` frames indicate where the request body is assembled.
3. **Match crypto algorithm to request body:** If `crypto[]` shows a `digest` or `encrypt` event, match the `algorithm` and `outputLen` to the observed ciphertext length in the request body.
4. **Extract caller function path:** From the stack frames, identify the outermost business function (not `fetch`, `XMLHttpRequest`, or crypto internals). This is the candidate entrypoint.

### Evidence Standards for Runtime Tracing

- **Minimum evidence for `confidence=high`:** At least one `requests[]` entry with a stack that frames through a business function, plus at least one `crypto[]` or `serializers[]` entry that correlates to the target parameter.
- **Minimum evidence for `confidence=medium`:** At least one `requests[]` entry with the target parameter visible in `bodySnippet`, even if the stack does not clearly frame the business caller.
- **Not sufficient for `confidence=high`:** Only crypto library internal calls without business caller context.

### Failure Handling

| Symptom | Action |
|---|---|
| Probe injection fails (anti-debug blocks it) | Record anti-debug symptom; refer to `references/antidebug/` rules; degrade to static analysis |
| No `requests[]` entries after triggering target action | Verify the target action was actually performed; check if the probe was injected in the correct execution context |
| `crypto[]` is empty but request body contains ciphertext | The site may use a non-Subtle crypto library (e.g., CryptoJS, JSEncrypt); use the CryptoJS/JSEncrypt hook snippets from `antidebug/dynamic-alias.md` |
| `stack` frames are all anonymous or minified | Use the source location rules (Section 3) to correlate with bundle line numbers |

### Risk Notes
- The probe does not replace network evidence; it supplements it.
- The probe hooks are soft (wrap, not replace) and should not break page functionality.
- If a hook causes timing changes, record the hook-off baseline first, then the hook-on observation.
- The probe does not persist across page navigations; re-inject via `initScript` if the page reloads.

---

## 5. Evidence Standards (Cross-Cutting)

### Evidence Hierarchy
1. **Network evidence** (request URL, method, body, headers, response) -- strongest
2. **Runtime hook evidence** (call stacks, crypto events, serializer events) -- strong
3. **Source code evidence** (bundle location, object path, keyword match) -- supporting only

### Confidence Requirements
| Confidence | Minimum Evidence |
|---|---|
| `high` | Network evidence + Runtime/stack/module evidence (at least 2 types) |
| `medium` | Single evidence source (network OR runtime) |
| `low` | Keyword search or source code pattern only |

### What Counts as Evidence
- A `requests[]` entry from the runtime probe with a stack that frames through a business function.
- A `crypto[]` entry that correlates algorithm and output length to the observed ciphertext.
- A `serializers[]` entry that shows the parameter being serialized before request dispatch.
- An `Error().stack` capture from `evaluate_script` that shows the business caller.
- A hook-captured input/output pair that maps plaintext to ciphertext.
- A single-variable experiment result that shows which request field changes when the input changes.

### What Does NOT Count as Evidence
- A keyword match in source code without runtime correlation.
- A crypto library function match without business caller context.
- A global object path that exists but was never observed to be called during the target action.
- A suspected entrypoint without any stack, hook, or network confirmation.

### Recording Requirements
Every evidence item must include:
- Source type (network, hook, stack, serializer, crypto, experiment)
- Timestamp or sequence indicator
- Enough context to reproduce the observation (URL, method, hook point path, stack frames)
- Whether the observation was made with or without patches/hooks active
