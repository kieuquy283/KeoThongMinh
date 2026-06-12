from __future__ import annotations

import asyncio

import pytest
from app.services.event_bus import Event, EventType, EventBus, reset_event_bus, get_event_bus


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_event_bus()
    yield
    reset_event_bus()


class TestEventBus:
    def test_sync_listener_is_called(self):
        bus = EventBus()
        received: list[Event] = []

        def listener(event: Event) -> None:
            received.append(event)

        bus.subscribe(EventType.user_message, listener)
        event = Event(type=EventType.user_message, payload={"text": "hello"}, session_id="s1")
        bus.publish(event)
        assert len(received) == 1
        assert received[0] is event

    def test_async_listener_is_called(self):
        bus = EventBus()
        received: list[Event] = []

        async def listener(event: Event) -> None:
            received.append(event)

        bus.subscribe(EventType.llm_token, listener)
        event = Event(type=EventType.llm_token, payload={"token": "xin"}, session_id="s1")

        async def run():
            await bus.publish_async(event)

        asyncio.run(run())
        assert len(received) == 1
        assert received[0] is event

    def test_unsubscribe_removes_listener(self):
        bus = EventBus()
        received: list[Event] = []

        def listener(event: Event) -> None:
            received.append(event)

        unsubscribe = bus.subscribe(EventType.stream_start, listener)
        bus.publish(Event(type=EventType.stream_start))
        assert len(received) == 1

        unsubscribe()
        bus.publish(Event(type=EventType.stream_start))
        assert len(received) == 1

    def test_different_event_types_isolated(self):
        bus = EventBus()
        received_a: list[Event] = []
        received_b: list[Event] = []

        def listener_a(event: Event) -> None:
            received_a.append(event)

        def listener_b(event: Event) -> None:
            received_b.append(event)

        bus.subscribe(EventType.tool_call, listener_a)
        bus.subscribe(EventType.tool_result, listener_b)

        bus.publish(Event(type=EventType.tool_call, payload={"intent": "weather"}))
        assert len(received_a) == 1
        assert len(received_b) == 0

        bus.publish(Event(type=EventType.tool_result, payload={"intent": "weather"}))
        assert len(received_a) == 1
        assert len(received_b) == 1

    def test_multiple_listeners_same_event(self):
        bus = EventBus()
        results: list[int] = []

        def listener1(event: Event) -> None:
            results.append(1)

        def listener2(event: Event) -> None:
            results.append(2)

        bus.subscribe(EventType.stream_end, listener1)
        bus.subscribe(EventType.stream_end, listener2)
        bus.publish(Event(type=EventType.stream_end))
        assert results == [1, 2]

    def test_event_as_dict(self):
        event = Event(
            type=EventType.interrupt,
            payload={"reason": "cancel"},
            session_id="s1",
        )
        d = event.as_dict()
        assert d["type"] == "interrupt"
        assert d["payload"] == {"reason": "cancel"}
        assert d["session_id"] == "s1"

    def test_publish_no_listeners_does_not_raise(self):
        bus = EventBus()
        bus.publish(Event(type=EventType.cancel, session_id="s1"))

    def test_publish_async_no_listeners_does_not_raise(self):
        bus = EventBus()

        async def run():
            await bus.publish_async(Event(type=EventType.cancel, session_id="s1"))

        asyncio.run(run())

    def test_clear_removes_all_listeners(self):
        bus = EventBus()
        received: list[Event] = []

        def listener(event: Event) -> None:
            received.append(event)

        bus.subscribe(EventType.user_message, listener)
        bus.subscribe(EventType.stream_start, listener)
        bus.clear()
        bus.publish(Event(type=EventType.user_message))
        bus.publish(Event(type=EventType.stream_start))
        assert len(received) == 0

    def test_get_event_bus_singleton(self):
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_reset_event_bus_clears_and_creates_new(self):
        bus1 = get_event_bus()
        reset_event_bus()
        bus2 = get_event_bus()
        assert bus1 is not bus2

    def test_listener_receives_payload(self):
        bus = EventBus()
        result: dict | None = None

        def listener(event: Event) -> None:
            nonlocal result
            result = event.payload

        bus.subscribe(EventType.tool_result, listener)
        bus.publish(Event(type=EventType.tool_result, payload={"intent": "weather", "result": {"temp": 25}}))
        assert result == {"intent": "weather", "result": {"temp": 25}}

    def test_event_type_enum_values(self):
        assert EventType.user_message.value == "user_message"
        assert EventType.llm_token.value == "llm_token"
        assert EventType.stream_start.value == "stream_start"
        assert EventType.stream_end.value == "stream_end"
        assert EventType.tool_call.value == "tool_call"
        assert EventType.tool_result.value == "tool_result"
        assert EventType.interrupt.value == "interrupt"
        assert EventType.cancel.value == "cancel"
        assert EventType.replanning.value == "replanning"


class TestEventTypeCoverage:
    def test_all_event_types_referenced_in_codebase(self):
        import os

        backend_dir = os.path.join(os.path.dirname(__file__), "..", "app", "services")
        main_dir = os.path.join(os.path.dirname(__file__), "..", "app")
        files_to_check = [
            os.path.join(backend_dir, "stream_manager.py"),
            os.path.join(backend_dir, "async_tool_executor.py"),
            os.path.join(backend_dir, "chat_flow.py"),
            os.path.join(main_dir, "main.py"),
        ]
        content = ""
        for fpath in files_to_check:
            if os.path.exists(fpath):
                with open(fpath, encoding="utf-8") as f:
                    content += f.read() + "\n"

        for et in EventType:
            assert f"EventType.{et.name}" in content or f"'{et.value}'" in content, \
                f"EventType.{et.name} is not referenced in any service module or main.py"


class TestEventBusEdgeCases:
    def test_unsubscribe_twice_raises(self):
        bus = EventBus()

        def listener(event: Event) -> None:
            pass

        unsubscribe = bus.subscribe(EventType.user_message, listener)
        unsubscribe()
        with pytest.raises(ValueError):
            unsubscribe()

    def test_subscribe_same_listener_twice(self):
        bus = EventBus()
        received: list[Event] = []

        def listener(event: Event) -> None:
            received.append(event)

        bus.subscribe(EventType.user_message, listener)
        bus.subscribe(EventType.user_message, listener)
        bus.publish(Event(type=EventType.user_message))
        assert len(received) == 2

    def test_publish_async_with_sync_listener(self):
        bus = EventBus()
        received: list[Event] = []

        def listener(event: Event) -> None:
            received.append(event)

        bus.subscribe(EventType.stream_start, listener)

        async def run():
            await bus.publish_async(Event(type=EventType.stream_start))

        asyncio.run(run())
        assert len(received) == 1
