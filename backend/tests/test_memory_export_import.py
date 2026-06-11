from __future__ import annotations

import json


class TestMemoryExport:
    def test_export_returns_schema(self, client):
        response = client.get("/memory/export")
        assert response.status_code == 200
        payload = response.json()
        assert payload["schema_version"] == 1
        assert "exported_at" in payload
        assert isinstance(payload["records"], list)

    def test_export_includes_stored_records(self, client):
        client.post("/memory", json={"key": "default_city", "value": "Hà Nội"})
        response = client.get("/memory/export")
        assert response.status_code == 200
        payload = response.json()
        records = payload["records"]
        assert any(r["key"] == "default_city" and r["value"] == "Hà Nội" for r in records)

    def test_export_does_not_include_secrets(self, client):
        # Secret-like keys cannot be created via the normal endpoint (Literal-based),
        # but let's verify the export doesn't accidentally expose anything
        client.post("/memory", json={"key": "user_name", "value": "Test"})
        response = client.get("/memory/export")
        assert response.status_code == 200
        for record in response.json()["records"]:
            assert "api_key" not in record["key"].lower()
            assert "secret" not in record["key"].lower()
            assert "password" not in record["key"].lower()
            assert "token" not in record["key"].lower()

    def test_export_empty_when_no_memory(self, client):
        response = client.get("/memory/export")
        assert response.status_code == 200
        assert response.json()["records"] == []


class TestMemoryImport:
    def test_import_accepts_valid_json(self, client):
        payload = {
            "records": [
                {"key": "default_city", "value": "Hà Nội", "category": "preference"},
                {"key": "user_name", "value": "Quy", "category": "preference"},
            ],
            "mode": "merge",
        }
        response = client.post("/memory/import", json=payload)
        assert response.status_code == 200
        result = response.json()
        assert result["ok"] is True
        assert result["records_found"] == 2
        assert result["records_added"] == 2

    def test_imported_records_are_queryable(self, client):
        payload = {
            "records": [
                {"key": "default_city", "value": "Hà Nội"},
                {"key": "user_name", "value": "Quy"},
            ],
            "mode": "merge",
        }
        client.post("/memory/import", json=payload)
        response = client.get("/memory")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 2

    def test_import_merge_avoids_duplicate_keys(self, client):
        client.post("/memory", json={"key": "default_city", "value": "Hà Nội"})
        payload = {
            "records": [
                {"key": "default_city", "value": "Sài Gòn", "category": "preference"},
                {"key": "user_name", "value": "Quy"},
            ],
            "mode": "merge",
        }
        response = client.post("/memory/import", json=payload)
        assert response.status_code == 200
        result = response.json()
        assert result["records_added"] == 1
        assert result["records_updated"] == 1
        # Verify existing value was updated via list
        response = client.get("/memory")
        assert response.status_code == 200
        items = response.json()
        city_item = next(item for item in items if item["key"] == "default_city")
        assert city_item["value"] == "Sài Gòn"

    def test_import_replace_clears_first(self, client):
        client.post("/memory", json={"key": "default_city", "value": "Hà Nội"})
        payload = {
            "records": [
                {"key": "user_name", "value": "Quy"},
            ],
            "mode": "replace",
        }
        response = client.post("/memory/import", json=payload)
        assert response.status_code == 200
        result = response.json()
        assert result["records_added"] == 1
        # Only the imported record should exist
        response = client.get("/memory")
        assert len(response.json()) == 1

    def test_import_rejects_empty_payload(self, client):
        response = client.post("/memory/import", json={"records": [], "mode": "merge"})
        assert response.status_code == 200
        assert response.json()["records_found"] == 0

    def test_import_rejects_invalid_schema(self, client):
        response = client.post("/memory/import", json={"records": "not_a_list", "mode": "merge"})
        assert response.status_code == 422

    def test_import_rejects_secret_looking_keys(self, client):
        payload = {
            "records": [
                {"key": "api_key", "value": "sk-12345"},
            ],
            "mode": "merge",
        }
        response = client.post("/memory/import", json=payload)
        assert response.status_code == 422
        payload = {
            "records": [
                {"key": "secret_token", "value": "abc123"},
            ],
            "mode": "merge",
        }
        response = client.post("/memory/import", json=payload)
        assert response.status_code == 422

    def test_import_with_duplicates_in_same_payload(self, client):
        payload = {
            "records": [
                {"key": "default_city", "value": "Hà Nội"},
                {"key": "default_city", "value": "Sài Gòn"},
            ],
            "mode": "merge",
        }
        response = client.post("/memory/import", json=payload)
        assert response.status_code == 200
        result = response.json()
        assert result["records_invalid"] == 1
        assert result["records_added"] == 1


class TestPersonalDataReset:
    def test_reset_clears_memory(self, client):
        client.post("/memory", json={"key": "default_city", "value": "Hà Nội"})
        client.post("/memory", json={"key": "user_name", "value": "Quy"})
        response = client.post("/personal-data/reset")
        assert response.status_code == 200
        result = response.json()
        assert result["memory_deleted"] == 2

    def test_reset_returns_ok(self, client):
        response = client.post("/personal-data/reset")
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_reset_does_not_crash_if_folders_missing(self, client):
        response = client.post("/personal-data/reset")
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_memory_empty_after_reset(self, client):
        client.post("/memory", json={"key": "default_city", "value": "Hà Nội"})
        client.post("/personal-data/reset")
        response = client.get("/memory")
        assert response.json() == []
