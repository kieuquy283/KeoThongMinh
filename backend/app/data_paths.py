from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger("keobot.data_paths")

BASE_DIR = Path(__file__).resolve().parents[1]

_OVERRIDE_ROOT: Path | None = None


def set_data_root(path: str | Path) -> None:
    global _OVERRIDE_ROOT
    _OVERRIDE_ROOT = Path(path).expanduser().resolve()


def get_data_root() -> Path:
    if _OVERRIDE_ROOT is not None:
        return _OVERRIDE_ROOT
    raw = os.getenv("KEOBOT_DATA_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return BASE_DIR / "data"


def get_data_dir() -> Path:
    return get_data_root() / "data"


def get_logs_dir() -> Path:
    return get_data_root() / "logs"


def get_memory_db_path() -> Path:
    return get_data_dir() / "memory.sqlite3"


def get_reminder_db_path() -> Path:
    return get_data_dir() / "reminders.sqlite3"


def get_documents_dir() -> Path:
    return get_data_root() / "documents"


def get_indexes_dir() -> Path:
    return get_data_root() / "indexes"


def get_exports_dir() -> Path:
    return get_data_root() / "exports"


def get_temp_dir() -> Path:
    return get_data_root() / "temp"


def get_backups_dir() -> Path:
    return get_data_root() / "backups"


def get_static_dir() -> Path:
    return get_data_root() / "static"


def get_audio_dir() -> Path:
    return get_static_dir() / "audio"


def ensure_data_dirs() -> dict[str, str]:
    paths: dict[str, Path] = {
        "data": get_data_dir(),
        "logs": get_logs_dir(),
        "documents": get_documents_dir(),
        "indexes": get_indexes_dir(),
        "exports": get_exports_dir(),
        "temp": get_temp_dir(),
        "backups": get_backups_dir(),
        "static": get_static_dir(),
        "audio": get_audio_dir(),
    }
    created: dict[str, str] = {}
    for name, path in paths.items():
        path.mkdir(parents=True, exist_ok=True)
        created[name] = str(path)
    return created


def is_path_inside_data_root(path: str | Path) -> bool:
    resolved = Path(path).expanduser().resolve()
    root = get_data_root().resolve()
    try:
        resolved.relative_to(root)
        return True
    except ValueError:
        return False


def migrate_old_db(old_db_name: str) -> bool:
    old_path = get_data_root() / old_db_name
    new_path = get_data_dir() / old_db_name
    if not old_path.exists():
        return False
    if new_path.exists():
        return False
    get_data_dir().mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(old_path), str(new_path))
    logger.info("Migrated %s from %s to %s", old_db_name, old_path, new_path)
    return True
