#!/usr/bin/env python3
"""Hook template generator.

Generates various hook templates for common browser APIs.

Usage:
  python3 scripts/hook_templates.py --type cookie --output generated/hooks/cookie.js
  python3 scripts/hook_templates.py --type all --output generated/hooks/
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


TEMPLATES = {
    "cookie": r'''
// Cookie Hook - Monitor document.cookie access
(function() {
  let _cookie = document.cookie;
  const originalDesc = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie');

  Object.defineProperty(document, 'cookie', {
    get: function() {
      console.log('[HOOK] cookie.get:', _cookie.substring(0, 100));
      return _cookie;
    },
    set: function(value) {
      console.log('[HOOK] cookie.set:', value.substring(0, 200));
      _cookie = value;
      if (originalDesc && originalDesc.set) {
        originalDesc.set.call(document, value);
      }
    },
    configurable: true
  });
  console.log('[HOOK] cookie hook installed');
})();
''',

    "xhr": r'''
// XMLHttpRequest Hook - Monitor XHR open/send
(function() {
  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function(method, url) {
    this.__hook = { method, url, timestamp: Date.now() };
    console.log('[HOOK] xhr.open:', method, url);
    return originalOpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function(body) {
    if (this.__hook) {
      this.__hook.body = body;
      console.log('[HOOK] xhr.send:', this.__hook.method, this.__hook.url,
        body ? body.substring(0, 200) : '(no body)');
    }
    return originalSend.apply(this, arguments);
  };
  console.log('[HOOK] xhr hook installed');
})();
''',

    "fetch": r'''
// Fetch Hook - Monitor fetch calls
(function() {
  const originalFetch = window.fetch;
  window.fetch = function(input, init) {
    const url = typeof input === 'string' ? input : input && input.url;
    const method = (init && init.method) || 'GET';
    const body = init && init.body;
    console.log('[HOOK] fetch:', method, url, body ? body.substring(0, 200) : '(no body)');
    return originalFetch.apply(this, arguments);
  };
  console.log('[HOOK] fetch hook installed');
})();
''',

    "eval": r'''
// Eval Hook - Monitor eval/Function calls
(function() {
  const originalEval = window.eval;
  const originalFunction = window.Function;

  window.eval = function(code) {
    console.log('[HOOK] eval:', typeof code === 'string' ? code.substring(0, 200) : typeof code);
    return originalEval.apply(this, arguments);
  };

  window.Function = function(...args) {
    console.log('[HOOK] new Function:', args.length, 'args');
    return originalFunction.apply(this, args);
  };
  console.log('[HOOK] eval hook installed');
})();
''',

    "json": r'''
// JSON Hook - Monitor JSON.parse/stringify
(function() {
  const originalParse = JSON.parse;
  const originalStringify = JSON.stringify;

  JSON.parse = function(text) {
    console.log('[HOOK] JSON.parse:', typeof text === 'string' ? text.substring(0, 200) : typeof text);
    return originalParse.apply(this, arguments);
  };

  JSON.stringify = function(value) {
    const result = originalStringify.apply(this, arguments);
    console.log('[HOOK] JSON.stringify:', result.substring(0, 200));
    return result;
  };
  console.log('[HOOK] json hook installed');
})();
''',

    "base64": r'''
// Base64 Hook - Monitor atob/btoa
(function() {
  const originalAtob = window.atob;
  const originalBtoa = window.btoa;

  window.atob = function(encoded) {
    console.log('[HOOK] atob:', encoded.substring(0, 100));
    return originalAtob.apply(this, arguments);
  };

  window.btoa = function(text) {
    console.log('[HOOK] btoa:', text.substring(0, 100));
    return originalBtoa.apply(this, arguments);
  };
  console.log('[HOOK] base64 hook installed');
})();
''',

    "websocket": r'''
// WebSocket Hook - Monitor WebSocket messages
(function() {
  const originalSend = WebSocket.prototype.send;

  WebSocket.prototype.send = function(data) {
    console.log('[HOOK] ws.send:', typeof data === 'string' ? data.substring(0, 200) : typeof data);
    return originalSend.apply(this, arguments);
  };
  console.log('[HOOK] websocket hook installed');
})();
''',

    "crypto": r'''
// Crypto Hook - Monitor crypto.subtle operations
(function() {
  if (!window.crypto || !window.crypto.subtle) return;

  const original = window.crypto.subtle;
  const methods = ['encrypt', 'decrypt', 'digest', 'sign', 'verify', 'generateKey', 'importKey', 'exportKey'];

  methods.forEach(method => {
    if (original[method]) {
      const originalMethod = original[method].bind(original);
      original[method] = function(...args) {
        console.log('[HOOK] crypto.subtle.' + method, args.length, 'args');
        return originalMethod.apply(this, args);
      };
    }
  });
  console.log('[HOOK] crypto hook installed');
})();
''',
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Hook template generator.")
    parser.add_argument("--type", required=True, choices=list(TEMPLATES.keys()) + ["all"],
                        help="Hook type to generate.")
    parser.add_argument("--output", required=True, help="Output file or directory.")
    args = parser.parse_args()

    output = Path(args.output)

    if args.type == "all":
        output.mkdir(parents=True, exist_ok=True)
        for name, template in TEMPLATES.items():
            (output / f"{name}.js").write_text(template.strip(), encoding="utf-8")
        print(f"[OK] all hooks written to {output}")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(TEMPLATES[args.type].strip(), encoding="utf-8")
        print(f"[OK] {args.type} hook written to {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
