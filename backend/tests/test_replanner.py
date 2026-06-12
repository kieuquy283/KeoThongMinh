from __future__ import annotations

import asyncio

import pytest
from app.services.replanner import (
    ReplanDecision,
    ReplanInput,
    ReplanOutput,
    Replanner,
    _compute_similarity,
    _detect_intent_from_text,
    _heuristic_decide,
    _prepare_input_from_session,
    decide_replan,
    get_replanner,
)
from app.services.stream_manager import StreamManager, get_stream_manager
from app.services.event_bus import EventType, Event, get_event_bus, reset_event_bus


@pytest.fixture(autouse=True)
def _reset():
    reset_event_bus()
    yield
    reset_event_bus()


class TestReplanDecision:
    def test_enum_values(self):
        assert ReplanDecision.continue_.value == "continue"
        assert ReplanDecision.restart.value == "restart"
        assert ReplanDecision.switch_intent.value == "switch_intent"
        assert ReplanDecision.ask_missing_info.value == "ask_missing_info"


class TestComputeSimilarity:
    def test_identical_texts(self):
        assert _compute_similarity("thoi tiet hom nay", "thoi tiet hom nay") == 1.0

    def test_partial_overlap(self):
        sim = _compute_similarity("thoi tiet hom nay", "hom nay the nao")
        assert 0.3 < sim < 0.8

    def test_no_overlap(self):
        assert _compute_similarity("thoi tiet", "cam on ban") == 0.0

    def test_empty_strings(self):
        assert _compute_similarity("", "hello") == 0.0
        assert _compute_similarity("hello", "") == 0.0
        assert _compute_similarity("", "") == 0.0


class TestDetectIntentFromText:
    def test_detect_weather(self):
        assert _detect_intent_from_text("thoi tiet ha noi") == "weather"

    def test_detect_time(self):
        assert _detect_intent_from_text("bay gio la may gio") == "time"

    def test_detect_currency(self):
        assert _detect_intent_from_text("ty gia usd hom nay") == "currency"

    def test_detect_search(self):
        assert _detect_intent_from_text("tim kiem thong tin") == "general_search"

    def test_detect_news(self):
        assert _detect_intent_from_text("tin tuc hom nay") == "news_search"

    def test_no_intent(self):
        assert _detect_intent_from_text("ban la ai") is None


class TestHeuristicDecide:
    def test_follow_up_continues(self):
        input_data = ReplanInput(
            partial_response="Thoi tiet hom nay tai Ha Noi",
            new_input="nhiet do bao nhieu",
            intent="weather",
        )
        output = _heuristic_decide(input_data)
        assert output.decision == ReplanDecision.continue_

    def test_new_topic_restarts(self):
        input_data = ReplanInput(
            partial_response="Thoi tiet hom nay tai Ha Noi",
            new_input="thoi bo qua, chuyen khac di",
            intent="weather",
        )
        output = _heuristic_decide(input_data)
        assert output.decision == ReplanDecision.restart

    def test_switch_intent(self):
        input_data = ReplanInput(
            partial_response="Thoi tiet hom nay tai Ha Noi",
            new_input="ty gia usd hom nay the nao",
            intent="weather",
        )
        output = _heuristic_decide(input_data)
        assert output.decision == ReplanDecision.switch_intent
        assert output.new_intent == "currency"

    def test_missing_info_with_location(self):
        input_data = ReplanInput(
            partial_response="Minh can biet ban muon xem thoi tiet o dau",
            new_input="o Da Nang",
            intent="weather",
            missing_field="location",
        )
        output = _heuristic_decide(input_data)
        assert output.decision == ReplanDecision.continue_

    def test_missing_info_still_short(self):
        input_data = ReplanInput(
            partial_response="Minh can biet ban muon xem thoi tiet o dau",
            new_input="Ha Noi",
            intent="weather",
            missing_field="location",
        )
        output = _heuristic_decide(input_data)
        assert output.decision == ReplanDecision.continue_

    def test_missing_info_unrelated_answer(self):
        input_data = ReplanInput(
            partial_response="Minh can biet ban muon xem gio o thanh pho nao",
            new_input="khong muon xem nua",
            intent="time",
            missing_field="timezone",
        )
        output = _heuristic_decide(input_data)
        assert output.decision == ReplanDecision.continue_

    def test_missing_info_short_unrelated(self):
        input_data = ReplanInput(
            partial_response="Minh can biet ban muon xem gio o thanh pho nao",
            new_input="khong",
            intent="time",
            missing_field="timezone",
        )
        output = _heuristic_decide(input_data)
        assert output.decision == ReplanDecision.ask_missing_info

    def test_unavailable_tool_restarts(self):
        input_data = ReplanInput(
            partial_response="",
            new_input="thoi tiet hom nay",
            intent="weather",
            tool_result={"is_available": False},
        )
        output = _heuristic_decide(input_data)
        assert output.decision == ReplanDecision.restart

    def test_intent_none_with_partial_switch(self):
        input_data = ReplanInput(
            partial_response="Minh da nghe roi",
            new_input="tim kiem thong tin ve python",
            intent="none",
        )
        output = _heuristic_decide(input_data)
        assert output.decision == ReplanDecision.switch_intent
        assert output.new_intent == "general_search"

    def test_intent_none_new_topic_restarts(self):
        input_data = ReplanInput(
            partial_response="Minh da nghe roi",
            new_input="thoi bo qua, cam on ban",
            intent="none",
        )
        output = _heuristic_decide(input_data)
        assert output.decision == ReplanDecision.restart
        assert output.reason == "new_topic"

    def test_short_input_without_trigger(self):
        input_data = ReplanInput(
            partial_response="Minh da nghe roi",
            new_input="cam on",
            intent="none",
        )
        output = _heuristic_decide(input_data)
        assert output.decision == ReplanDecision.restart

    def test_follow_up_without_partial(self):
        input_data = ReplanInput(
            partial_response="",
            new_input="ke tiep di",
            intent="none",
        )
        output = _heuristic_decide(input_data)
        assert output.decision == ReplanDecision.continue_


