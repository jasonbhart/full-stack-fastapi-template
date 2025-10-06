"""Test JSON validation for agent tools.

This test ensures HTTPPostInput can be instantiated and properly validates
JSON-serializable data while rejecting non-compliant values.

NOTE: These tests will be skipped until langchain_core is installed (task 22).
"""

import pytest

# Skip all tests in this module if langchain_core is not available
pytest.importorskip("langchain_core.tools")


def test_httppostinput_import() -> None:
    """Test that HTTPPostInput can be imported without RecursionError."""
    from app.agents.tools import HTTPPostInput

    assert HTTPPostInput is not None


def test_httppostinput_accepts_valid_json_types() -> None:
    """Test that HTTPPostInput accepts all valid JSON types."""
    from app.agents.tools import HTTPPostInput

    # Dict payload
    obj1 = HTTPPostInput(url="http://example.com", json_data={"key": "value"})
    assert obj1.json_data == {"key": "value"}

    # List payload
    obj2 = HTTPPostInput(url="http://example.com", json_data=["a", "b", "c"])
    assert obj2.json_data == ["a", "b", "c"]

    # String payload
    obj3 = HTTPPostInput(url="http://example.com", json_data="string payload")
    assert obj3.json_data == "string payload"

    # Number payload
    obj4 = HTTPPostInput(url="http://example.com", json_data=42)
    assert obj4.json_data == 42

    # Boolean payload
    obj5 = HTTPPostInput(url="http://example.com", json_data=True)
    assert obj5.json_data is True

    # None/null payload
    obj6 = HTTPPostInput(url="http://example.com", json_data=None)
    assert obj6.json_data is None


def test_httppostinput_rejects_nan() -> None:
    """Test that HTTPPostInput rejects NaN values (not valid JSON)."""
    from app.agents.tools import HTTPPostInput

    with pytest.raises(ValueError, match="json_data must be valid JSON"):
        HTTPPostInput(url="http://example.com", json_data=float("nan"))


def test_httppostinput_rejects_infinity() -> None:
    """Test that HTTPPostInput rejects Infinity values (not valid JSON)."""
    from app.agents.tools import HTTPPostInput

    with pytest.raises(ValueError, match="json_data must be valid JSON"):
        HTTPPostInput(url="http://example.com", json_data=float("inf"))

    with pytest.raises(ValueError, match="json_data must be valid JSON"):
        HTTPPostInput(url="http://example.com", json_data=float("-inf"))


def test_httppostinput_rejects_non_serializable() -> None:
    """Test that HTTPPostInput rejects non-JSON-serializable types."""
    from app.agents.tools import HTTPPostInput

    # Sets are not JSON-serializable
    with pytest.raises(ValueError, match="json_data must be valid JSON"):
        HTTPPostInput(url="http://example.com", json_data={1, 2, 3})  # type: ignore[arg-type]


def test_httppostinput_nested_structures() -> None:
    """Test that HTTPPostInput accepts nested JSON structures."""
    from app.agents.tools import HTTPPostInput

    nested_data = {
        "users": [
            {"id": 1, "name": "Alice", "active": True},
            {"id": 2, "name": "Bob", "active": False},
        ],
        "metadata": {"count": 2, "page": 1},
    }

    obj = HTTPPostInput(url="http://example.com", json_data=nested_data)  # type: ignore[arg-type]
    assert obj.json_data == nested_data
