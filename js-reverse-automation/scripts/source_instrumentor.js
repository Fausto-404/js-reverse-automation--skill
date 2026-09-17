#!/usr/bin/env node
"use strict";

/**
 * Conservative source-level property instrumentation.
 *
 * This tool intentionally rewrites only explicitly selected member reads such
 * as navigator.webdriver, document.cookie,
 * document.getElementById("username").value, or
 * document["getElementById"]("username")["value"]. It skips strings,
 * comments, assignments, and calls so it can be used as a low-risk first tap
 * before broader AST instrumentation is introduced.
 *
 * Usage:
 *   node scripts/source_instrumentor.js --input bundle.js --output bundle.tap.js \
 *     --properties webdriver,userAgent,cookie --objects navigator,document
 */

const fs = require("fs");
const path = require("path");

function parseArgs() {
  const result = {};
  for (let i = 2; i < process.argv.length; i += 2) {
    const key = process.argv[i];
    if (!key.startsWith("--")) throw new Error(`invalid option: ${key}`);
    result[key.slice(2)] = process.argv[i + 1];
  }
  if (!result.input || !result.output || !result.properties)
    throw new Error("Usage: source_instrumentor.js --input FILE --output FILE --properties name[,name]");
  return result;
}

function maskStringsAndComments(code) {
  const chars = code.split("");
  let state = "code";
  let quote = "";
  for (let i = 0; i < code.length; i += 1) {
    const ch = code[i];
    const next = code[i + 1];
    if (state === "code") {
      if (ch === "/" && next === "/") { chars[i] = " "; chars[i + 1] = " "; i += 1; state = "line"; continue; }
      if (ch === "/" && next === "*") { chars[i] = " "; chars[i + 1] = " "; i += 1; state = "block"; continue; }
      if (ch === "'" || ch === '"' || ch === "`") { quote = ch; chars[i] = " "; state = "string"; }
      continue;
    }
    if (state === "line") {
      if (ch === "\n") state = "code"; else chars[i] = " ";
      continue;
    }
    if (state === "block") {
      if (ch === "*" && next === "/") { chars[i] = " "; chars[i + 1] = " "; i += 1; state = "code"; }
      else if (ch !== "\n") chars[i] = " ";
      continue;
    }
    if (state === "string") {
      if (ch === "\\") { chars[i] = " "; if (i + 1 < code.length) { if (code[i + 1] !== "\n") chars[i + 1] = " "; i += 1; } continue; }
      if (ch === quote) { chars[i] = " "; state = "code"; }
      else if (ch !== "\n") chars[i] = " ";
    }
  }
  return chars.join("");
}

function lineOf(code, offset) {
  return code.slice(0, offset).split("\n").length;
}

function instrument(code, options) {
  const objects = new Set((options.objects || "navigator,document,screen,window,location").split(",").map(x => x.trim()).filter(Boolean));
  const properties = new Set(options.properties.split(",").map(x => x.trim()).filter(Boolean));
  const masked = maskStringsAndComments(code);
  // Supports a simple dot/bracket chain with non-nested call arguments in the
  // middle. The final member is inspected separately so calls such as
  // CryptoJS.AES.encrypt(...) are not wrapped.
  const pattern = /\b([A-Za-z_$][\w$]*)\s*((?:(?:\.\s*[A-Za-z_$][\w$]*\s*(?:\([^()\n]*\))?)|(?:\[\s*["'][A-Za-z_$][\w$]*["']\s*\]\s*(?:\([^()\n]*\))?))+)/g;
  const edits = [];
  let match;
  while ((match = pattern.exec(code))) {
    // The matching pass runs on source so static bracket names remain visible;
    // reject starts that are actually inside a string/comment.
    if (masked[match.index] !== code[match.index]) continue;
    const objectName = match[1];
    const expression = code.slice(match.index, match.index + match[0].length).trim();
    const finalMember = /(?:\.\s*([A-Za-z_$][\w$]*)\s*(\([^()\n]*\))?|\[\s*["']([A-Za-z_$][\w$]*)["']\s*\]\s*(\([^()\n]*\))?)\s*$/.exec(expression);
    if (!finalMember) continue;
    const propertyName = finalMember[1] || finalMember[3];
    if (!objects.has(objectName) || !properties.has(propertyName)) continue;
    if (finalMember[2] || finalMember[4]) continue;
    const end = match.index + match[0].length;
    const tail = masked.slice(end).match(/^\s*/)[0].length;
    const next = masked[end + tail];
    const after = masked[end + tail + 1];
    if (next === "(" || (next === "=" && after !== "=" && after !== ">")) continue;
    if (expression.includes("__JSRA_TAP_GET__")) continue;
    const label = `${objectName}.${propertyName}`;
    edits.push({
      start: match.index,
      end,
      replacement: `__JSRA_TAP_GET__(() => (${expression}), ${JSON.stringify(label)}, ${JSON.stringify(options.tag || "source")})`,
      line: lineOf(code, match.index),
      property: label
    });
    if (edits.length >= Number(options.maxRewrites || 500)) break;
  }
  let output = code;
  for (const edit of edits.slice().reverse()) output = output.slice(0, edit.start) + edit.replacement + output.slice(edit.end);
  const bootstrap = `\n;(() => {\n  const g = globalThis;\n  if (g.__JSRA_TAPS__) g.__JSRA_TAPS__.installed = true;\n  else {\n    const state = g.__JSRA_TAPS__ = { probe_id: "source-tap", installed: true, events: [], max: 5000 };\n    g.__JSRA_TAP_GET__ = function(thunk, path, tag) {\n      try { const value = thunk(); state.events.push({ type: "tap_get", path, tag, value_type: typeof value, value_length: value == null ? 0 : String(value).length, timestamp: Date.now() }); if (state.events.length > state.max) state.events.shift(); return value; }\n      catch (error) { state.events.push({ type: "tap_get_err", path, tag, error: String(error), timestamp: Date.now() }); throw error; }\n    };\n  }\n})();\n`;
  return { output: bootstrap + output, edits, parser_mode: "conservative-member-read" };
}

function main() {
  const args = parseArgs();
  const code = fs.readFileSync(args.input, "utf8");
  const result = instrument(code, args);
  fs.mkdirSync(path.dirname(args.output), { recursive: true });
  fs.writeFileSync(args.output, result.output, "utf8");
  const reportPath = args.report || `${args.output}.report.json`;
  fs.writeFileSync(reportPath, JSON.stringify({
    input: path.resolve(args.input),
    output: path.resolve(args.output),
    parser_mode: result.parser_mode,
    rewrite_count: result.edits.length,
    edits: result.edits.map(({ replacement, ...edit }) => edit)
  }, null, 2) + "\n", "utf8");
  console.log(JSON.stringify({ status: "ok", parser_mode: result.parser_mode, rewrite_count: result.edits.length, output: args.output, report: reportPath }));
}

try { main(); }
catch (error) { console.error(String(error.stack || error)); process.exit(2); }
