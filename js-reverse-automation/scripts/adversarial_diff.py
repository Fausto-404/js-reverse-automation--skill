#!/usr/bin/env python3
"""Compare baseline and patched adversarial probe exports.

This turns an intervention into evidence: a patch is useful only when it
produces additional target signals or requests without increasing runtime
errors.  It does not claim that a page is bypassed; it reports observable
changes for the authorized test target.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from common import dump_json, load_json


def events(value: dict) -> list[dict]:
    state = value.get("state") if isinstance(value, dict) else {}
    raw = state.get("events", []) if isinstance(state, dict) else []
    return [item for item in raw if isinstance(item, dict)]


def summarize(items: list[dict]) -> dict:
    types = Counter(str(item.get("type", "unknown")) for item in items)
    paths = Counter(str(item.get("path")) for item in items if item.get("path"))
    return {
        "events": len(items),
        "types": dict(sorted(types.items())),
        "paths": dict(sorted(paths.items())),
        "requests": sum(count for name, count in types.items() if name.startswith("network.")),
        "errors": sum(count for name, count in types.items() if "error" in name or "reject" in name),
        "interventions": sum(count for name, count in types.items() if name.startswith("intervention.")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare JSRA adversarial probe exports.")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--patched", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    before = summarize(events(load_json(Path(args.baseline), {})))
    after = summarize(events(load_json(Path(args.patched), {})))
    new_types = sorted(set(after["types"]) - set(before["types"]))
    new_paths = sorted(set(after["paths"]) - set(before["paths"]))
    errors_not_increased = after["errors"] <= before["errors"]
    evidence_increased = after["events"] > before["events"] or after["requests"] > before["requests"]
    result = {
        "baseline": before,
        "patched": after,
        "delta": {
            "events": after["events"] - before["events"],
            "requests": after["requests"] - before["requests"],
            "errors": after["errors"] - before["errors"],
            "new_types": new_types,
            "new_paths": new_paths,
        },
        "verdict": "improved" if evidence_increased and errors_not_increased else "inconclusive",
        "limitations": [
            "This is an observable-difference report, not proof of bypass or protocol success.",
            "A real target request and business success condition still require independent verification.",
        ],
    }
    dump_json(Path(args.output), result)
    print(f"[OK] adversarial diff: {args.output} verdict={result['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
