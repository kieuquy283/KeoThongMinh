from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def wait_for_health(url: str, timeout_seconds: int = 30) -> None:
    deadline = time.time() + timeout_seconds
    last_error: str | None = None

    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)

        time.sleep(0.5)

    raise TimeoutError(last_error or f"Health check did not return 200 within {timeout_seconds}s.")


def main() -> int:
    root_dir = Path(__file__).resolve().parents[1]
    backend_exe = root_dir / "dist" / "keobot_backend" / "keobot_backend.exe"
    health_url = "http://127.0.0.1:8000/health"

    if not backend_exe.exists():
        print(f"FAIL: backend executable not found: {backend_exe}")
        return 1

    print(f"PASS: backend executable found: {backend_exe}")

    process = subprocess.Popen(
        [str(backend_exe)],
        cwd=str(backend_exe.parent),
        env={
            **os.environ,
            "BACKEND_PORT": "8000",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        wait_for_health(health_url, timeout_seconds=30)
        print("PASS: /health returned 200")
        print("SMOKE RESULT: PASS")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        print("SMOKE RESULT: FAIL")
        return 1
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
