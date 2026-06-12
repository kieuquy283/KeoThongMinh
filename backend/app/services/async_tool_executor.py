from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.services. memory_store import get_memory_store
from app.tools.currency_tool import get_currency_info
from app.tools.search_tool import get_search_info
from app.tools.time_tool import get_time_info
from app.tools.weather_tool import get_weather_info


_TOOL_TIMEOUT = 15.0


def _run_tool_sync(intent: str, query: str, entities: dict[str, Any]) -> dict[str, Any]:
    if intent == "time":
        return get_time_info(query, entities=entities)
    if intent == "currency":
        return get_currency_info(query, entities=entities)
    if intent == "weather":
        return get_weather_info(query, entities=entities)
    if intent in {"news_search", "general_search"}:
        return get_search_info(query, intent, entities=entities)
    return {
        "is_available": False,
        "message": "Unsupported tool.",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _apply_memory_defaults_sync(intent: str, entities: dict[str, Any], memory_context: dict[str, str]) -> dict[str, Any]:
    merged = dict(entities)
    if intent == "weather" and not merged.get("location") and memory_context.get("default_city"):
        merged["location"] = memory_context["default_city"]
    if intent == "time" and not merged.get("timezone") and memory_context.get("default_timezone"):
        merged["timezone"] = memory_context["default_timezone"]
    if intent == "currency" and not merged.get("target_currency") and memory_context.get("default_currency"):
        merged["target_currency"] = memory_context["default_currency"]
    return merged


def _build_sources_sync(intent: str, tool_result: dict[str, Any]) -> list[dict[str, Any]]:
    if intent in {"news_search", "general_search"}:
        return [
            {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "published_at": result.get("published_at"),
            }
            for result in tool_result.get("results", [])
            if result.get("title") and result.get("url")
        ]
    return []


def _tool_is_unavailable(tool_result: dict[str, Any]) -> bool:
    if tool_result.get("available") is False:
        return True
    if tool_result.get("is_available") is False:
        return True
    return False


def _detect_missing_info_sync(intent: str, entities: dict[str, Any], tool_result: dict[str, Any]) -> str | None:
    if intent == "weather" and not entities.get("location"):
        return "Minh can biet ban muon xem thoi tiet o dau de tra loi."
    if intent == "time" and not entities.get("timezone") and not entities.get("location"):
        return "Minh can biet ban muon xem gio o thanh pho nao."
    if intent == "currency":
        if not entities.get("base_currency") and not entities.get("target_currency"):
            return "Minh can biet ban muon doi tu tien nao sang tien nao."
    return None


@dataclass
class ToolExecution:
    intent: str
    query: str
    entities: dict[str, Any]
    _task: asyncio.Task | None = field(default=None, repr=False)
    _result: dict[str, Any] | None = None
    _error: str | None = None
    _done: bool = False

    @property
    def is_done(self) -> bool:
        return self._done

    @property
    def result(self) -> dict[str, Any] | None:
        return self._result

    @property
    def error(self) -> str | None:
        return self._error

    def cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

    async def wait(self, timeout: float | None = None) -> dict[str, Any] | None:
        if self._done:
            return self._result
        try:
            await asyncio.wait_for(self._task, timeout=timeout)
        except asyncio.TimeoutError:
            self._error = f"Tool timed out after {timeout}s"
        return self._result


class AsyncToolExecutor:
    def __init__(self) -> None:
        self._executions: list[ToolExecution] = []

    async def execute(
        self,
        intent: str,
        query: str,
        entities: dict[str, Any],
        timeout: float = _TOOL_TIMEOUT,
    ) -> ToolExecution:
        memory_context = get_memory_store().get_memory_context()
        merged = _apply_memory_defaults_sync(intent, dict(entities), memory_context)

        exec_ = ToolExecution(intent=intent, query=query, entities=merged)
        exec_._task = asyncio.create_task(self._run(exec_, merged, timeout))
        self._executions.append(exec_)
        return exec_

    async def _run(
        self,
        exec_: ToolExecution,
        entities: dict[str, Any],
        timeout: float,
    ) -> None:
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_run_tool_sync, exec_.intent, exec_.query, entities),
                timeout=timeout,
            )
            exec_._result = result
            exec_._done = True
        except asyncio.TimeoutError:
            exec_._error = f"Tool timed out after {timeout}s"
        except Exception as exc:
            exec_._error = str(exc)

    async def execute_multiple(
        self,
        routes: list[tuple[str, str, dict[str, Any]]],
        timeout: float = _TOOL_TIMEOUT,
    ) -> list[ToolExecution]:
        executions = [
            await self.execute(intent, query, entities, timeout=timeout)
            for intent, query, entities in routes
        ]
        return executions

    @property
    def active_count(self) -> int:
        return sum(1 for e in self._executions if not e.is_done and e._error is None)

    def cleanup(self) -> None:
        for e in self._executions:
            e.cancel()
        self._executions.clear()
