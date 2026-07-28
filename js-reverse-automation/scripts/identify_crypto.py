#!/usr/bin/env python3
"""Crypto algorithm identifier.

Identifies encryption algorithm by output length and character set.

Usage:
  python3 scripts/identify_crypto.py --output-sample "5d41402abc4b2a76b9719d911017c592"
"""
from __future__ import annotations

import argparse
import re
import json


# Algorithm signatures by output length
LENGTH_SIGNATURES = {
    32: ["MD5", "MD4", "MD2"],
    40: ["SHA-1", "RIPEMD-160"],
    56: ["SHA-224"],
    64: ["SHA-256", "SHA3-256"],
    96: ["SHA-384"],
    128: ["SHA-512", "SHA3-512"],
    172: ["RSA-1024 (Base64)"],
    256: ["RSA-1024 (Hex)", "RSA-2048 (Base64 truncated)"],
    344: ["RSA-2048 (Base64)"],
    512: ["RSA-2048 (Hex)", "RSA-4096 (Base64 truncated)"],
}

# Character set patterns
CHARSET_PATTERNS = [
    (r'^[0-9a-f]+$', 'hex'),
    (r'^[0-9A-F]+$', 'hex_upper'),
    (r'^[A-Za-z0-9+/]+=*$', 'base64'),
    (r'^[A-Za-z0-9_-]+$', 'base64url'),
    (r'^[0-9]+$', 'decimal'),
]


def identify(sample: str) -> dict:
    """Identify crypto algorithm by output sample."""
    result = {
        "sample": sample[:100],
        "length": len(sample),
        "charset": "unknown",
        "possible_algorithms": [],
        "confidence": "low"
    }

    # Detect charset
    for pattern, charset in CHARSET_PATTERNS:
        if re.match(pattern, sample):
            result["charset"] = charset
            break

    # Match by length
    length = len(sample)
    if length in LENGTH_SIGNATURES:
        result["possible_algorithms"] = LENGTH_SIGNATURES[length]
        result["confidence"] = "medium"
    else:
        # Find closest match
        for sig_length, algorithms in LENGTH_SIGNATURES.items():
            if abs(length - sig_length) <= 4:
                result["possible_algorithms"] = [f"{alg} (approximate)" for alg in algorithms]
                result["confidence"] = "low"
                break

    # Special cases
    if result["charset"] == "base64" and length % 4 == 0:
        decoded_length = length * 3 // 4
        if decoded_length in [128, 256, 512]:
            result["possible_algorithms"].append(f"RSA-{decoded_length * 8} (Base64 encoded)")

    if result["charset"] == "hex" and length in [128, 256, 512, 1024]:
        result["possible_algorithms"].append(f"RSA-{length * 4} (Hex encoded)")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Crypto algorithm identifier.")
    parser.add_argument("--output-sample", required=True, help="Sample encrypted output.")
    parser.add_argument("--output", help="Path to output JSON.")
    args = parser.parse_args()

    result = identify(args.output_sample)

    if args.output:
        dump_json(args.output, result)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
