"""Tests for the core validation logic."""

# TODO: Add tests for custom Validator instances (register, override handlers, composition)

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


class TestValidateFloat:
    """Tests for float validation."""

    @pytest.mark.parametrize(
        "value",
        [
            1.5,
            -1.5,
            0.0,
            float("inf"),
            float("-inf"),
        ],
        ids=["positive", "negative", "zero", "inf", "neg_inf"],
    )
    def test_valid_float(self, value: float) -> None:
        result = validator.validate(float, value)
        assert result == value
        assert isinstance(result, float)

    def test_valid_nan(self) -> None:
        result = validator.validate(float, float("nan"))
        assert result != result  # nan != nan
        assert isinstance(result, float)

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
    def test_int_coerces_to_float(self, value: int) -> None:
        result = validator.validate(float, value)
        assert result == float(value)
        assert isinstance(result, float)

    @pytest.mark.parametrize(
        ("value", "expected_type_name"),
        [
            # Bool rejection
            (True, "bool"),
            (False, "bool"),
            # String rejection
            ("1.5", "str"),
            ("", "str"),
            # None rejection
            (None, "NoneType"),
            # Other types
            ([1.5], "list"),
            ({"value": 1.5}, "dict"),
            ((1.5,), "tuple"),
        ],
        ids=[
            "true",
            "false",
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
            validator.validate(float, value)
        assert f"expected float, got {expected_type_name}" in str(exc_info.value)


class TestValidateStr:
    """Tests for str validation."""

    @pytest.mark.parametrize(
        "value",
        [
            "hello",
            "",
            "123",
            " ",
            "\U0001f600",
        ],
        ids=["simple", "empty", "numeric", "whitespace", "unicode"],
    )
    def test_valid_str(self, value: str) -> None:
        result = validator.validate(str, value)
        assert result == value
        assert isinstance(result, str)

    @pytest.mark.parametrize(
        ("value", "expected_type_name"),
        [
            (42, "int"),
            (3.14, "float"),
            (True, "bool"),
            (False, "bool"),
            (None, "NoneType"),
            (["a"], "list"),
            ({"a": 1}, "dict"),
            (b"hello", "bytes"),
        ],
        ids=["int", "float", "true", "false", "none", "list", "dict", "bytes"],
    )
    def test_rejects_invalid_types(
        self, value: object, expected_type_name: str
    ) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(str, value)
        assert f"expected str, got {expected_type_name}" in str(exc_info.value)


class TestValidateBool:
    """Tests for bool validation."""

    @pytest.mark.parametrize(
        "value",
        [True, False],
        ids=["true", "false"],
    )
    def test_valid_bool(self, value: bool) -> None:
        result = validator.validate(bool, value)
        assert result == value
        assert isinstance(result, bool)

    @pytest.mark.parametrize(
        ("value", "expected_type_name"),
        [
            (1, "int"),
            (0, "int"),
            (1.0, "float"),
            (0.0, "float"),
            ("true", "str"),
            ("", "str"),
            (None, "NoneType"),
            ([], "list"),
        ],
        ids=[
            "one",
            "zero",
            "one_float",
            "zero_float",
            "true_str",
            "empty_str",
            "none",
            "empty_list",
        ],
    )
    def test_rejects_invalid_types(
        self, value: object, expected_type_name: str
    ) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(bool, value)
        assert f"expected bool, got {expected_type_name}" in str(exc_info.value)


class TestValidateNone:
    """Tests for None validation."""

    def test_valid_none(self) -> None:
        result = validator.validate(type(None), None)
        assert result is None

    @pytest.mark.parametrize(
        ("value", "expected_type_name"),
        [
            (0, "int"),
            (0.0, "float"),
            (False, "bool"),
            ("", "str"),
            ([], "list"),
            ({}, "dict"),
        ],
        ids=["zero", "zero_float", "false", "empty_str", "empty_list", "empty_dict"],
    )
    def test_rejects_invalid_types(
        self, value: object, expected_type_name: str
    ) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(type(None), value)
        assert f"expected NoneType, got {expected_type_name}" in str(exc_info.value)


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
