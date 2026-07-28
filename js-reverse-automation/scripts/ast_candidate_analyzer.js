#!/usr/bin/env node
"use strict";

/**
 * Static AST candidate analyzer for JavaScript bundles.
 *
 * Parses JS files using Babel (with fallback regex parser) to find function
 * declarations matching crypto-related keywords.
 *
 * Usage:
 *   node scripts/ast_candidate_analyzer.js --input bundle.js --output artifacts/static_candidates.json
 */

const fs = require("fs");
const path = require("path");

let babelParser = null;
try { babelParser = require("@babel/parser"); } catch (_) {}

function args() {
  const out = {};
  for (let i = 2; i < process.argv.length; i += 2)
    out[process.argv[i].replace(/^--/, "")] = process.argv[i + 1];
  if (!out.input || !out.output)
    throw new Error("Usage: ast_candidate_analyzer.js --input bundle.js --output static_candidates.json");
  return out;
}

const KEYWORDS = /encrypt|decrypt|cipher|sign|hmac|digest|hash|rsa|aes|des|sm2|sm3|sm4|md5|sha|base64|crypto/i;

function sourceSnippet(code, start, end) {
  return code.slice(start || 0, Math.min(end || code.length, (start || 0) + 1200));
}

function locationFromOffset(code, offset) {
  const before = code.slice(0, offset);
  const lines = before.split("\n");
  return { line: lines.length, column: lines[lines.length - 1].length };
}

function signalsFor(name, snippet) {
  const signals = [];
  if (KEYWORDS.test(name)) signals.push("name_keyword");
  if (KEYWORDS.test(snippet)) signals.push("source_keyword");
  if (/crypto\.subtle|CryptoJS|JSEncrypt|sm-crypto|jsrsasign|forge/i.test(snippet))
    signals.push("known_library");
  if (/publicKey|privateKey|BEGIN PUBLIC KEY|BEGIN RSA/i.test(snippet))
    signals.push("key_material");
  return signals;
}

function addCandidate(map, code, name, start, end, mode) {
  const snippet = sourceSnippet(code, start, end);
  const signals = signalsFor(name, snippet);
  if (!signals.length) return;
  const loc = locationFromOffset(code, start);
  const key = `${name}:${loc.line}:${loc.column}`;
  map.set(key, {
    id: `static:${key}`, name, path: name, type: "function",
    location: loc, signals, source_snippet: snippet, parser_mode: mode
  });
}

function walk(node, parent, visit) {
  if (!node || typeof node !== "object") return;
  if (typeof node.type === "string") visit(node, parent);
  for (const [key, value] of Object.entries(node)) {
    if (["loc", "start", "end", "extra", "tokens", "comments"].includes(key)) continue;
    if (Array.isArray(value)) value.forEach(child => walk(child, node, visit));
    else if (value && typeof value === "object") walk(value, node, visit);
  }
}

function nameOf(node, parent) {
  if (node.id && node.id.name) return node.id.name;
  if (parent && parent.type === "VariableDeclarator" && parent.id && parent.id.name)
    return parent.id.name;
  if (parent && /ObjectProperty|ObjectMethod|ClassMethod/.test(parent.type || ""))
    return parent.key && (parent.key.name || parent.key.value) || "anonymous";
  return "anonymous";
}

function analyzeWithBabel(code, map) {
  const ast = babelParser.parse(code, {
    sourceType: "unambiguous",
    errorRecovery: true,
    plugins: ["jsx", "typescript", "classProperties", "optionalChaining", "dynamicImport", "decorators-legacy"]
  });
  walk(ast, null, (node, parent) => {
    if (!["FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression",
          "ObjectMethod", "ClassMethod"].includes(node.type)) return;
    addCandidate(map, code, nameOf(node, parent), node.start, node.end, "babel");
  });
}

function analyzeFallback(code, map) {
  const patterns = [
    /function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{/g,
    /(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function\s*)?\([^)]*\)\s*=>?\s*\{/g,
    /([A-Za-z_$][\w$]*)\s*:\s*(?:async\s*)?function\s*\([^)]*\)\s*\{/g
  ];
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(code)))
      addCandidate(map, code, match[1], match.index, Math.min(code.length, match.index + 3000), "fallback-regex");
  }
}

function main() {
  const opt = args();
  const code = fs.readFileSync(opt.input, "utf8");
  const map = new Map();

  if (babelParser) analyzeWithBabel(code, map);
  else analyzeFallback(code, map);

  const result = {
    version: "2.1.0",
    input: path.resolve(opt.input),
    parser_mode: babelParser ? "babel" : "fallback-regex",
    candidates: Array.from(map.values())
  };

  fs.mkdirSync(path.dirname(opt.output), { recursive: true });
  fs.writeFileSync(opt.output, JSON.stringify(result, null, 2) + "\n");
  console.log(JSON.stringify({
    status: "ok",
    parser_mode: result.parser_mode,
    candidates: result.candidates.length,
    output: opt.output
  }));
}

try { main(); }
catch (error) { console.error(String(error.stack || error)); process.exit(2); }
