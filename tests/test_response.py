"""Tests for reading Gemini response bodies."""

import pytest

from news_collector.response import response_json


def test_parses_json() -> None:
    assert response_json('{"a": 1}', "extract") == {"a": 1}


@pytest.mark.parametrize("text", [None, ""])
def test_missing_text_names_the_call(text: str | None) -> None:
    with pytest.raises(ValueError, match="no text for extract"):
        response_json(text, "extract")
