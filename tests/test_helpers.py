"""Unit tests for Exhibit A's own helpers (no network, no API key)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from exhibit_a.llm import extract_json, strip_reasoning


def test_strip_reasoning_removes_think_block():
    assert strip_reasoning("<think>pondering</think>answer") == "answer"


def test_strip_reasoning_handles_unterminated_block():
    assert strip_reasoning("ok<think>cut off") == "ok"


def test_extract_json_from_fenced_block():
    assert extract_json('here you go:\n```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_tolerates_surrounding_text():
    assert extract_json('sure! [{"x": 2}] done') == [{"x": 2}]


def test_extract_json_after_reasoning():
    assert extract_json('<think>hmm</think>{"ok": true}') == {"ok": True}
