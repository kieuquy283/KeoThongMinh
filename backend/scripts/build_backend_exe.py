from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root_dir = Path(__file__).resolve().parents[1]
    entrypoint = root_dir / "keobot_backend_entry.py"

    if importlib.util.find_spec("PyInstaller") is None:
        print("PyInstaller is not installed.")
        print("Install it with:")
        print("  pip install pyinstaller")
        return 1

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "keobot_backend",
        str(entrypoint),
    ]

    print("Running:", " ".join(command))
    completed = subprocess.run(command, cwd=root_dir)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
