from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest


def _reload_data_paths(monkeypatch, data_root: str | None = None):
    if data_root is not None:
        monkeypatch.setenv("KEOBOT_DATA_DIR", data_root)
    else:
        monkeypatch.delenv("KEOBOT_DATA_DIR", raising=False)
    mod = importlib.import_module("app.data_paths")
    importlib.reload(mod)
    return mod


def test_get_data_root_uses_env_var(monkeypatch, tmp_path):
    mod = _reload_data_paths(monkeypatch, str(tmp_path / "custom"))
    root = mod.get_data_root()
    assert root == (tmp_path / "custom").resolve()


def test_get_data_root_fallback_to_base_dir(monkeypatch):
    mod = _reload_data_paths(monkeypatch, data_root=None)
    from app.data_paths import BASE_DIR
    assert mod.get_data_root() == (BASE_DIR / "data").resolve()


def test_set_data_root_overrides_env(monkeypatch, tmp_path):
    mod = _reload_data_paths(monkeypatch, str(tmp_path / "env_val"))
    mod.set_data_root(str(tmp_path / "override"))
    assert mod.get_data_root() == (tmp_path / "override").resolve()
    mod._OVERRIDE_ROOT = None


def test_set_data_root_resolves_tilde(monkeypatch):
    mod = _reload_data_paths(monkeypatch)
    mod.set_data_root("~/keobot_test_tilde")
    root = mod.get_data_root()
    assert root == Path.home().joinpath("keobot_test_tilde").resolve()
    mod._OVERRIDE_ROOT = None


def test_get_data_dir_is_subdir_of_root(monkeypatch, tmp_path):
    mod = _reload_data_paths(monkeypatch, str(tmp_path / "base"))
    assert mod.get_data_dir() == mod.get_data_root() / "data"


def test_all_subdirs_live_under_root(monkeypatch, tmp_path):
    mod = _reload_data_paths(monkeypatch, str(tmp_path / "base"))
    root = mod.get_data_root()
    for getter in (
        mod.get_data_dir,
        mod.get_logs_dir,
        mod.get_memory_db_path,
        mod.get_reminder_db_path,
        mod.get_documents_dir,
        mod.get_indexes_dir,
        mod.get_exports_dir,
        mod.get_temp_dir,
        mod.get_backups_dir,
        mod.get_static_dir,
        mod.get_audio_dir,
    ):
        path = getter()
        assert str(path).startswith(str(root)), f"{getter.__name__} -> {path} not under {root}"


def test_is_path_inside_data_root_accepts_inner(monkeypatch, tmp_path):
    mod = _reload_data_paths(monkeypatch, str(tmp_path / "base"))
    inner = mod.get_data_dir() / "subdir" / "file.txt"
    assert mod.is_path_inside_data_root(inner) is True


def test_is_path_inside_data_root_rejects_outer(monkeypatch, tmp_path):
    mod = _reload_data_paths(monkeypatch, str(tmp_path / "base"))
    outer = tmp_path / "outside" / "file.txt"
    assert mod.is_path_inside_data_root(outer) is False


def test_is_path_inside_data_root_rejects_sibling(monkeypatch, tmp_path):
    mod = _reload_data_paths(monkeypatch, str(tmp_path / "base"))
    sibling = tmp_path / "base_sibling" / "file.txt"
    assert mod.is_path_inside_data_root(sibling) is False


@pytest.mark.skipif(sys.platform == "win32", reason="requires symlink privilege")
def test_is_path_inside_data_root_accepts_symlink(monkeypatch, tmp_path):
    mod = _reload_data_paths(monkeypatch, str(tmp_path / "base"))
    inside = mod.get_data_dir() / "target.txt"
    inside.parent.mkdir(parents=True, exist_ok=True)
    inside.write_text("hi")
    link = mod.get_data_dir() / "mylink.txt"
    link.symlink_to(inside, target_is_directory=False)
    assert mod.is_path_inside_data_root(link) is True


@pytest.mark.skipif(sys.platform == "win32", reason="requires symlink privilege")
def test_is_path_inside_data_root_rejects_symlink_escape(monkeypatch, tmp_path):
    mod = _reload_data_paths(monkeypatch, str(tmp_path / "base"))
    outside = tmp_path / "outside.txt"
    outside.write_text("hi")
    link = mod.get_data_dir() / "escape_link.txt"
    try:
        link.symlink_to(outside, target_is_directory=False)
        assert mod.is_path_inside_data_root(link) is True
        assert mod.is_path_inside_data_root(outside) is False
    except OSError:
        pass


def test_ensure_data_dirs_creates_all(monkeypatch, tmp_path):
    mod = _reload_data_paths(monkeypatch, str(tmp_path / "base"))
    created = mod.ensure_data_dirs()
    for name in ("data", "logs", "documents", "indexes", "exports", "temp", "backups", "static", "audio"):
        assert name in created, f"Missing {name}"
        assert Path(created[name]).is_dir(), f"{name} -> {created[name]} not created"


def test_ensure_data_dirs_is_idempotent(monkeypatch, tmp_path):
    mod = _reload_data_paths(monkeypatch, str(tmp_path / "base"))
    first = mod.ensure_data_dirs()
    second = mod.ensure_data_dirs()
    assert first == second


def test_migrate_old_db_copies_file(monkeypatch, tmp_path):
    mod = _reload_data_paths(monkeypatch, str(tmp_path / "base"))
    old_name = "test_old.sqlite3"
    old_path = mod.get_data_root() / old_name
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_text("old-db-content")

    result = mod.migrate_old_db(old_name)
    assert result is True

    new_path = mod.get_data_dir() / old_name
    assert new_path.exists()
    assert new_path.read_text() == "old-db-content"


def test_migrate_old_db_skips_if_no_old_file(monkeypatch, tmp_path):
    mod = _reload_data_paths(monkeypatch, str(tmp_path / "base"))
    result = mod.migrate_old_db("nonexistent.sqlite3")
    assert result is False


def test_migrate_old_db_skips_if_new_already_exists(monkeypatch, tmp_path):
    mod = _reload_data_paths(monkeypatch, str(tmp_path / "base"))
    old_name = "test_skip.sqlite3"
    old_path = mod.get_data_root() / old_name
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_text("old")
    new_path = mod.get_data_dir() / old_name
    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.write_text("new")

    result = mod.migrate_old_db(old_name)
    assert result is False
    assert new_path.read_text() == "new"


def test_get_data_root_no_setenv_fallback(monkeypatch):
    monkeypatch.delenv("KEOBOT_DATA_DIR", raising=False)
    mod = importlib.import_module("app.data_paths")
    importlib.reload(mod)
    root = mod.get_data_root()
    assert isinstance(root, Path)
    assert root.is_absolute()
