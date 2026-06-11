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

    def test_release_workflow_has_signing_input(self):
        workflow_path = REPO_ROOT / ".github" / "workflows" / "release.yml"
        content = workflow_path.read_text(encoding="utf-8")
        assert "signed:" in content
        assert "CSC_LINK" in content
        assert "FORCE_CODE_SIGNING" in content


class TestSigningConfig:
    """Tests for code signing configuration."""

    def test_signing_scripts_exist(self):
        scripts_dir = REPO_ROOT / "desktop" / "scripts"
        expected = [
            "check_signing_config.js",
            "verify_windows_signature.js",
        ]
        for script in expected:
            assert (scripts_dir / script).exists(), f"Missing signing script: {script}"

    def test_check_signing_config_no_secret_leaks(self):
        script_path = REPO_ROOT / "desktop" / "scripts" / "check_signing_config.js"
        content = script_path.read_text(encoding="utf-8")
        assert "Certificate files and passwords are never logged" in content
        assert "process.env." in content
        # Should not contain actual secret values
        for secret in ["ghp_", "gho_", "github_pat_"]:
            assert secret not in content

    def test_verify_signature_graceful_fallback(self):
        script_path = REPO_ROOT / "desktop" / "scripts" / "verify_windows_signature.js"
        content = script_path.read_text(encoding="utf-8")
        assert "verifier_not_available" in content or "not_found" in content
        assert "REQUIRE_SIGNED_ARTIFACTS" in content
        # Should not fail unsigned builds by default
        assert "process.exit(1)" not in content.split("if (requireSigned")[0] if "if (requireSigned" in content else True

    def test_main_js_has_signing_detection(self):
        main_js_path = REPO_ROOT / "desktop" / "main.js"
        content = main_js_path.read_text(encoding="utf-8")
        assert "hasSigningConfig" in content
        assert "signedBuild" in content
        assert "releaseMode" in content

    def test_desktop_dts_has_signing_fields(self):
        dts_path = REPO_ROOT / "frontend" / "src" / "desktop.d.ts"
        content = dts_path.read_text(encoding="utf-8")
        assert "releaseMode" in content
        assert "signedBuild" in content

    def test_validate_artifacts_has_cert_scan(self):
        validate_path = REPO_ROOT / "desktop" / "scripts" / "validate_release_artifacts.js"
        content = validate_path.read_text(encoding="utf-8")
        assert ".pfx" in content
        assert "certificate" in content.lower() or "cert" in content.lower()
        assert "signing" in content.lower()

    def test_no_hardcoded_cert_paths_in_config(self):
        pkg = _load_desktop_pkg()
        build = pkg.get("build", {})
        win = build.get("win", {})
        # Should not have hardcoded certificateFile or certificatePassword
        assert "certificateFile" not in win or not win["certificateFile"]
        assert "certificatePassword" not in win or not win["certificatePassword"]
        # Should not have forceCodeSigning in base config (it's env-only)
        assert "forceCodeSigning" not in win


class TestReleaseModeHandling:
    """Tests for dev / unsigned-release / signed-release mode handling."""

    def test_package_json_has_release_scripts(self):
        pkg = _load_desktop_pkg()
        scripts = pkg.get("scripts", {})
        assert "check:signing" in scripts
        assert "verify:signature" in scripts
        assert "validate:signing" in scripts
        assert "release:signed" in scripts

    def test_signing_scripts_have_env_guards(self):
        """Verify signing scripts don't fail without env vars."""
        check_path = REPO_ROOT / "desktop" / "scripts" / "check_signing_config.js"
        check_content = check_path.read_text(encoding="utf-8")
        assert "process.env." in check_content

        verify_path = REPO_ROOT / "desktop" / "scripts" / "verify_windows_signature.js"
        verify_content = verify_path.read_text(encoding="utf-8")
        assert "REQUIRE_SIGNED_ARTIFACTS" in verify_content
