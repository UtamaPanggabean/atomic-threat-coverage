#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys


root = Path(__file__).resolve().parent.parent
errors = []
for line in (root / "submodules.lock").read_text(encoding="utf-8").splitlines():
    if not line.strip() or line.startswith("#"):
        continue
    relative, expected = line.split()
    result = subprocess.run(
        ["git", "-C", str(root / relative), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    )
    actual = result.stdout.strip() if result.returncode == 0 else "not initialized"
    if actual != expected:
        errors.append(f"{relative}: expected {expected}, got {actual}")

if errors:
    print("Submodule pin verification failed:", file=sys.stderr)
    print("\n".join(errors), file=sys.stderr)
    raise SystemExit(1)
print("All submodule revisions match submodules.lock")
