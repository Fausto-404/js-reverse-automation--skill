#!/usr/bin/env python3
"""Anti-crawl type classifier.

Classifies the target website's anti-crawl mechanism into one of three types:
1. Signature-type: environment IS the signature (e.g., RS/Akamai, 412 challenges)
2. Behavioral-type: parameter signing + interceptors (e.g., TikTok a_bogus)
3. Pure obfuscation: just hard to read, no environment detection

Usage:
  python3 scripts/classify_anticrawl.py --probe artifacts/probe_dump.json --analysis analysis_result.json --output artifacts/anticrawl_type.json
"""
from __future__ import annotations

import argparse
from common import dump_json, flatten_events, load_json


def classify(events: list[dict], analysis: dict) -> dict:
    """Classify anti-crawl type based on probe events and analysis."""
    result = {
        "type": "unknown",
        "confidence": "low",
        "evidence": [],
        "recommended_strategy": "runtime_hook"
    }

    # Check for signature-type indicators
    signature_indicators = []
    for event in events:
        etype = event.get("type", "")
        # 412 challenge patterns
        if "412" in str(event.get("url", "")):
            signature_indicators.append("412_challenge")
        # Environment fingerprinting
        if "navigator" in str(event.get("function", "")).lower():
            signature_indicators.append("navigator_access")
        if "canvas" in str(event.get("function", "")).lower():
            signature_indicators.append("canvas_fingerprint")
        if "webgl" in str(event.get("function", "")).lower():
            signature_indicators.append("webgl_fingerprint")

    # Check for behavioral-type indicators
    behavioral_indicators = []
    for event in events:
        etype = event.get("type", "")
        # XHR/fetch with signing
        if etype.startswith("network."):
            body = str(event.get("input_preview", ""))
            if any(kw in body.lower() for kw in ["x-bogus", "a_bogus", "wmsdk", "sign", "signature"]):
                behavioral_indicators.append("signing_parameter")
        # Crypto library usage
        if etype.startswith("crypto."):
            behavioral_indicators.append("crypto_operation")

    # Check for obfuscation indicators
    obfuscation_indicators = []
    # Check if there are many nested function calls
    if len(events) > 100:
        obfuscation_indicators.append("high_event_count")
    # Check for eval/Function usage
    for event in events:
        if "eval" in str(event.get("function", "")).lower():
            obfuscation_indicators.append("eval_usage")

    # Determine type
    if signature_indicators:
        result["type"] = "signature"
        result["confidence"] = "high" if len(signature_indicators) >= 2 else "medium"
        result["evidence"] = signature_indicators
        result["recommended_strategy"] = "environment_masquerade"
    elif behavioral_indicators:
        result["type"] = "behavioral"
        result["confidence"] = "high" if len(behavioral_indicators) >= 2 else "medium"
        result["evidence"] = behavioral_indicators
        result["recommended_strategy"] = "algorithm_tracking"
    elif obfuscation_indicators:
        result["type"] = "obfuscation"
        result["confidence"] = "medium"
        result["evidence"] = obfuscation_indicators
        result["recommended_strategy"] = "runtime_hook"
    else:
        result["type"] = "simple"
        result["confidence"] = "medium"
        result["evidence"] = ["no_complex_indicators"]
        result["recommended_strategy"] = "runtime_hook"

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Anti-crawl type classifier.")
    parser.add_argument("--probe", required=True, help="Path to probe_dump.json.")
    parser.add_argument("--analysis", help="Path to analysis_result.json.")
    parser.add_argument("--output", required=True, help="Path to output JSON.")
    args = parser.parse_args()

    probe = load_json(args.probe, {})
    analysis = load_json(args.analysis, {}) if args.analysis else {}
    events = flatten_events(probe)

    result = classify(events, analysis)
    dump_json(args.output, result)
    print(f"[OK] anti-crawl type: {result['type']} (confidence: {result['confidence']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