class TestDecideReplan:
    def test_decide_replan_with_local_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "local")
        from app.config import get_settings
        get_settings.cache_clear()

        input_data = ReplanInput(
            partial_response="Thoi tiet hom nay",
            new_input="ty gia usd",
            intent="weather",
        )

        async def run():
            return await decide_replan(input_data)

        output = asyncio.run(run())
        assert output.decision in (ReplanDecision.continue_, ReplanDecision.restart, ReplanDecision.switch_intent)

        get_settings.cache_clear()

    def test_decide_replan_with_mock_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        from app.config import get_settings
        get_settings.cache_clear()

        input_data = ReplanInput(
            partial_response="",
            new_input="thoi tiet ha noi",
            intent="weather",
        )

        async def run():
            return await decide_replan(input_data)

        output = asyncio.run(run())
        assert output.decision == ReplanDecision.continue_

        get_settings.cache_clear()

    def test_decide_replan_switch_intent_mock(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        from app.config import get_settings
        get_settings.cache_clear()

        input_data = ReplanInput(
            partial_response="",
            new_input="ty gia usd",
            intent="weather",
        )

        async def run():
            return await decide_replan(input_data)

        output = asyncio.run(run())
        assert output.decision == ReplanDecision.switch_intent
        assert output.new_intent == "currency"

        get_settings.cache_clear()


class TestReplanner:
    def test_subscribe_to_events(self):
        replanner = Replanner()
        replanner.subscribe_to_events()
        bus = get_event_bus()

        call_count = 0

        def track(event):
            nonlocal call_count
            call_count += 1

        bus.subscribe(EventType.interrupt, track)

        bus.publish(Event(type=EventType.interrupt, payload={"text": "test"}, session_id="s1"))
        assert call_count == 1

    def test_interrupt_event_stores_replan_context(self):
        stream_mgr = get_stream_manager()
        session = stream_mgr.create_session("test-session")
        session.start()
        session.add_token("Thoi tiet hom nay tai")

        replanner = Replanner()
        replanner.subscribe_to_events()

        bus = get_event_bus()
        event = Event(type=EventType.interrupt, payload={
            "text": "bo qua thoi",
            "partial_response": "Thoi tiet hom nay tai",
            "intent": "weather",
        }, session_id="test-session")

        replanner._on_interrupt(event)

        assert session.replan_context is not None
        assert session.replan_context["decision"] == "restart"
        stream_mgr.remove_session("test-session")

    def test_replanning_event_stores_context(self):
        stream_mgr = get_stream_manager()
        session = stream_mgr.create_session("test-session")
        session.start()

        replanner = Replanner()
        replanner.subscribe_to_events()

        replanner._on_replanning(Event(type=EventType.replanning, payload={
            "tool": "weather",
            "reason": "missing_info",
            "tool_result": {"is_available": True},
        }, session_id="test-session"))

        assert session.replan_context is not None
        stream_mgr.remove_session("test-session")

    def test_get_replanner_singleton(self):
        r1 = get_replanner()
        r2 = get_replanner()
        assert r1 is r2

    def test_prepare_input_from_session_without_session(self):
        input_data = _prepare_input_from_session(
            session_id="nonexistent",
            new_input="test",
        )
        assert input_data.new_input == "test"
        assert input_data.partial_response == ""
        assert input_data.conversation_turns == []


class TestReplanDataclasses:
    def test_replan_input_defaults(self):
        inp = ReplanInput()
        assert inp.partial_response == ""
        assert inp.new_input == ""
        assert inp.conversation_turns == []
        assert inp.memory_context == {}
        assert inp.intent == "none"
        assert inp.tool_result is None
        assert inp.missing_field is None

    def test_replan_output_defaults(self):
        out = ReplanOutput(decision=ReplanDecision.continue_)
        assert out.decision == ReplanDecision.continue_
        assert out.reason == ""
        assert out.new_intent is None
        assert out.explanation == ""

    def test_replan_output_switch_intent(self):
        out = ReplanOutput(
            decision=ReplanDecision.switch_intent,
            reason="tool_change",
            new_intent="weather",
            explanation="Nguoi dung muon dung cong cu khac",
        )
        assert out.new_intent == "weather"
        assert out.reason == "tool_change"
