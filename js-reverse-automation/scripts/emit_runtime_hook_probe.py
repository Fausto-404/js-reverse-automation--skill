#!/usr/bin/env python3
"""Generate a runtime hook probe JS file for tracing fetch/XHR/crypto/serializers.

The probe writes evidence to window.__JSRA_TRACE__ using a unified event model
with event_id, trace_id, parent_event_id, input_fingerprint, output_fingerprint.
Supports SHA-256 fingerprinting and sensitive field redaction.

Usage:
  python3 scripts/emit_runtime_hook_probe.py --output generated/runtime_hook_probe.js
  python3 scripts/emit_runtime_hook_probe.py --output generated/runtime_hook_probe.js --max-events 5000
  python3 scripts/emit_runtime_hook_probe.py --output generated/runtime_hook_probe.js --capture-raw
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


HOOK_REGISTRY = (Path(__file__).with_name("hook_registry.js")).read_text(encoding="utf-8")

TEMPLATE = r'''(() => {
  "use strict";
  const PROBE_ID = "runtime-hook";
  const CONFIG = __CONFIG__;
  const root = window;
__HOOK_REGISTRY__
  const registry = getHookRegistry(root);
  if (window.__JSRA_TRACE__ && window.__JSRA_TRACE__.probe_id === PROBE_ID) {
    return window.__JSRA_TRACE__;
  }

  const sensitive = /pass(word)?|token|secret|authorization|cookie|session|credential/i;
  const nativeJSONStringify = JSON.stringify.bind(JSON);
  const nativeDigest = window.crypto && crypto.subtle
    ? registry.native(crypto.subtle, "digest").bind(crypto.subtle) : null;
  const nativeTextEncode = window.TextEncoder
    ? registry.native(TextEncoder.prototype, "encode") : null;
  const state = { probe_id: PROBE_ID, installedAt: Date.now(), events: [], maxEvents: CONFIG.maxEvents, dropped: 0 };
  let eventCounter = 0;
  let activeTraceId = null;
  let libraryTimer = null;
  const runtimeLayers = [];
  let originalRequest = null;

  function uuid(prefix) {
    eventCounter += 1;
    return `${prefix}-${Date.now().toString(36)}-${eventCounter.toString(36)}`;
  }
  function stack() {
    try { return String(new Error().stack || "").split("\n").slice(2, 14); } catch (_) { return []; }
  }
  function stableString(value) {
    try {
      if (typeof value === "string") return value;
      if (value instanceof ArrayBuffer) return Array.from(new Uint8Array(value)).join(",");
      if (ArrayBuffer.isView(value))
        return Array.from(new Uint8Array(value.buffer, value.byteOffset, value.byteLength)).join(",");
      return nativeJSONStringify(value);
    } catch (_) { return String(value); }
  }
  function safeClone(value, depth = 0, seen = new WeakSet()) {
    if (value === null || value === undefined) return value;
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return value;
    if (typeof value === "bigint") return `${value}n`;
    if (typeof value === "function") return "[function]";
    if (value instanceof ArrayBuffer) return `[ArrayBuffer:${value.byteLength}]`;
    if (ArrayBuffer.isView(value)) return `[${value.constructor.name}:${value.byteLength}]`;
    if (depth >= 4) return "[MaxDepth]";
    if (seen.has(value)) return "[Circular]";
    seen.add(value);
    if (Array.isArray(value)) return value.slice(0, 32).map(item => safeClone(item, depth + 1, seen));
    const output = {};
    for (const key of Object.keys(value).slice(0, 32)) {
      if (sensitive.test(key)) output[key] = "<redacted>";
      else {
        try { output[key] = safeClone(value[key], depth + 1, seen); }
        catch (_) { output[key] = "[Unreadable]"; }
      }
    }
    return output;
  }
  async function sha256(value) {
    try {
      if (!nativeDigest || !nativeTextEncode) return null;
      const data = nativeTextEncode.call(new TextEncoder(), stableString(value));
      const digest = await nativeDigest("SHA-256", data);
      return "sha256:" + Array.from(new Uint8Array(digest))
        .map(b => b.toString(16).padStart(2, "0")).join("");
    } catch (_) { return null; }
  }
  function preview(value, key = "") {
    if (sensitive.test(key)) return "<redacted>";
    if (CONFIG.captureRaw) return safeClone(value);
    // JSON.stringify(undefined) returns undefined.  Normalise it before
    // measuring/slicing so an optional crypto or WebSocket argument cannot
    // abort the entire target page.
    const text = String(stableString(value) ?? "");
    return text.length > 96 ? text.slice(0, 96) + "…" : text;
  }
  async function record(type, detail = {}, parentEventId = null) {
    const event = {
      event_id: uuid("evt"),
      trace_id: detail.trace_id || activeTraceId || uuid("trace"),
      parent_event_id: parentEventId,
      type,
      function: detail.function || null,
      url: detail.url || null,
      input_preview: preview(detail.input, detail.key || ""),
      output_preview: preview(detail.output, detail.key || ""),
      input_fingerprint: detail.hasOwnProperty("input") ? await sha256(detail.input) : null,
      output_fingerprint: detail.hasOwnProperty("output") ? await sha256(detail.output) : null,
      stack: detail.stack || stack(),
      metadata: detail.metadata || {},
      timestamp: Date.now()
    };
    state.events.push(event);
    if (state.events.length > state.maxEvents) {
      state.events.splice(0, state.events.length - state.maxEvents);
      state.dropped += 1;
    }
    return event;
  }
  async function recordFields(traceId, body, parentEventId) {
    let parsed = null;
    if (body == null) return;
    try {
      if (typeof body === "string") {
        const trimmed = body.trim();
        if (trimmed.startsWith("{") || trimmed.startsWith("["))
          parsed = JSON.parse(trimmed);
        else
          parsed = Object.fromEntries(new URLSearchParams(body).entries());
      } else if (body instanceof URLSearchParams) {
        parsed = Object.fromEntries(body.entries());
      } else if (typeof body === "object" && !(body instanceof ArrayBuffer) && !ArrayBuffer.isView(body)) {
        parsed = body;
      }
    } catch (_) { parsed = null; }
    async function walk(value, path, depth) {
      if (depth > 4) return;
      if (value && typeof value === "object") {
        const entries = Array.isArray(value) ? value.entries() : Object.entries(value);
        for (const [key, child] of entries)
          await walk(child, path ? `${path}.${key}` : String(key), depth + 1);
      } else {
        await record("network.field", {
          trace_id: traceId, function: "request-field",
          input: value, key: path, metadata: { path }
        }, parentEventId);
      }
    }
    if (parsed !== null) await walk(parsed, "$", 0);
  }
  function addRuntimeLayer(target, key, id, factory) {
    const layer = registry.add(target, key, id, factory);
    if (layer && !layer.duplicate) runtimeLayers.push({ target, key, id });
    return layer;
  }
  function wrapMethod(target, key, type, name, options = {}) {
    if (!target || typeof target[key] !== "function") return;
    addRuntimeLayer(target, key, `runtime:${name}`, original => {
      const wrapped = function(...args) {
      if (registry.internalDepth > 0) return original.apply(this, args);
      if (typeof options.skip === "function" && options.skip.call(this, args))
        return original.apply(this, args);
      const traceId = activeTraceId || uuid("trace");
      activeTraceId = traceId;
      let result;
      try { result = original.apply(this, args); }
      catch (error) {
        record(type + ".error", { trace_id: traceId, function: name, input: args, output: String(error) });
        throw error;
      }
      if (result && typeof result.then === "function") {
        return result.then(value => {
          record(type, { trace_id: traceId, function: name, input: args, output: value });
          return value;
        });
      }
      record(type, { trace_id: traceId, function: name, input: args, output: result });
      return result;
      };
      Object.defineProperty(wrapped, "__jsraWrapped", { value: true });
      return wrapped;
    });
  }

  // === Network hooks ===
  if (typeof window.fetch === "function") {
    addRuntimeLayer(window, "fetch", "runtime:network.fetch", original => async function(input, init = {}) {
      if (registry.internalDepth > 0) return original.apply(this, arguments);
      const traceId = uuid("trace"); activeTraceId = traceId;
      const url = typeof input === "string" ? input : input && input.url;
      const body = init.body || (input && input.body) || null;
      const networkEvent = await record("network.fetch", {
        trace_id: traceId, function: "fetch", url, input: body,
        metadata: { method: init.method || "GET" }
      });
      await recordFields(traceId, body, networkEvent.event_id);
      return original.apply(this, arguments);
    });
  }

  if (window.XMLHttpRequest) {
    addRuntimeLayer(XMLHttpRequest.prototype, "open", "runtime:network.xhr.open", original => function(method, url) {
      if (registry.internalDepth > 0) return original.apply(this, arguments);
      this.__jsra = { method, url }; return original.apply(this, arguments);
    });
    addRuntimeLayer(XMLHttpRequest.prototype, "send", "runtime:network.xhr.send", original => function(body) {
      if (registry.internalDepth > 0) return original.apply(this, arguments);
      const traceId = uuid("trace"); activeTraceId = traceId;
      record("network.xhr", {
        trace_id: traceId, function: "XMLHttpRequest.send",
        url: this.__jsra && this.__jsra.url, input: body,
        metadata: { method: this.__jsra && this.__jsra.method }
      }).then(event => recordFields(traceId, body, event.event_id));
      return original.apply(this, arguments);
    });
  }

  if (window.Request) {
    originalRequest = window.Request;
    window.Request = new Proxy(originalRequest, {
      construct(target, args, newTarget) {
        const instance = Reflect.construct(target, args, newTarget);
        record("network.request.construct", {
          function: "Request", url: instance.url,
          input: args[1] && args[1].body
        });
        return instance;
      }
    });
  }

  // === Serializer / encoding hooks ===
  if (window.WebSocket) wrapMethod(WebSocket.prototype, "send", "network.websocket", "WebSocket.send", {
    skip: function() {
      try {
        const url = String(this && this.url || "");
        return (CONFIG.controlWebSocketUrls || []).some(fragment => url.includes(fragment));
      } catch (_) { return false; }
    }
  });
  if (window.JSON) wrapMethod(JSON, "stringify", "serializer.json", "JSON.stringify");
  if (window.URLSearchParams)
    wrapMethod(URLSearchParams.prototype, "toString", "serializer.urlsearchparams", "URLSearchParams.toString");
  if (window.FormData) wrapMethod(FormData.prototype, "append", "serializer.formdata", "FormData.append");
  if (window.TextEncoder) wrapMethod(TextEncoder.prototype, "encode", "encoding.text", "TextEncoder.encode");
  if (window.TextDecoder) wrapMethod(TextDecoder.prototype, "decode", "encoding.text", "TextDecoder.decode");
  wrapMethod(window, "btoa", "encoding.base64", "btoa");
  wrapMethod(window, "atob", "encoding.base64", "atob");

  // === WebCrypto hooks ===
  if (window.crypto && crypto.subtle) {
    ["encrypt", "decrypt", "digest", "sign", "verify", "deriveBits", "deriveKey"].forEach(name => {
      wrapMethod(crypto.subtle, name, "crypto.webcrypto", `crypto.subtle.${name}`);
    });
  }

  // === Library hooks (CryptoJS, JSEncrypt, sm2/sm3/sm4) ===
  function installLibraryHooks() {
    try {
      if (window.CryptoJS) {
        ["AES", "DES", "TripleDES", "Rabbit", "RC4"].forEach(alg => {
          const obj = window.CryptoJS[alg];
          if (obj)
            ["encrypt", "decrypt"].forEach(op =>
              wrapMethod(obj, op, "crypto.cryptojs", `CryptoJS.${alg}.${op}`));
        });
        ["MD5", "SHA1", "SHA256", "SHA512", "HmacSHA256"].forEach(name =>
          wrapMethod(window.CryptoJS, name, "crypto.cryptojs", `CryptoJS.${name}`));
      }
      if (window.JSEncrypt && window.JSEncrypt.prototype) {
        ["encrypt", "decrypt", "sign", "verify"].forEach(op =>
          wrapMethod(window.JSEncrypt.prototype, op, "crypto.jsencrypt", `JSEncrypt.${op}`));
      }
      if (window.sm2)
        ["doEncrypt", "doDecrypt", "doSignature", "doVerifySignature"].forEach(op =>
          wrapMethod(window.sm2, op, "crypto.sm", `sm2.${op}`));
      if (window.sm3) wrapMethod(window, "sm3", "crypto.sm", "sm3");
      if (window.sm4)
        ["encrypt", "decrypt"].forEach(op =>
          wrapMethod(window.sm4, op, "crypto.sm", `sm4.${op}`));
    } catch (_) {}
  }
  installLibraryHooks();
  // Re-install periodically to catch late-loading libraries
  libraryTimer = setInterval(installLibraryHooks, 2000);

  // === Public API ===
  window.__JSRA_TRACE__ = {
    probe_id: PROBE_ID,
    state,
    markTrace(label = "manual") { activeTraceId = uuid(label); return activeTraceId; },
    clearTrace() { activeTraceId = null; },
    async record(type, detail) { return record(type, detail); },
    export() { return { probe_id: PROBE_ID, exportedAt: Date.now(), events: state.events.slice() }; },
    dump() { return nativeJSONStringify(this.export()); },
    uninstall() {
      if (libraryTimer) clearInterval(libraryTimer);
      for (const layer of runtimeLayers.slice().reverse()) registry.remove(layer.target, layer.key, layer.id);
      if (originalRequest) window.Request = originalRequest;
    }
  };
  console.info("[JSRA] runtime probe installed");
  return window.__JSRA_TRACE__;
})();
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit JSRA runtime hook probe.")
    parser.add_argument("--output", required=True, help="Output JS file path.")
    parser.add_argument("--max-events", type=int, default=3000, help="Max events to keep.")
    parser.add_argument("--capture-raw", action="store_true", help="Store raw values instead of previews.")
    parser.add_argument("--params", default="", help="Comma-separated target parameter names to watch (for documentation).")
    parser.add_argument("--control-websocket-url", action="append", default=[],
                        help="URL fragment for a JSRPC/control WebSocket to leave untouched.")
    args = parser.parse_args()

    control_urls = args.control_websocket_url or ["127.0.0.1:12080", "localhost:12080"]
    config = {"maxEvents": max(100, args.max_events), "captureRaw": bool(args.capture_raw),
              "controlWebSocketUrls": control_urls}
    # --params is retained for backward compatibility but not used in the probe
    # The probe watches all crypto-related activity automatically.
    if args.params:
        config["targetParams"] = [p.strip() for p in args.params.split(",") if p.strip()]
    content = TEMPLATE.replace("__CONFIG__", json.dumps(config))
    content = content.replace("__HOOK_REGISTRY__", HOOK_REGISTRY)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
