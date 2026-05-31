#!/usr/bin/env python3
"""Generate a runtime hook probe JS file for tracing fetch/XHR/crypto/serializers.

The probe writes evidence to window.__JSRA_TRACE__ and can be injected via
navigate_page(initScript=...) or evaluate_script.

Usage:
  python3 scripts/emit_runtime_hook_probe.py --output generated/runtime_hook_probe.js
  python3 scripts/emit_runtime_hook_probe.py --output generated/runtime_hook_probe.js --params "password,sign,token"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Output JS file path.")
    parser.add_argument("--params", default="", help="Comma-separated target parameter names to watch.")
    return parser.parse_args()


def build_probe(target_params: list[str]) -> str:
    params_json = json.dumps(target_params, ensure_ascii=False)
    return f"""// emit_runtime_hook_probe.py
// Runtime Hook Probe v1 — soft breakpoint tracing
(function() {{
  'use strict';

  if (window.__JSRA_TRACE__) return; // avoid double-install

  var TARGET_PARAMS = {params_json};
  var SENSITIVE_KEYS = ['sign', 'token', 'enc', 'password', 'signature', 'hash', 'key', 'nonce', 'timestamp', 'ts', 'data', 'encrypt', 'decrypt'];
  var ALL_WATCHED = TARGET_PARAMS.concat(SENSITIVE_KEYS);

  function safeString(v, maxLen) {{
    maxLen = maxLen || 500;
    if (v === null || v === undefined) return String(v);
    if (v instanceof ArrayBuffer) return '[ArrayBuffer:' + v.byteLength + ']';
    if (v instanceof Uint8Array) return '[Uint8Array:' + v.length + ']';
    if (v instanceof Blob) return '[Blob:' + v.size + ']';
    if (typeof v === 'object') {{
      try {{ var s = JSON.stringify(v); return s.length > maxLen ? s.substring(0, maxLen) + '...' : s; }}
      catch(e) {{ return '[Object]'; }}
    }}
    var s = String(v);
    return s.length > maxLen ? s.substring(0, maxLen) + '...' : s;
  }}

  function getStack(skip) {{
    skip = skip || 0;
    try {{ throw new Error(); }} catch(e) {{
      var lines = e.stack.split('\\n').slice(2 + skip);
      return lines.slice(0, 10).map(function(l) {{ return l.trim(); }});
    }}
  }}

  function hasWatchedKey(obj) {{
    if (!obj || typeof obj !== 'object') return false;
    var keys = Object.keys(obj);
    for (var i = 0; i < keys.length; i++) {{
      var k = keys[i].toLowerCase();
      for (var j = 0; j < ALL_WATCHED.length; j++) {{
        if (k.indexOf(ALL_WATCHED[j].toLowerCase()) !== -1) return true;
      }}
    }}
    return false;
  }}

  function summarizeHeaders(headers) {{
    if (!headers) return null;
    var result = {{}};
    if (headers instanceof Headers) {{
      headers.forEach(function(v, k) {{ result[k] = v.length > 200 ? v.substring(0, 200) + '...' : v; }});
    }} else if (typeof headers === 'object') {{
      Object.keys(headers).forEach(function(k) {{
        var v = String(headers[k]);
        result[k] = v.length > 200 ? v.substring(0, 200) + '...' : v;
      }});
    }}
    return result;
  }}

  var trace = window.__JSRA_TRACE__ = {{
    version: 'runtime-hook-v1',
    installedAt: Date.now(),
    requests: [],
    calls: [],
    crypto: [],
    serializers: [],
    errors: [],
    dump: function() {{
      return JSON.stringify({{
        version: this.version,
        installedAt: this.installedAt,
        requests: this.requests,
        calls: this.calls,
        crypto: this.crypto,
        serializers: this.serializers,
        errors: this.errors
      }});
    }},
    clear: function() {{
      this.requests = [];
      this.calls = [];
      this.crypto = [];
      this.serializers = [];
      this.errors = [];
    }}
  }};

  // === 1. Hook window.fetch ===
  var origFetch = window.fetch;
  window.fetch = function(input, init) {{
    try {{
      var url = typeof input === 'string' ? input : (input instanceof Request ? input.url : (input && input.toString ? input.toString() : 'unknown'));
      var method = (init && init.method) || (input instanceof Request ? input.method : 'GET');
      var body = (init && init.body) || (input instanceof Request ? 'Request<body>' : null);
      trace.requests.push({{
        type: 'fetch',
        url: url,
        method: method,
        headers: summarizeHeaders(init && init.headers),
        bodySnippet: safeString(body),
        timestamp: Date.now(),
        stack: getStack(1)
      }});
    }} catch(e) {{ trace.errors.push({{ hook: 'fetch', error: e.message }}); }}
    return origFetch.apply(this, arguments);
  }};

  // === 2. Hook XMLHttpRequest ===
  var origXHROpen = XMLHttpRequest.prototype.open;
  var origXHRSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function(method, url) {{
    this.__jsra = {{ method: method, url: url }};
    return origXHROpen.apply(this, arguments);
  }};

  XMLHttpRequest.prototype.send = function(body) {{
    try {{
      var info = this.__jsra || {{}};
      trace.requests.push({{
        type: 'xhr',
        url: info.url || 'unknown',
        method: info.method || 'unknown',
        bodySnippet: safeString(body),
        timestamp: Date.now(),
        stack: getStack(1)
      }});
    }} catch(e) {{ trace.errors.push({{ hook: 'xhr.send', error: e.message }}); }}
    return origXHRSend.apply(this, arguments);
  }};

  // === 3. Hook FormData ===
  var origFDAppend = FormData.prototype.append;
  var origFDSet = FormData.prototype.set;

  FormData.prototype.append = function(name, value) {{
    try {{
      trace.serializers.push({{
        type: 'FormData.append',
        name: name,
        valueType: typeof value,
        valueLen: value && value.length ? value.length : (value instanceof Blob ? value.size : null),
        timestamp: Date.now()
      }});
    }} catch(e) {{}}
    return origFDAppend.apply(this, arguments);
  }};

  FormData.prototype.set = function(name, value) {{
    try {{
      trace.serializers.push({{
        type: 'FormData.set',
        name: name,
        valueType: typeof value,
        timestamp: Date.now()
      }});
    }} catch(e) {{}}
    return origFDSet.apply(this, arguments);
  }};

  // === 4. Hook URLSearchParams ===
  var origUSPAppend = URLSearchParams.prototype.append;
  var origUSPSet = URLSearchParams.prototype.set;
  var origUSPToString = URLSearchParams.prototype.toString;

  URLSearchParams.prototype.append = function(name, value) {{
    try {{
      trace.serializers.push({{
        type: 'URLSearchParams.append',
        name: name,
        valueSnippet: safeString(value, 200),
        timestamp: Date.now()
      }});
    }} catch(e) {{}}
    return origUSPAppend.apply(this, arguments);
  }};

  URLSearchParams.prototype.set = function(name, value) {{
    try {{
      trace.serializers.push({{
        type: 'URLSearchParams.set',
        name: name,
        valueSnippet: safeString(value, 200),
        timestamp: Date.now()
      }});
    }} catch(e) {{}}
    return origUSPSet.apply(this, arguments);
  }};

  URLSearchParams.prototype.toString = function() {{
    try {{
      var result = origUSPToString.apply(this, arguments);
      trace.serializers.push({{
        type: 'URLSearchParams.toString',
        resultSnippet: safeString(result, 500),
        timestamp: Date.now(),
        stack: getStack(1)
      }});
      return result;
    }} catch(e) {{ return origUSPToString.apply(this, arguments); }}
  }};

  // === 5. Hook JSON.stringify (selective) ===
  var origJSONStringify = JSON.stringify;
  JSON.stringify = function(value) {{
    try {{
      if (value && typeof value === 'object' && hasWatchedKey(value)) {{
        trace.serializers.push({{
          type: 'JSON.stringify',
          keys: Object.keys(value).slice(0, 20),
          snippet: safeString(value, 300),
          timestamp: Date.now(),
          stack: getStack(1)
        }});
      }}
    }} catch(e) {{}}
    return origJSONStringify.apply(this, arguments);
  }};

  // === 6. Hook crypto.subtle ===
  if (window.crypto && window.crypto.subtle) {{
    var origDigest = crypto.subtle.digest.bind(crypto.subtle);
    var origSign = crypto.subtle.sign ? crypto.subtle.sign.bind(crypto.subtle) : null;
    var origEncrypt = crypto.subtle.encrypt ? crypto.subtle.encrypt.bind(crypto.subtle) : null;
    var origDecrypt = crypto.subtle.decrypt ? crypto.subtle.decrypt.bind(crypto.subtle) : null;

    crypto.subtle.digest = function(algorithm, data) {{
      var entry = {{
        type: 'digest',
        algorithm: typeof algorithm === 'string' ? algorithm : algorithm.name,
        inputLen: data ? data.byteLength || data.length : 0,
        timestamp: Date.now(),
        stack: getStack(1)
      }};
      trace.crypto.push(entry);
      return origDigest(algorithm, data).then(function(hash) {{
        entry.outputLen = hash.byteLength;
        entry.outputHex = Array.from(new Uint8Array(hash)).map(function(b) {{ return b.toString(16).padStart(2, '0'); }}).join('').substring(0, 32) + '...';
        return hash;
      }});
    }};

    if (origSign) {{
      crypto.subtle.sign = function(algorithm, key, data) {{
        var entry = {{
          type: 'sign',
          algorithm: typeof algorithm === 'string' ? algorithm : algorithm.name,
          inputLen: data ? data.byteLength || data.length : 0,
          timestamp: Date.now(),
          stack: getStack(1)
        }};
        trace.crypto.push(entry);
        return origSign(algorithm, key, data).then(function(sig) {{
          entry.outputLen = sig.byteLength;
          return sig;
        }});
      }};
    }}

    if (origEncrypt) {{
      crypto.subtle.encrypt = function(algorithm, key, data) {{
        var entry = {{
          type: 'encrypt',
          algorithm: typeof algorithm === 'string' ? algorithm : algorithm.name,
          inputLen: data ? data.byteLength || data.length : 0,
          timestamp: Date.now(),
          stack: getStack(1)
        }};
        trace.crypto.push(entry);
        return origEncrypt(algorithm, key, data).then(function(enc) {{
          entry.outputLen = enc.byteLength;
          return enc;
        }});
      }};
    }}

    if (origDecrypt) {{
      crypto.subtle.decrypt = function(algorithm, key, data) {{
        var entry = {{
          type: 'decrypt',
          algorithm: typeof algorithm === 'string' ? algorithm : algorithm.name,
          inputLen: data ? data.byteLength || data.length : 0,
          timestamp: Date.now(),
          stack: getStack(1)
        }};
        trace.crypto.push(entry);
        return origDecrypt(algorithm, key, data).then(function(dec) {{
          entry.outputLen = dec.byteLength;
          return dec;
        }});
      }};
    }}
  }}

  console.log('[JSRA] Runtime hook probe v1 installed, watching: ' + ALL_WATCHED.join(', '));
}})();
"""


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    target_params = [p.strip() for p in args.params.split(",") if p.strip()]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_probe(target_params), encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(output_path), "target_params": target_params}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
