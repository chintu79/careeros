#!/usr/bin/env python3
"""
CI secret-shape scanner (Phase 3.0.7).

Scans the working tree (tracked files in CI, else all regular files under the repo)
for token-shaped credentials. Prints only the file path and the pattern name —
NEVER the matched value.

Usage:
    python .github/scripts/secret_scan.py [--files-file FILELIST]

Exit codes:
    0  no findings
    1  findings (or usage error)
"""

import argparse
import os
import re
import subprocess
import sys

def looks_like_placeholder(text: str) -> bool:
    """Common placeholder/example words that mark a synthetic value, never a live credential."""
    lowered = text.lower()
    return any(word in lowered for word in ("your", "example", "placeholder", "changeme",
                                            "dummy", "fake", "not-a-secret", "dummy_token",
                                            "truncated", "redacted", "masked"))


PATTERNS = [
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_classic_pat", re.compile(r"\bghp_[A-Za-z0-9]{36,}\b")),
    ("github_fine_grained_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("groq_api_key", re.compile(r"\bgsk_[A-Za-z0-9_-]{20,}\b")),
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("private_key_header", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("json_web_token", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
]

SKIP_DIRS = {
    ".git", "node_modules", "venv", "__pycache__", ".pytest_cache", "dist",
    ".mypy_cache", ".playwright-mcp", "coverage",
}
SKIP_FILES = {".taste-skill", ".github"}
MAX_FILE_BYTES = 1024 * 1024


def tracked_files():
    try:
        out = subprocess.check_output(["git", "ls-files"], text=True, stderr=subprocess.DEVNULL)
        items = [line.strip() for line in out.splitlines() if line.strip()]
        if items:
            return items
    except Exception:
        pass
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            yield os.path.join(root, name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files-file", help="optional newline-separated file list")
    args = parser.parse_args()

    if args.files_file:
        files = [line.strip() for line in open(args.files_file, encoding="utf-8") if line.strip()]
    else:
        files = list(tracked_files())

    findings = []
    for path in files:
        if path.startswith((".taste-skill/", ".github/scripts/secret_scan.py")):
            continue
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if size > MAX_FILE_BYTES:
            continue
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
            content = raw.decode("utf-8", errors="ignore")
        except OSError:
            continue
        for line_number, line in enumerate(content.splitlines(), 1):
            if "secret-scan-allow" in line:
                continue
            for pattern_name, pattern in PATTERNS:
                for match in pattern.finditer(line):
                    if looks_like_placeholder(match.group(0)):
                        continue
                    findings.append((path, pattern_name))

    if findings:
        for path, pattern_name in findings:
            print(f"SECRET-SHAPE: {pattern_name} in {path}")
        print(f"\n{len(findings)} secret-shaped value(s) found; values are not printed by this tool.")
        return 1
    print("secret scan clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
