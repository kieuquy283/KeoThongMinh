from __future__ import annotations

import pytest

from app.services.memory_parser import parse_memory_text


@pytest.mark.parametrize(
    ("text", "key", "value"),
    [
        ("Từ giờ gọi mình là Quy", "user_name", "Quy"),
        ("Nhớ rằng thành phố mặc định của mình là Hà Nội", "default_city", "Hà Nội"),
        ("Hãy nhớ tiền tệ mặc định của mình là VND", "default_currency", "VND"),
        ("Remember that my default city is Hanoi", "default_city", "Hanoi"),
        ("From now on, call me Quy", "user_name", "Quy"),
        ("Use a shorter answer style.", "answer_style", "short"),
        ("Dùng kiểu trả lời ngắn gọn.", "answer_style", "short"),
        ("My preferred form of address is anh", "preferred_form_of_address", "Anh"),
    ],
)
def test_memory_parser_set_commands(text: str, key: str, value: str):
    result = parse_memory_text(text)

    assert result["action"] == "set"
    assert result["key"] == key
    assert result["value"] == value
    assert result["category"] == "preference"


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("Forget my default city", "default_city"),
        ("Xóa tên của mình đi", "user_name"),
        ("Delete my default currency", "default_currency"),
        ("Xóa kiểu trả lời của mình", "answer_style"),
    ],
)
def test_memory_parser_delete_commands(text: str, key: str):
    result = parse_memory_text(text)

    assert result["action"] == "delete"
    assert result["key"] == key
    assert result["value"] is None
    assert result["category"] == "preference"


def test_memory_parser_ignores_normal_chat():
    result = parse_memory_text("Hôm nay trời đẹp quá")

    assert result["action"] == "none"
    assert result["key"] is None
    assert result["value"] is None
