#!/usr/bin/env python3
"""Emit/apply differential verification artifacts.

Two subcommands:
  emit  — Generate a JS verification script that calls candidate functions with
          test samples and compares output fingerprints against captured request
          field expectations.
  apply — Merge verification results back into candidates, promoting to
          verified=true only when actual sample matches succeed.

Usage:
  python3 scripts/differential_verifier.py emit \
    --analysis analysis_result.json \
    --candidates artifacts/encryption_candidates.json \
    --output generated/differential_verifier.js \
    --plan-output artifacts/differential_plan.json

  python3 scripts/differential_verifier.py apply \
    --candidates artifacts/encryption_candidates.json \
    --results artifacts/differential_verification_results.json \
    --output artifacts/encryption_candidates.verified.json \
    --minimum-matches 2
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import dump_json, load_json

JS_TEMPLATE = r'''(() => {
  "use strict";
  const plan = __PLAN__;
  const results = [];

  function resolvePath(path) {
    if (!path) return null;
    if (path.startsWith("webpack:")) {
      const parts = path.split(":");
      let source = "default", moduleId, exportPath;
      if (parts.length >= 4) {
        source = parts[1]; moduleId = parts[2]; exportPath = parts.slice(3).join(":");
      } else {
        moduleId = parts[1]; exportPath = parts.slice(2).join(":");
      }
      const req = (window.__JSRA_WEBPACK_REQUIRE_MAP__ &&
                   window.__JSRA_WEBPACK_REQUIRE_MAP__[source]) ||
                  window.__JSRA_WEBPACK_REQUIRE__;
      if (!req || !req.c || !req.c[moduleId]) return null;
      let value = req.c[moduleId].exports;
      for (const part of (exportPath || "default").split(".")) {
        if (part === "default" && value && value.default !== undefined) value = value.default;
        else if (part) value = value && value[part];
      }
      return value;
    }
    const normalized = path.replace(/^window\./, "");
    return normalized.split(".").reduce((obj, key) => obj && obj[key], window);
  }

  async function fp(value) {
    const text = typeof value === "string" ? value : JSON.stringify(value);
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return "sha256:" + Array.from(new Uint8Array(digest))
      .map(b => b.toString(16).padStart(2, "0")).join("");
  }

  async function run() {
    for (const item of plan.items) {
      if (!item.safe_to_invoke) {
        results.push({
          candidate_id: item.candidate_id, verified: false,
          skipped: true, reason: "safe_to_invoke is false"
        });
        continue;
      }
      const fn = resolvePath(item.path);
      if (typeof fn !== "function") {
        results.push({
          candidate_id: item.candidate_id, verified: false,
          reason: "candidate not resolvable", tests: []
        });
        continue;
      }
      const tests = [];
      for (const sample of item.samples) {
        try {
          const output = await fn(sample);
          const output_fingerprint = await fp(output);
          const expected = item.expected_fingerprints[String(sample)] || null;
          const matched = Boolean(expected && expected === output_fingerprint);
          tests.push({
            input: sample,
            output_fingerprint,
            output_preview: String(output).slice(0, 96),
            expected_fingerprint: expected,
            matched,
            expectation_source: expected ? "captured_request_field" : "missing_expectation"
          });
        } catch (error) {
          tests.push({ input: sample, error: String(error), matched: false });
        }
      }
      const matched = tests.filter(test => test.matched === true).length;
      results.push({
        candidate_id: item.candidate_id, path: item.path,
        verified: matched >= item.minimum_matches,
        matched, tests
      });
    }
    window.__JSRA_VERIFICATION_RESULTS__ = {
      version: "2.1.0", generatedAt: Date.now(), results
    };
    return window.__JSRA_VERIFICATION_RESULTS__;
  }
  return run();
})();
'''


def build_plan(analysis: dict, candidates: dict) -> dict:
    """Build a verification plan from analysis transforms and candidates."""
    transforms = analysis.get("transforms") or []
    by_path = {c.get("path"): c for c in candidates.get("candidates", []) if c.get("path")}
    by_name = {c.get("name"): c for c in candidates.get("candidates", []) if c.get("name")}
    samples = analysis.get("verification", {}).get("samples") or ["JSRA_TEST_A", "JSRA_TEST_B"]
    expected_by_sample = analysis.get("verification", {}).get("expected_fingerprints", {})
    items = []
    for transform in transforms:
        path = transform.get("candidate_path")
        candidate = by_path.get(path) or by_name.get(path)
        if candidate is None and path:
            candidate = {"id": f"configured:{path}", "path": path}
        if candidate:
            items.append({
                "candidate_id": candidate.get("id"),
                "transform_id": transform.get("id"),
                "path": path or candidate.get("path"),
                "safe_to_invoke": bool(transform.get("safe_to_invoke")),
                "samples": samples,
                "minimum_matches": int(analysis.get("verification", {}).get("minimum_matches", 1)),
                "expected_fingerprints": (
                    transform.get("expected_fingerprints", {}) or expected_by_sample
                )
            })
    return {"version": "2.1.0", "items": items}


def emit(args: argparse.Namespace) -> int:
    """Emit a differential verification JS script."""
    analysis = load_json(args.analysis)
    candidates = load_json(args.candidates)
    plan = build_plan(analysis, candidates)
    content = JS_TEMPLATE.replace("__PLAN__", json.dumps(plan, ensure_ascii=False))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if args.plan_output:
        dump_json(args.plan_output, plan)
    print(f"[OK] verifier emitted: {path}; items={len(plan['items'])}")
    return 0


def apply(args: argparse.Namespace) -> int:
    """Apply verification results back into candidates."""
    candidates = load_json(args.candidates)
    results = load_json(args.results)
    by_id = {r.get("candidate_id"): r for r in results.get("results", [])}
    minimum = args.minimum_matches
    for candidate in candidates.get("candidates", []):
        result = by_id.get(candidate.get("id"))
        if not result:
            continue
        matched = sum(test.get("matched") is True for test in result.get("tests", []))
        candidate.setdefault("verification", []).append(result)
        candidate.setdefault("evidence", []).append({
            "type": "verification", "mode": "active_differential", "matched": matched
        })
        # Only actual sample matches can promote to verified
        if matched >= minimum and result.get("verified") is True:
            candidate["verified"] = True
            candidate.setdefault("scores", {})["verification"] = 1.0
            candidate["total_score"] = round(min(1.0, candidate.get("total_score", 0) + .12), 3)
            candidate["confidence"] = "high" if candidate["total_score"] >= .62 else "medium"
    dump_json(args.output, candidates)
    print(f"[OK] verification results applied: {args.output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit/apply differential verification artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_emit = sub.add_parser("emit", help="Emit verification JS script.")
    p_emit.add_argument("--analysis", required=True)
    p_emit.add_argument("--candidates", required=True)
    p_emit.add_argument("--output", required=True)
    p_emit.add_argument("--plan-output", help="Optional path to dump the plan JSON.")

    p_apply = sub.add_parser("apply", help="Apply verification results to candidates.")
    p_apply.add_argument("--candidates", required=True)
    p_apply.add_argument("--results", required=True)
    p_apply.add_argument("--output", required=True)
    p_apply.add_argument("--minimum-matches", type=int, default=2)

    args = parser.parse_args()
    return emit(args) if args.command == "emit" else apply(args)


if __name__ == "__main__":
    raise SystemExit(main())
