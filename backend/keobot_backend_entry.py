from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = get_base_dir()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.chdir(BASE_DIR)

from app.main import app


if __name__ == "__main__":
    print(f"[keobot-backend] starting from {BASE_DIR}")
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False, log_level="info")
