#!/usr/bin/env python3
"""Generate JSRPC injection code from analysis_result.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", required=True, help="Path to analysis_result.json.")
    parser.add_argument("--output", required=True, help="Generated JS file path.")
    return parser.parse_args()


def load_json(path: str) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("analysis_result.json must contain a JSON object")
    return data


def js_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def emit_parameter_block(name: str, config: dict) -> str:
    entrypoint = config["entrypoint"]
    runtime = config["runtime"]
    call_signature = config["call_signature"]
    return f"""  {js_string(name)}: {{
    entrypoint: {json.dumps(entrypoint, ensure_ascii=False, indent=4).replace(chr(10), chr(10) + '    ')},
    runtime: {json.dumps(runtime, ensure_ascii=False, indent=4).replace(chr(10), chr(10) + '    ')},
    callSignature: {json.dumps(call_signature, ensure_ascii=False, indent=4).replace(chr(10), chr(10) + '    ')}
  }}"""


def build_script(analysis: dict) -> str:
    parameters = analysis.get("parameters", {})
    parameter_blocks = ",\n".join(
        emit_parameter_block(name, config) for name, config in parameters.items()
    )
    action_name = analysis["jsrpc"]["action_name"]
    ws_url = analysis["jsrpc"]["transport"]["ws_url"]

    return f"""// emit_jsrpc_stub.py
