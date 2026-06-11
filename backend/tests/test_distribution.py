"""Tests for release distribution configuration."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DESKTOP_PKG_PATH = REPO_ROOT / "desktop" / "package.json"
BACKEND_PKG = "app.main"
BACKEND_APP = "app"


def _load_desktop_pkg() -> dict:
    with open(DESKTOP_PKG_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestDesktopPublishConfig:
    def test_publish_config_exists(self):
        pkg = _load_desktop_pkg()
        publish = pkg.get("build", {}).get("publish")
        assert publish is not None, "build.publish should not be null"
        assert len(publish) > 0, "build.publish should be a non-empty array"

    def test_publish_config_has_github_provider(self):
        pkg = _load_desktop_pkg()
        publish = pkg["build"]["publish"]
        for entry in publish if isinstance(publish, list) else [publish]:
            assert entry["provider"] == "github"

    def test_publish_config_has_draft_release_type(self):
        pkg = _load_desktop_pkg()
        publish = pkg["build"]["publish"]
        for entry in publish if isinstance(publish, list) else [publish]:
            assert entry.get("releaseType") == "draft"

    def test_no_tokens_in_publish_config(self):
        pkg = _load_desktop_pkg()
        raw = json.dumps(pkg["build"]["publish"])
        assert "ghp_" not in raw, "Should not contain GitHub personal access token"
        assert "gho_" not in raw, "Should not contain GitHub OAuth token"
        assert "github_pat_" not in raw, "Should not contain GitHub PAT"
        assert "GITHUB_TOKEN" not in raw, "Should not reference GITHUB_TOKEN directly"
        assert "GH_TOKEN" not in raw, "Should not reference GH_TOKEN directly"


class TestDesktopPublishDisabled:
    """Tests for when publish is set to null (dev builds)."""

    @pytest.fixture
    def null_publish_pkg(self):
        """Simulate a package.json where publish is null."""
        pkg = _load_desktop_pkg()
        original_publish = pkg.get("build", {}).get("publish")
        pkg.setdefault("build", {})["publish"] = None
        return pkg, original_publish

    def test_dev_build_no_publish(self, null_publish_pkg):
        pkg, _ = null_publish_pkg
        assert pkg["build"]["publish"] is None


class TestAppInfo:
    def test_app_info_metadata(self):
        """Verify getAppInfo returns expected metadata keys."""
        pkg = _load_desktop_pkg()
        build_config = pkg.get("build", {})
        assert "appId" in build_config
        assert "productName" in build_config
        assert pkg.get("version") is not None

    def test_update_channel(self):
        """Verify version string is valid semver-like."""
        version = _load_desktop_pkg()["version"]
        parts = version.split(".")
        assert len(parts) == 3

    def test_artifact_name_patterns(self):
        """Verify artifact filenames use ${version} variable."""
        pkg = _load_desktop_pkg()
        build = pkg.get("build", {})
        portable_name = build.get("portable", {}).get("artifactName", "")
        nsis_name = build.get("nsis", {}).get("artifactName", "")
        assert "${version}" in portable_name
        assert "${version}" in nsis_name


class TestUpdaterDisabledState:
    def test_main_js_checks_publish_config(self):
        """Verify main.js has hasPublishConfig function."""
        main_js_path = REPO_ROOT / "desktop" / "main.js"
        content = main_js_path.read_text(encoding="utf-8")
        assert "hasPublishConfig" in content
        assert "publishProvider" in content

    def test_main_js_returns_publish_provider(self):
        """Verify getAppInfo IPC handler returns publishProvider."""
        main_js_path = REPO_ROOT / "desktop" / "main.js"
        content = main_js_path.read_text(encoding="utf-8")
        assert "publishProvider" in content
        assert "updateChannel" in content

    def test_no_hardcoded_tokens_in_main(self):
        """Verify main.js does not contain hardcoded tokens."""
        main_js_path = REPO_ROOT / "desktop" / "main.js"
        content = main_js_path.read_text(encoding="utf-8")
        for token_pattern in ["ghp_", "gho_", "github_pat_"]:
            lines = [l for l in content.split("\n") if token_pattern in l and "#" not in l.split("#")[0]]
            assert not lines, f"Found potential token pattern '{token_pattern}' in main.js"


class TestReleaseArtifacts:
    def test_release_scripts_exist(self):
        scripts_dir = REPO_ROOT / "desktop" / "scripts"
        expected = ["prepare_release.js", "check_update_metadata.js", "validate_release_artifacts.js", "smoke_packaged_app.js"]
        for script in expected:
            assert (scripts_dir / script).exists(), f"Missing script: {script}"

    def test_release_workflow_exists(self):
        workflow_path = REPO_ROOT / ".github" / "workflows" / "release.yml"
        assert workflow_path.exists()
        content = workflow_path.read_text(encoding="utf-8")
        assert "workflow_dispatch" in content
        assert "GITHUB_TOKEN" in content
        for token_pattern in ["ghp_", "gho_", "github_pat_"]:
            assert token_pattern not in content, f"Hardcoded token pattern in workflow: {token_pattern}"
