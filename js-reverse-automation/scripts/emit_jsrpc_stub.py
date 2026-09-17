#!/usr/bin/env python3
"""Generate JSRPC injection code from analysis_result.json.

Supports parameter-based and transforms-based configuration.
Includes evidence gating: unverified candidates return __JSRPC_ERROR__:EvidenceMissing.

Usage:
  python3 scripts/emit_jsrpc_stub.py --analysis analysis_result.json --output generated/jsrpc_inject.js
  python3 scripts/emit_jsrpc_stub.py --analysis analysis_result.json --candidates artifacts/encryption_candidates.json --output generated/jsrpc_inject.js
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import load_json


def js_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def parameter_name(transform: dict) -> str:
    path = str(transform.get("path") or "$.value")
    value = path.removeprefix("$").strip(".")
    return value.split(".", 1)[0] or str(transform.get("id") or "value")


def normalize_analysis(analysis: dict) -> dict:
    """Normalize analysis to a common format."""
    transforms = list(analysis.get("transforms") or [])
    raw_parameters = analysis.get("parameters") or {}
    parameters: dict[str, dict] = {str(k): dict(v) for k, v in raw_parameters.items() if isinstance(v, dict)}

    # Build parameters from transforms if present
    for transform in transforms:
        name = parameter_name(transform)
        config = parameters.setdefault(name, {})
        config.setdefault("entrypoint", {
            "type": transform.get("entrypoint_type", "global"),
            "path": transform.get("candidate_path", ""),
        })
        config.setdefault("runtime", {"bind_this_mode": "none"})
        config.setdefault("call_signature", {
            "arguments": ["value"], "returns": "unknown", "async": False
        })
        config["jsra_transform"] = transform
        for key in ("capture", "dom_bindings", "delivery_mode"):
            if key in transform:
                config.setdefault(key, transform[key])

    # Ensure all parameters have required fields
    for name, config in parameters.items():
        config.setdefault("entrypoint", {})
        config.setdefault("runtime", {"bind_this_mode": "none"})
        config.setdefault("call_signature", {})
        config["call_signature"].setdefault("async", False)
        config.setdefault("jsra_transform", {
            "id": name, "action": name, "safe_to_invoke": False
        })

    jsrpc = dict(analysis.get("jsrpc") or {})
    transport = jsrpc.get("transport") if isinstance(jsrpc.get("transport"), dict) else {}
    action = jsrpc.get("action_name") or jsrpc.get("action")
    if not action:
        action = next((t.get("action") for t in transforms if t.get("action")), "jsra_transform")
    ws_url = transport.get("ws_url") or jsrpc.get("ws_url")
    group = jsrpc.get("group", "jsra")
    if not ws_url:
        ws_url = f"ws://127.0.0.1:12080/ws?group={group}&name=jsra"
    return {"action_name": action, "ws_url": ws_url, "parameters": parameters}


def candidate_verified(candidate: dict | None) -> tuple[bool, str]:
    """Check if a candidate has sufficient verification evidence."""
    if not candidate:
        return False, "candidate evidence record is missing"
    if candidate.get("source") == "hint" or candidate.get("type") == "hint":
        return False, "manual entrypoint hints are not runtime evidence"
    if candidate.get("verified") is not True:
        return False, "candidate is not verified by runtime evidence"
    verification = candidate.get("verification")
    if not isinstance(verification, list) or not verification:
        return False, "candidate has no verification records"
    matched = False
    for record in verification:
        if not isinstance(record, dict):
            continue
        if record.get("matched") is True or record.get("verified") is True:
            matched = True
        for test in record.get("tests", []) if isinstance(record.get("tests"), list) else []:
            if isinstance(test, dict) and test.get("matched") is True:
                matched = True
    if not matched:
        return False, "candidate has no successful runtime/request match"
    return True, "verified runtime entrypoint"


def find_candidate_file(analysis_path: Path) -> Path | None:
    """Find candidate files in the artifacts directory."""
    roots = (analysis_path.parent / "artifacts", analysis_path.parent)
    for root in roots:
        # Prefer the post-verification artifact whenever both files exist.
        for name in ("encryption_candidates.verified.json", "encryption_candidates.json"):
            path = root / name
            if path.exists():
                return path
    return None


def build_script(config: dict, gate_errors: dict[str, str]) -> str:
    """Build the JSRPC injection script with evidence gating."""
    serialized = json.dumps(config, ensure_ascii=False, indent=2)
    errors = json.dumps(gate_errors, ensure_ascii=False, indent=2)
    return f'''// Generated by emit_jsrpc_stub.py. This file only invokes page runtime functions.
(() => {{
  "use strict";
  const CONFIG = {serialized};
  const EVIDENCE_ERRORS = {errors};

  function errorValue(parameter, name, message) {{
    return "__JSRPC_ERROR__:" + parameter + ":" + name + ":" + message;
  }}

  function getByPath(root, path) {{
    if (!root || !path) return null;
    return String(path).replace(/^window\\./, "").split(".").reduce((current, key) =>
      current == null ? null : current[key], root);
  }}

  function parentPath(path) {{
    const parts = String(path || "").split(".");
    parts.pop();
    return parts.join(".");
  }}

  function resolveEntrypoint(parameterConfig) {{
    const entrypoint = parameterConfig.entrypoint || {{}};
    if (entrypoint.type === "resolver") {{
      const resolver = getByPath(window, entrypoint.resolver_path || entrypoint.resolver_name);
      if (typeof resolver !== "function") return null;
      const resolved = resolver();
      return typeof resolved === "string" ? getByPath(window, resolved) : resolved;
    }}
    if (entrypoint.type === "webpack_export") {{
      const requireFn = window.__JSRA_require || window.__JSRA_WEBPACK_REQUIRE__;
      if (typeof requireFn !== "function") throw new Error("Webpack require was not captured");
      const moduleValue = requireFn(entrypoint.module_id);
      if (!moduleValue) throw new Error("Webpack module was not found: " + entrypoint.module_id);
      return getByPath(moduleValue, entrypoint.export_path || "default");
    }}
    return getByPath(window, entrypoint.path || "");
  }}

  function resolveThis(parameterConfig) {{
    const runtime = parameterConfig.runtime || {{}};
    if (runtime.bind_this_path) return getByPath(window, runtime.bind_this_path);
    if (runtime.bind_this_mode === "window" || runtime.bind_this_mode === "global") return window;
    if (runtime.bind_this_mode === "entrypoint_parent")
      return getByPath(window, parentPath((parameterConfig.entrypoint || {{}}).path));
    return null;
  }}

  function normalizeInput(payload) {{
    if (typeof payload === "string") {{
      try {{
        const parsed = JSON.parse(payload);
        if (parsed && typeof parsed === "object") return parsed;
      }} catch (_ ) {{}}
      return {{ value: payload }};
    }}
    if (payload && typeof payload === "object") {{
      if (Object.prototype.hasOwnProperty.call(payload, "value") || Array.isArray(payload.args))
        return payload;
      if (Object.prototype.hasOwnProperty.call(payload, "data"))
        return {{ value: payload.data, parameter: payload.parameter }};
      return {{ value: payload }};
    }}
    return {{ value: payload }};
  }}

  function coerce(value) {{
    if (value == null) return "";
    if (typeof value === "string") return value;
    if (typeof value === "number" || typeof value === "boolean") return String(value);
    return value;
  }}

  function bindInputFields(payload, parameterConfig, raw) {{
    const bindings = parameterConfig.dom_bindings || {{}};
    const fields = payload.fields || (payload.context && payload.context.fields) || payload;
    for (const [source, elementId] of Object.entries(bindings)) {{
      const element = document.getElementById(elementId);
      if (!element) continue;
      const value = source === "value" ? raw : fields[source];
      if (value !== undefined) element.value = String(value);
    }}
  }}

  function resultOrError(parameter, input, result) {{
    if (result === undefined || result === null)
      return errorValue(parameter, "InvalidResult", "page function returned no value");
    if (typeof result === "string" && result.length === 0)
      return errorValue(parameter, "InvalidResult", "page function returned an empty value");
    if (typeof result === "string" && result.indexOf("__JSRPC_ERROR__:") === 0) return result;
    if (result instanceof ArrayBuffer) return Array.from(new Uint8Array(result));
    return result;
  }}

  function serializeRequestBody(body) {{
    if (body == null) return null;
    if (typeof body === "string") return body;
    if (body instanceof URLSearchParams) return body.toString();
    if (body instanceof FormData) {{
      const values = {{}};
      for (const [key, value] of body.entries())
        values[key] = typeof value === "string" ? value : `[${{value.constructor.name}}]`;
      return values;
    }}
    if (body instanceof ArrayBuffer) return `[ArrayBuffer:${{body.byteLength}}]`;
    if (ArrayBuffer.isView(body)) return `[${{body.constructor.name}}:${{body.byteLength}}]`;
    try {{ return JSON.stringify(body); }} catch (_) {{ return String(body); }}
  }}

  function headerObject(headers) {{
    if (!headers) return {{}};
    try {{ return Object.fromEntries(new Headers(headers).entries()); }}
    catch (_) {{ return {{}}; }}
  }}

  function matchesRoute(url, expected) {{
    if (!expected) return true;
    try {{
      const actualPath = new URL(url, window.location.href).pathname.replace(/\\/+$/, "");
      const expectedPath = new URL(expected, window.location.href).pathname.replace(/\\/+$/, "");
      return actualPath === expectedPath;
    }} catch (_) {{
      return String(url).split("?", 1)[0] === String(expected).split("?", 1)[0];
    }}
  }}

  async function invokeWithNetworkCapture(fn, thisArg, args, captureConfig = {{}}) {{
    const originalFetch = window.fetch;
    const originalAlert = window.alert;
    const xhrPrototype = window.XMLHttpRequest && window.XMLHttpRequest.prototype;
    const originalXhrOpen = xhrPrototype && xhrPrototype.open;
    const originalXhrSend = xhrPrototype && xhrPrototype.send;
    const originalXhrSetRequestHeader = xhrPrototype && xhrPrototype.setRequestHeader;
    const timeoutMs = 10000;
    let captured = null;
    const requests = [];
    let resolveNetwork;
    const networkSeen = new Promise(resolve => {{ resolveNetwork = resolve; }});
    let restored = false;
    const suppressPageUi = captureConfig.suppress_page_success === true;
    const recordNetwork = record => {{
      requests.push(record);
      const expected = String(captureConfig.url_contains || captureConfig.route || "");
      if (matchesRoute(record.url, expected)) {{
        captured = record;
        resolveNetwork(captured);
        return true;
      }}
      return false;
    }};
    const parseXhrResponse = xhr => {{
      try {{
        const value = xhr.responseType === "" || xhr.responseType === "text"
          ? xhr.responseText : xhr.response;
        if (typeof value === "string") {{
          try {{ return JSON.parse(value); }} catch (_) {{ return value; }}
        }}
        return serializeRequestBody(value);
      }} catch (_) {{ return null; }}
    }};
    const withTimeout = (promise, ms, fallback) => {{
      let timer;
      const timeout = new Promise(resolve => {{
        timer = setTimeout(() => resolve(fallback), ms);
      }});
      return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
    }};
    const restore = () => {{
      if (restored) return;
      restored = true;
      if (suppressPageUi) {{
        try {{ window.alert = originalAlert; }} catch (_) {{}}
      }}
      try {{
        Object.defineProperty(window, "fetch", {{
          configurable: true, writable: true, value: originalFetch
        }});
      }} catch (_) {{ try {{ window.fetch = originalFetch; }} catch (__) {{}} }}
      if (xhrPrototype) {{
        for (const [key, value] of [["open", originalXhrOpen], ["send", originalXhrSend], ["setRequestHeader", originalXhrSetRequestHeader]]) {{
          if (typeof value !== "function") continue;
          try {{ Object.defineProperty(xhrPrototype, key, {{ configurable: true, writable: true, value }}); }}
          catch (_) {{ try {{ xhrPrototype[key] = value; }} catch (__) {{}} }}
        }}
      }}
    }};

    // Challenge pages commonly use alert() before redirecting on either
    // success or failure.  A synthetic response used only to keep the page
    // in place must not leave an external JSRPC caller blocked by a modal.
    // Keep the suppression scoped to this invocation and restore the native
    // function in every exit path.
    if (suppressPageUi && typeof originalAlert === "function") {{
      try {{ window.alert = () => {{}}; }} catch (_) {{}}
    }}

    if (typeof originalFetch === "function") {{
      const captureFetch = async function (input, init = {{}}) {{
        const url = typeof input === "string" ? input : (input && input.url) || "";
        const method = (init && init.method) || (input && input.method) || "GET";
        const body = init && Object.prototype.hasOwnProperty.call(init, "body")
          ? init.body : (input && input.body);
        const response = await Reflect.apply(originalFetch, this, arguments);
        let responseBody = null;
        try {{ responseBody = await response.clone().json(); }} catch (_) {{
          try {{ responseBody = await response.clone().text(); }} catch (__) {{}}
        }}
        const record = {{
          url,
          method,
          headers: headerObject(init && init.headers),
          requestBody: serializeRequestBody(body),
          status: response.status,
          response: responseBody
        }};
        if (recordNetwork(record)) {{
          if (suppressPageUi) {{
            try {{
              return new Response(JSON.stringify({{ success: false }}), {{
                status: response.status,
                headers: {{ "Content-Type": "application/json" }}
              }});
            }} catch (_) {{}}
          }}
        }}
        return response;
      }};
      try {{
        Object.defineProperty(window, "fetch", {{
          configurable: true, writable: true, value: captureFetch
        }});
      }} catch (_) {{
        try {{ window.fetch = captureFetch; }} catch (__) {{}}
      }}
    }}

    if (xhrPrototype && typeof originalXhrOpen === "function" && typeof originalXhrSend === "function") {{
      try {{
        Object.defineProperty(xhrPrototype, "open", {{
          configurable: true, writable: true,
          value: function(method, url) {{
            this.__jsraCapture = {{ method: String(method || "GET"), url: String(url || ""), headers: {{}} }};
            return Reflect.apply(originalXhrOpen, this, arguments);
          }}
        }});
        if (typeof originalXhrSetRequestHeader === "function") {{
          Object.defineProperty(xhrPrototype, "setRequestHeader", {{
            configurable: true, writable: true,
            value: function(name, value) {{
              const capture = this.__jsraCapture || (this.__jsraCapture = {{ method: "GET", url: "", headers: {{}} }});
              capture.headers[String(name)] = String(value);
              return Reflect.apply(originalXhrSetRequestHeader, this, arguments);
            }}
          }});
        }}
        Object.defineProperty(xhrPrototype, "send", {{
          configurable: true, writable: true,
          value: function(body) {{
            const xhr = this;
            const capture = xhr.__jsraCapture || {{ method: "GET", url: "", headers: {{}} }};
            const onLoadEnd = () => {{
              const record = {{
                transport: "xhr",
                url: capture.url,
                method: capture.method,
                headers: capture.headers,
                requestBody: serializeRequestBody(body),
                status: xhr.status,
                response: parseXhrResponse(xhr)
              }};
              recordNetwork(record);
              try {{ xhr.removeEventListener("loadend", onLoadEnd); }} catch (_) {{}}
            }};
            try {{ xhr.addEventListener("loadend", onLoadEnd, {{ once: true }}); }} catch (_) {{}}
            return Reflect.apply(originalXhrSend, this, arguments);
          }}
        }});
      }} catch (_) {{
        // Some pages make XHR methods non-configurable; fetch capture remains available.
      }}
    }}

    let resultState;
    try {{
      const result = fn.apply(thisArg, args);
      resultState = await withTimeout(
        Promise.resolve(result).then(value => ({{ value }}), error => ({{ error }})),
        timeoutMs, {{ timedOut: true }}
      );
    }} catch (error) {{
      resultState = {{ error }};
    }}
    const network = await withTimeout(networkSeen, timeoutMs, null);
    // The page function may return void while its fetch().then(...) chain is
    // still pending.  Keep alert() muted through that microtask/macrotask
    // boundary so the synthetic response cannot open a modal after capture.
    if (suppressPageUi && network) {{
      await new Promise(resolve => setTimeout(resolve, 50));
    }}
    restore();
    return {{ resultState, network: network || captured, requests }};
  }}

  if (typeof Hlclient === "undefined")
    throw new Error("Hlclient is unavailable; load JsEnv_Dev.js first");
  const client = new Hlclient(CONFIG.ws_url);

  client.regAction(CONFIG.action_name, function(resolve, rawPayload) {{
    const payload = normalizeInput(rawPayload);
    const parameter = payload.parameter || Object.keys(CONFIG.parameters)[0];
    const parameterConfig = CONFIG.parameters[parameter];
    if (!parameterConfig) {{
      resolve(errorValue(parameter, "UnknownParameter", "no parameter contract"));
      return;
    }}
    // Evidence gate: refuse to call unverified candidates
    const evidenceError = EVIDENCE_ERRORS[parameter];
    if (evidenceError) {{
      resolve(errorValue(parameter, "EvidenceMissing", evidenceError));
      return;
    }}
    try {{
      const fn = resolveEntrypoint(parameterConfig);
      if (typeof fn !== "function")
        throw new Error("verified page entrypoint is not callable");
      const raw = payload.value;
      bindInputFields(payload, parameterConfig, raw);
      let args = Array.isArray(payload.args) ? payload.args.map(coerce) : [coerce(raw)];
      const transform = parameterConfig.jsra_transform || {{}};
      if (Array.isArray(transform.arguments)) {{
        args = transform.arguments.map((arg) =>
          arg && arg.source === "constant" ? arg.value : coerce(raw));
      }}
      const captureConfig = parameterConfig.capture || transform.capture || {{}};
      invokeWithNetworkCapture(fn, resolveThis(parameterConfig), args, captureConfig)
        .then((invocation) => {{
          const resultState = invocation.resultState || {{}};
          if (resultState.error) throw resultState.error;
          if (invocation.network) {{
            resolve({{
              success: true,
              parameter,
              plaintext: raw,
              result: resultState.value === undefined ? null : resultState.value,
              request: invocation.network,
              requestBody: invocation.network.requestBody,
              response: invocation.network.response,
              status: invocation.network.status
            }});
            return;
          }}
          resolve(resultOrError(parameter, raw, resultState.value));
        }})
        .catch((error) => resolve(errorValue(parameter, error.name || "Error", error.message || String(error))));
    }} catch (error) {{
      resolve(errorValue(parameter, error.name || "Error", error.message || String(error)));
    }}
  }});
  window.__JSRA_RPC_CLIENT__ = client;
  console.info("[JSRA] registered evidence-gated action", CONFIG.action_name);
}})();
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate evidence-gated JSRPC registration code.")
    parser.add_argument("--analysis", required=True, help="Path to analysis_result.json.")
    parser.add_argument("--candidates", help="Path to encryption_candidates.json.")
    parser.add_argument("--output", required=True, help="Output JS file path.")
    args = parser.parse_args()

    analysis_path = Path(args.analysis)
    analysis = load_json(analysis_path)
    config = normalize_analysis(analysis)

    # Load candidates for evidence gating
    candidates_data: dict = {}
    candidate_path = Path(args.candidates) if args.candidates else find_candidate_file(analysis_path)
    if candidate_path and candidate_path.exists():
        try:
            candidates_data = load_json(candidate_path)
        except (OSError, ValueError):
            candidates_data = {}
    by_path = {
        c.get("path"): c
        for c in candidates_data.get("candidates", [])
        if isinstance(c, dict) and c.get("path")
    }

    # Build evidence gate errors
    gate_errors: dict[str, str] = {}
    for name, parameter in config["parameters"].items():
        transform = parameter.get("jsra_transform") or {}
        path = (parameter.get("entrypoint") or {}).get("path") or transform.get("candidate_path")
        candidate = by_path.get(path)
        ok, reason = candidate_verified(candidate)
        if not ok:
            gate_errors[name] = f"{reason}; path={path or '<missing>'}"
        if transform.get("safe_to_invoke") is True and not ok:
            gate_errors[name] = f"safe_to_invoke requires verified runtime evidence: {gate_errors[name]}"

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_script(config, gate_errors), encoding="utf-8")
    status = {
        "status": "ok" if not gate_errors else "quarantined",
        "output": str(output),
        "evidence_errors": gate_errors
    }
    print(json.dumps(status, ensure_ascii=False))
    return 0 if not gate_errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