(function () {{
  'use strict';

  var analysis = {{
    actionName: {js_string(action_name)},
    wsUrl: {js_string(ws_url)},
    parameters: {{
{parameter_blocks}
    }}
  }};

  function getByPath(root, path) {{
    if (!root || !path) return null;
    return path.split('.').reduce(function (current, key) {{
      if (current == null) return null;
      return current[key];
    }}, root);
  }}

  function parentPath(path) {{
    if (!path) return '';
    var parts = path.split('.');
    parts.pop();
    return parts.join('.');
  }}

  function resolveEntrypoint(parameterConfig) {{
    var entrypoint = parameterConfig.entrypoint || {{}};

    // Type: resolver — call a resolver function that returns the target or a path
    if (entrypoint.type === 'resolver') {{
      var resolverPath = entrypoint.resolver_path || entrypoint.resolver_name || '';
      var resolver = getByPath(window, resolverPath);
      if (typeof resolver === 'function') {{
        var resolved = resolver();
        if (typeof resolved === 'string') {{
          return getByPath(window, resolved);
        }}
        return resolved;
      }}
      return null;
    }}

    // Type: webpack_export — use captured __webpack_require__ to get module export
    if (entrypoint.type === 'webpack_export') {{
      var requireFn = window.__JSRA_require;
      if (typeof requireFn !== 'function') {{
        throw new Error('Webpack require not captured. Run module probe first.');
      }}
      var moduleId = entrypoint.module_id;
      var exportPath = entrypoint.export_path || 'default';
      if (moduleId == null) {{
        throw new Error('webpack_export requires module_id in entrypoint config');
      }}
      var mod = requireFn(moduleId);
      if (!mod) throw new Error('Module not found: ' + moduleId);
      return getByPath(mod, exportPath);
    }}

    // Type: object / jquery_plugin / global_function — direct path lookup
    return getByPath(window, entrypoint.path || '');
  }}

  function resolveThis(parameterConfig) {{
    var runtime = parameterConfig.runtime || {{}};
    if (runtime.bind_this_path) {{
      return getByPath(window, runtime.bind_this_path);
    }}
    var mode = runtime.bind_this_mode || '';
    if (mode === 'window' || mode === 'global') {{
      return window;
    }}
    if (mode === 'entrypoint_parent') {{
      return getByPath(window, parentPath((parameterConfig.entrypoint || {{}}).path || ''));
    }}
    return null;
  }}

  function normalizeInput(payload) {{
    if (typeof payload === 'string') {{
      try {{
        var maybeJson = JSON.parse(payload);
        if (maybeJson && typeof maybeJson === 'object') return maybeJson;
      }} catch (e) {{}}
      return {{ value: payload }};
    }}
    if (payload && typeof payload === 'object') {{
      if (typeof payload.value !== 'undefined' || Array.isArray(payload.args)) return payload;
      if (typeof payload.data !== 'undefined') return {{ value: payload.data, parameter: payload.parameter }};
      if (typeof payload.param !== 'undefined') return {{ value: payload.param, parameter: payload.parameter }};
      return {{ value: payload }};
    }}
    return {{ value: payload }};
  }}

  function coerceArg(value) {{
    if (value == null) return '';
    if (typeof value === 'string') return value;
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    if (value && typeof value === 'object' && typeof value.value !== 'undefined') {{
      return coerceArg(value.value);
    }}
    return String(value);
  }}

  function normalizeError(parameter, error) {{
    var name = error && error.name ? error.name : 'Error';
    var message = error && error.message ? error.message : String(error);
    return '__JSRPC_ERROR__:' + parameter + ':' + name + ':' + message;
  }}

  var client = new Hlclient(analysis.wsUrl);

  function checkPreconditions(parameterConfig) {{
    var inv = parameterConfig.invocation || {{}};
    var pre = inv.preconditions || {{}};
    var errors = [];
    if (pre.dom_required && Array.isArray(pre.selectors)) {{
      for (var i = 0; i < pre.selectors.length; i++) {{
        if (!document.querySelector(pre.selectors[i])) {{
          errors.push('Missing DOM element: ' + pre.selectors[i]);
        }}
      }}
    }}
    if (Array.isArray(pre.local_storage_keys)) {{
      for (var i = 0; i < pre.local_storage_keys.length; i++) {{
        if (!localStorage.getItem(pre.local_storage_keys[i])) {{
          errors.push('Missing localStorage key: ' + pre.local_storage_keys[i]);
        }}
      }}
    }}
    if (Array.isArray(pre.session_storage_keys)) {{
      for (var i = 0; i < pre.session_storage_keys.length; i++) {{
        if (!sessionStorage.getItem(pre.session_storage_keys[i])) {{
          errors.push('Missing sessionStorage key: ' + pre.session_storage_keys[i]);
        }}
      }}
    }}
    return errors;
  }}

  function handleResult(resolve, parameter, result) {{
    // Always try to handle Promise-like results (covers both declared async and undeclared)
    if (result && typeof result.then === 'function') {{
      result.then(function (asyncResult) {{
        // Handle ArrayBuffer/Uint8Array from crypto.subtle
        if (asyncResult instanceof ArrayBuffer) {{
          resolve(Array.from(new Uint8Array(asyncResult)));
        }} else {{
          resolve(asyncResult);
        }}
      }}).catch(function (error) {{
        resolve(normalizeError(parameter, error));
      }});
      return true;
    }}
    return false;
  }}

  client.regAction(analysis.actionName, function (resolve, rawPayload) {{
    var activeParameter = 'unknown';
    try {{
      var payload = normalizeInput(rawPayload);
      var parameter = payload.parameter || Object.keys(analysis.parameters)[0];
      activeParameter = parameter;
      var parameterConfig = analysis.parameters[parameter];
      if (!parameterConfig) {{
        throw new Error('Unknown parameter: ' + parameter);
      }}

      // Check preconditions
      var preErrors = checkPreconditions(parameterConfig);
      if (preErrors.length > 0) {{
        resolve(normalizeError(parameter, {{ name: 'PreconditionError', message: preErrors.join('; ') }}));
        return;
      }}

      var fn = resolveEntrypoint(parameterConfig);
      if (typeof fn !== 'function') {{
        throw new Error('Entrypoint is not callable for parameter: ' + parameter);
      }}

      var ctx = resolveThis(parameterConfig);
      var args = Array.isArray(payload.args) ? payload.args.map(coerceArg) : [coerceArg(payload.value)];

      // Resolve DOM-dependent args from preconditions.selectors
      var inv = parameterConfig.invocation || {{}};
      var pre = inv.preconditions || {{}};
      if (pre.dom_required && Array.isArray(pre.selectors)) {{
        for (var si = 0; si < pre.selectors.length; si++) {{
          var el = document.querySelector(pre.selectors[si]);
          if (el) {{
            var domVal = el.value || el.textContent || el.innerText || '';
            if (domVal) args.push(domVal);
          }}
        }}
      }}

      var result = fn.apply(ctx, args);

      // Try handling as Promise (covers async crypto, Webpack async imports, etc.)
      if (handleResult(resolve, parameter, result)) return;

      resolve(result);
    }} catch (error) {{
      resolve(normalizeError(activeParameter, error));
    }}
  }});
}})();
"""


def main() -> int:
    args = parse_args()
    analysis = load_json(args.analysis)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_script(analysis), encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
