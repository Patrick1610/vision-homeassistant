"""Scan the tracked tree and all reachable Git history without printing secret matches."""

import re
import subprocess
from pathlib import Path

PATTERNS = [
    rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----",
    rb"\bgh[pousr]_[A-Za-z0-9]{20,}",
    rb"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}",
    rb"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    rb"/" + rb"Users/[^/\s]+|/" + rb"Volumes/Storage\b|\.ui\.nabu\.casa",
]


def main():
    names = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    failures = []
    for name in filter(None, names):
        if name.startswith((".ai-review-broker/", "data/", "work/", ".venv/")):
            failures.append(name)
            continue
        path = Path(name)
        if path.is_file() and any(re.search(p, path.read_bytes()) for p in PATTERNS):
            failures.append(name)
    objects = subprocess.check_output(["git", "rev-list", "--objects", "--all"]).splitlines()
    objects += subprocess.check_output(
        ["git", "for-each-ref", "--format=%(objectname)", "refs/tags"]
    ).splitlines()
    seen = set()
    for entry in objects:
        object_id, _, object_path = entry.partition(b" ")
        if object_id in seen:
            continue
        seen.add(object_id)
        kind = subprocess.check_output(["git", "cat-file", "-t", object_id]).strip()
        if kind not in {b"blob", b"commit", b"tag"}:
            continue
        payload = subprocess.check_output(["git", "cat-file", "-p", object_id])
        if kind == b"tag":
            objects.append(payload.splitlines()[0].removeprefix(b"object "))
        if any(
            re.search(pattern, payload) or re.search(pattern, object_path) for pattern in PATTERNS
        ):
            failures.append("historical object " + object_id.decode())
    if failures:
        raise SystemExit("Publication check failed for files: " + ", ".join(failures))
    print("PASS: tracked tree and all reachable history scanned; no detected secrets/private paths")


if __name__ == "__main__":
    main()
