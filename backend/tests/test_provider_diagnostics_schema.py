from __future__ import annotations

from datetime import datetime

from app.schemas import ToolProviderStatus, ToolTestResponse, ToolsStatusResponse


def test_tool_provider_status_defaults_are_compatible():
    status = ToolProviderStatus(provider="none", configured=False)

    assert status.live is None
    assert status.status == "unknown_error"
    assert status.message == ""
    assert status.last_checked_at is None


def test_tools_status_response_serializes_nested_status():
    payload = ToolsStatusResponse(
        weather=ToolProviderStatus(
            provider="openweathermap",
            configured=True,
            live=True,
            status="ok",
            message="ok",
            last_checked_at=datetime(2026, 6, 9, 10, 0, 0),
        ),
        search=ToolProviderStatus(
            provider="tavily",
            configured=False,
            live=False,
            status="not_configured",
            message="missing key",
            last_checked_at=datetime(2026, 6, 9, 10, 0, 0),
        ),
        currency=ToolProviderStatus(
            provider="demo",
            configured=True,
            live=False,
            status="ok",
            message="demo",
            last_checked_at=datetime(2026, 6, 9, 10, 0, 0),
        ),
    )

    data = payload.model_dump()

    assert data["weather"]["status"] == "ok"
    assert data["search"]["message"] == "missing key"
    assert data["currency"]["provider"] == "demo"


def test_tool_test_response_schema():
    response = ToolTestResponse(
        tool="weather",
        status="not_configured",
        message="Weather provider not configured",
        sample_result={"available": False},
        checked_at=datetime(2026, 6, 9, 10, 0, 0),
    )

    assert response.tool == "weather"
    assert response.status == "not_configured"
    assert response.sample_result == {"available": False}
