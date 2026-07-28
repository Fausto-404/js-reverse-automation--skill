#!/usr/bin/env python3
"""Write a fail-closed report when runtime evidence is incomplete.

Usage:
  python3 scripts/quarantine.py \
    --analysis artifacts/analysis_result.json \
    --candidates artifacts/encryption_candidates.json \
    --probe artifacts/probe_dump.json \
    --module artifacts/module_dump.json \
    --graph artifacts/evidence_graph.json \
    --differential artifacts/differential_verification_results.json \
    --output artifacts/quarantine.json
"""
from __future__ import annotations

import argparse
from pathlib import Path

from common import dump_json, load_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a JSRA quarantine report.")
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--candidates", required=False)
    parser.add_argument("--probe", required=False)
    parser.add_argument("--module", required=False)
    parser.add_argument("--graph", required=False)
    parser.add_argument("--differential", required=False)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    paths = {
        "analysis": args.analysis,
        "candidates": args.candidates,
        "probe_dump": args.probe,
        "module_dump": args.module,
        "evidence_graph": args.graph,
        "differential_verification": args.differential,
    }
    missing = [name for name, value in paths.items() if not value or not Path(value).exists()]

    candidates = load_json(args.candidates, {}) if args.candidates else {}
    unresolved = []
    for candidate in candidates.get("candidates", []) if isinstance(candidates, dict) else []:
        if candidate.get("verified") is not True:
            unresolved.append(candidate.get("path") or candidate.get("id"))
        elif not candidate.get("verification"):
            unresolved.append(candidate.get("path") or candidate.get("id"))

    report = {
        "version": "2.1.0",
        "status": "quarantined" if missing or unresolved else "ready_for_validation",
        "missing_artifacts": missing,
        "unverified_candidates": [value for value in unresolved if value],
        "reason": "No Burp-ready artifact may be issued until a real page function is invoked and correlated with a target request field.",
        "next_actions": [
            "Inject runtime_hook_probe.js before navigation and export probe_dump.json.",
            "Inject module_probe.js when the entrypoint is bundled and export module_dump.json.",
            "Build evidence_graph.json from the captured events.",
            "Run differential_verifier emit/apply using captured request-field expectations.",
            "Regenerate JSRPC, Flask, and Burp artifacts only after validation passes.",
        ],
    }
    dump_json(args.output, report)
    print(f"[OK] quarantine report: {args.output}")
    return 0 if report["status"] == "ready_for_validation" else 2


if __name__ == "__main__":
    raise SystemExit(main())
