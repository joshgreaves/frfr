"""Tests for the core validation logic."""

import pytest

from frfr import validator


class TestValidateInt:
    """Tests for int validation."""

    @pytest.mark.parametrize(
        "value",
        [
            42,
            -42,
            0,
            10**100,
            -(10**100),
        ],
        ids=["positive", "negative", "zero", "large", "large_negative"],
    )
    def test_valid_int(self, value: int) -> None:
        result = validator.validate(int, value)
        assert result == value
        assert isinstance(result, int)
        assert not isinstance(result, bool)

    @pytest.mark.parametrize(
        ("value", "expected_type_name"),
        [
            # Bool rejection - critical, bool is subclass of int
            (True, "bool"),
            (False, "bool"),
            # Float rejection - even "whole" floats
            (1.5, "float"),
            (1.0, "float"),
            (0.0, "float"),
            (-1.0, "float"),
            # String rejection
            ("42", "str"),
            ("", "str"),
            # None rejection
            (None, "NoneType"),
            # Other types
            ([1], "list"),
            ({"value": 1}, "dict"),
            ((1,), "tuple"),
        ],
        ids=[
            "true",
            "false",
            "float",
            "whole_float",
            "zero_float",
            "negative_float",
            "numeric_string",
            "empty_string",
            "none",
            "list",
            "dict",
            "tuple",
        ],
    )
    def test_rejects_invalid_types(
        self, value: object, expected_type_name: str
    ) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(int, value)
        assert f"expected int, got {expected_type_name}" in str(exc_info.value)


class TestValidationError:
    """Tests for ValidationError formatting."""

    def test_error_includes_actual_value(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(int, "hello")
        assert "'hello'" in str(exc_info.value)

    def test_error_with_path(self) -> None:
        error = validator.ValidationError(int, "bad", path="data.users[0].age")
        assert "data.users[0].age" in str(error)
        assert "expected int" in str(error)

    def test_error_without_path(self) -> None:
        error = validator.ValidationError(int, "bad", path="")
        # Should not have leading dash when path is empty
        message = str(error)
        assert not message.startswith(" - ")
        assert "expected int" in message
