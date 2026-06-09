from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root_dir = Path(__file__).resolve().parents[1]
    spec_file = root_dir / "keobot_backend.spec"
    build_dir = root_dir / "build"
    dist_dir = root_dir / "dist"
    output_exe = dist_dir / "keobot_backend" / "keobot_backend.exe"

    if importlib.util.find_spec("PyInstaller") is None:
        print("PyInstaller is not installed.")
        print("Install it with:")
        print("  pip install pyinstaller")
        return 1

    for target in (build_dir, dist_dir):
        if target.exists():
            print(f"Removing old build directory: {target}")
            shutil.rmtree(target)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        str(spec_file),
    ]

    print("Running:", " ".join(command))
    try:
        completed = subprocess.run(command, cwd=root_dir, timeout=1800)
    except subprocess.TimeoutExpired:
        print("PyInstaller build timed out after 1800 seconds.")
        return 1

    if completed.returncode != 0:
        return completed.returncode

    if not output_exe.exists():
        print(f"Build completed but executable was not found: {output_exe}")
        return 1

    print(f"Build complete: {output_exe}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
