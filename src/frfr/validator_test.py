"""Tests for the core validation logic."""

# TODO: Add tests for custom Validator instances (register, override handlers, composition)

import collections
import types
from typing import Any, NotRequired, Required, TypedDict, Union

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


class TestValidateAny:
    """Tests for Any validation."""

    @pytest.mark.parametrize(
        "value",
        [
            42,
            3.14,
            "hello",
            True,
            None,
            [1, 2, 3],
            {"key": "value"},
            (1, 2),
        ],
        ids=["int", "float", "str", "bool", "none", "list", "dict", "tuple"],
    )
    def test_accepts_any_type(self, value: object) -> None:
        # Any is a special form, not a type - pyright doesn't like it as type[T].
        # This is an unlikely use-case anyway; nobody validates against Any in practice.
        result = validator.validate(Any, value)  # pyright: ignore[reportArgumentType]
        assert result is value  # Returns the exact same object


class TestValidateList:
    """Tests for list validation."""

    # Unparameterized list
    def test_unparameterized_list(self) -> None:
        result = validator.validate(list, [1, "two", 3.0])
        assert result == [1, "two", 3.0]
        assert isinstance(result, list)

    def test_empty_list(self) -> None:
        result = validator.validate(list, [])
        assert result == []
        assert isinstance(result, list)

    # Always returns new object (mutable containers are copied)
    def test_returns_new_list_unparameterized(self) -> None:
        original = [1, 2, 3]
        result = validator.validate(list, original)
        assert result == original
        assert result is not original

    def test_returns_new_list_parameterized(self) -> None:
        original = [1, 2, 3]
        result = validator.validate(list[int], original)
        assert result == original
        assert result is not original

    # Parameterized list[T]
    def test_list_of_int(self) -> None:
        result = validator.validate(list[int], [1, 2, 3])
        assert result == [1, 2, 3]
        assert isinstance(result, list)
        assert all(isinstance(x, int) for x in result)

    def test_list_of_str(self) -> None:
        result = validator.validate(list[str], ["a", "b", "c"])
        assert result == ["a", "b", "c"]
        assert isinstance(result, list)

    def test_empty_parameterized_list(self) -> None:
        result = validator.validate(list[int], [])
        assert result == []
        assert isinstance(result, list)

    # Coercion within elements
    def test_list_of_float_coerces_int(self) -> None:
        result = validator.validate(list[float], [1, 2, 3])
        assert result == [1.0, 2.0, 3.0]
        assert all(isinstance(x, float) for x in result)

    # Nested lists
    def test_nested_list(self) -> None:
        result = validator.validate(list[list[int]], [[1, 2], [3, 4]])
        assert result == [[1, 2], [3, 4]]
        assert isinstance(result, list)
        assert all(isinstance(inner, list) for inner in result)

    # Tuple coercion
    def test_tuple_coerces_to_list(self) -> None:
        result = validator.validate(list, (1, 2, 3))
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_tuple_coerces_to_parameterized_list(self) -> None:
        result = validator.validate(list[int], (1, 2, 3))
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_nested_tuple_coerces_to_list(self) -> None:
        result = validator.validate(list[list[int]], [(1, 2), (3, 4)])
        assert result == [[1, 2], [3, 4]]
        assert isinstance(result, list)
        assert all(isinstance(inner, list) for inner in result)

    # Rejection tests
    @pytest.mark.parametrize(
        ("value", "expected_type_name"),
        [
            ("not a list", "str"),
            (123, "int"),
            ({"a": 1}, "dict"),
            (None, "NoneType"),
        ],
        ids=["str", "int", "dict", "none"],
    )
    def test_rejects_non_list(self, value: object, expected_type_name: str) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(list, value)
        assert f"expected list, got {expected_type_name}" in str(exc_info.value)

    def test_rejects_invalid_element_type(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(list[int], [1, 2, "three"])
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_bool_in_int_list(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(list[int], [1, True, 3])
        assert "expected int, got bool" in str(exc_info.value)


class TestValidateTuple:
    """Tests for tuple validation."""

    # Unparameterized tuple
    def test_unparameterized_tuple(self) -> None:
        result = validator.validate(tuple, (1, "two", 3.0))
        assert result == (1, "two", 3.0)
        assert isinstance(result, tuple)

    def test_empty_tuple(self) -> None:
        result = validator.validate(tuple, ())
        assert result == ()
        assert isinstance(result, tuple)

    # List coercion
    def test_list_coerces_to_tuple(self) -> None:
        result = validator.validate(tuple, [1, 2, 3])
        assert result == (1, 2, 3)
        assert isinstance(result, tuple)

    # Homogeneous tuple[T, ...]
    def test_homogeneous_tuple(self) -> None:
        result = validator.validate(tuple[int, ...], (1, 2, 3))
        assert result == (1, 2, 3)
        assert isinstance(result, tuple)
        assert all(isinstance(x, int) for x in result)

    def test_homogeneous_tuple_empty(self) -> None:
        result = validator.validate(tuple[int, ...], ())
        assert result == ()
        assert isinstance(result, tuple)

    def test_homogeneous_tuple_coerces_elements(self) -> None:
        result = validator.validate(tuple[float, ...], (1, 2, 3))
        assert result == (1.0, 2.0, 3.0)
        assert all(isinstance(x, float) for x in result)

    def test_homogeneous_tuple_from_list(self) -> None:
        result = validator.validate(tuple[int, ...], [1, 2, 3])
        assert result == (1, 2, 3)
        assert isinstance(result, tuple)

    # Fixed-length tuple[T1, T2, ...]
    def test_fixed_tuple(self) -> None:
        result = validator.validate(tuple[int, str, bool], (1, "two", True))
        assert result == (1, "two", True)
        assert isinstance(result, tuple)

    def test_fixed_tuple_single_element(self) -> None:
        result = validator.validate(tuple[int], (42,))
        assert result == (42,)
        assert isinstance(result, tuple)

    def test_fixed_tuple_coerces_elements(self) -> None:
        result = validator.validate(tuple[float, float], (1, 2))
        assert result == (1.0, 2.0)
        assert all(isinstance(x, float) for x in result)

    def test_fixed_tuple_from_list(self) -> None:
        result = validator.validate(tuple[int, str], [1, "two"])
        assert result == (1, "two")
        assert isinstance(result, tuple)

    # Nested tuples
    def test_nested_tuple(self) -> None:
        result = validator.validate(tuple[tuple[int, ...], ...], ((1, 2), (3, 4)))
        assert result == ((1, 2), (3, 4))
        assert isinstance(result, tuple)
        assert all(isinstance(inner, tuple) for inner in result)

    # Rejection tests
    @pytest.mark.parametrize(
        ("value", "expected_type_name"),
        [
            ("not a tuple", "str"),
            (123, "int"),
            ({"a": 1}, "dict"),
            (None, "NoneType"),
        ],
        ids=["str", "int", "dict", "none"],
    )
    def test_rejects_non_tuple(self, value: object, expected_type_name: str) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(tuple, value)
        assert f"expected tuple, got {expected_type_name}" in str(exc_info.value)

    def test_rejects_invalid_element_in_homogeneous(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(tuple[int, ...], (1, 2, "three"))
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_wrong_length_fixed_tuple(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(tuple[int, str], (1, "two", 3))
        assert "expected tuple" in str(exc_info.value)

    def test_rejects_too_short_fixed_tuple(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(tuple[int, str, bool], (1, "two"))
        assert "expected tuple" in str(exc_info.value)

    def test_rejects_invalid_element_in_fixed_tuple(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(tuple[int, str], (1, 2))
        assert "expected str, got int" in str(exc_info.value)

    def test_rejects_bool_in_int_tuple(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(tuple[int, ...], (1, True, 3))
        assert "expected int, got bool" in str(exc_info.value)


class TestValidateDict:
    """Tests for dict validation."""

    # Unparameterized dict
    def test_unparameterized_dict(self) -> None:
        result = validator.validate(dict, {"a": 1, "b": "two"})
        assert result == {"a": 1, "b": "two"}
        assert isinstance(result, dict)

    def test_empty_dict(self) -> None:
        result = validator.validate(dict, {})
        assert result == {}
        assert isinstance(result, dict)

    # Always returns new dict
    def test_returns_new_dict(self) -> None:
        original = {"a": 1}
        result = validator.validate(dict, original)
        assert result == original
        assert result is not original

    def test_returns_new_dict_parameterized(self) -> None:
        original = {"a": 1}
        result = validator.validate(dict[str, int], original)
        assert result == original
        assert result is not original

    # Parameterized dict[K, V]
    def test_dict_str_int(self) -> None:
        result = validator.validate(dict[str, int], {"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}
        assert isinstance(result, dict)

    def test_dict_int_str(self) -> None:
        result = validator.validate(dict[int, str], {1: "a", 2: "b"})
        assert result == {1: "a", 2: "b"}
        assert isinstance(result, dict)

    def test_empty_parameterized_dict(self) -> None:
        result = validator.validate(dict[str, int], {})
        assert result == {}
        assert isinstance(result, dict)

    # Key coercion (same rules as values)
    def test_dict_key_coercion(self) -> None:
        result = validator.validate(dict[float, str], {1: "a", 2: "b"})
        assert result == {1.0: "a", 2.0: "b"}
        assert all(isinstance(k, float) for k in result.keys())

    # Value coercion
    def test_dict_value_coercion(self) -> None:
        result = validator.validate(dict[str, float], {"a": 1, "b": 2})
        assert result == {"a": 1.0, "b": 2.0}
        assert all(isinstance(v, float) for v in result.values())

    # Nested dicts
    def test_nested_dict(self) -> None:
        result = validator.validate(dict[str, dict[str, int]], {"outer": {"inner": 42}})
        assert result == {"outer": {"inner": 42}}
        assert isinstance(result["outer"], dict)

    # Mapping coercion
    def test_ordered_dict_coerces_to_dict(self) -> None:
        data = collections.OrderedDict([("a", 1), ("b", 2)])
        result = validator.validate(dict[str, int], data)
        assert result == {"a": 1, "b": 2}
        assert type(result) is dict

    def test_mapping_proxy_coerces_to_dict(self) -> None:
        data = types.MappingProxyType({"a": 1, "b": 2})
        result = validator.validate(dict[str, int], data)
        assert result == {"a": 1, "b": 2}
        assert type(result) is dict

    def test_defaultdict_coerces_to_dict(self) -> None:
        data: collections.defaultdict[str, int] = collections.defaultdict(int)
        data["a"] = 1
        data["b"] = 2
        result = validator.validate(dict[str, int], data)
        assert result == {"a": 1, "b": 2}
        assert type(result) is dict

    def test_counter_coerces_to_dict(self) -> None:
        data = collections.Counter({"a": 1, "b": 2})
        result = validator.validate(dict[str, int], data)
        assert result == {"a": 1, "b": 2}
        assert type(result) is dict

    # Rejection tests
    @pytest.mark.parametrize(
        ("value", "expected_type_name"),
        [
            ("not a dict", "str"),
            (123, "int"),
            ([("a", 1)], "list"),
            (None, "NoneType"),
            ((("a", 1),), "tuple"),
        ],
        ids=["str", "int", "list", "none", "tuple"],
    )
    def test_rejects_non_dict(self, value: object, expected_type_name: str) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(dict, value)
        assert f"expected dict, got {expected_type_name}" in str(exc_info.value)

    def test_rejects_invalid_key_type(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(dict[str, int], {1: 1})
        assert "expected str, got int" in str(exc_info.value)

    def test_rejects_invalid_value_type(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(dict[str, int], {"a": "not an int"})
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_bool_key_for_int_key(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(dict[int, str], {True: "a"})
        assert "expected int, got bool" in str(exc_info.value)


class TestValidateTypedDict:
    """Tests for TypedDict validation."""

    def test_simple_typed_dict(self) -> None:
        class User(TypedDict):
            name: str
            age: int

        result = validator.validate(User, {"name": "bestie", "age": 25})
        assert result == {"name": "bestie", "age": 25}
        assert isinstance(result, dict)

    def test_typed_dict_coerces_values(self) -> None:
        class Stats(TypedDict):
            score: float
            count: float

        result = validator.validate(Stats, {"score": 100, "count": 5})
        assert result == {"score": 100.0, "count": 5.0}
        assert all(isinstance(v, float) for v in result.values())

    def test_typed_dict_with_optional_keys(self) -> None:
        class Config(TypedDict):
            name: str
            debug: NotRequired[bool]

        # With optional key present
        result = validator.validate(Config, {"name": "app", "debug": True})
        assert result == {"name": "app", "debug": True}

        # Without optional key
        result = validator.validate(Config, {"name": "app"})
        assert result == {"name": "app"}

    def test_typed_dict_with_required_keys(self) -> None:
        class Config(TypedDict, total=False):
            name: Required[str]
            debug: bool

        result = validator.validate(Config, {"name": "app"})
        assert result == {"name": "app"}

    def test_nested_typed_dict(self) -> None:
        class Address(TypedDict):
            city: str
            zip_code: str

        class Person(TypedDict):
            name: str
            address: Address

        result = validator.validate(
            Person, {"name": "bestie", "address": {"city": "NYC", "zip_code": "10001"}}
        )
        assert result == {
            "name": "bestie",
            "address": {"city": "NYC", "zip_code": "10001"},
        }

    def test_typed_dict_from_mapping(self) -> None:
        class User(TypedDict):
            name: str
            age: int

        data = collections.OrderedDict([("name", "bestie"), ("age", 25)])
        result = validator.validate(User, data)
        assert result == {"name": "bestie", "age": 25}
        assert type(result) is dict

    # Rejection tests
    def test_rejects_missing_required_key(self) -> None:
        class User(TypedDict):
            name: str
            age: int

        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(User, {"name": "bestie"})
        assert "age" in str(exc_info.value)

    def test_rejects_wrong_value_type(self) -> None:
        class User(TypedDict):
            name: str
            age: int

        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(User, {"name": "bestie", "age": "twenty five"})
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_extra_keys(self) -> None:
        class User(TypedDict):
            name: str

        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(User, {"name": "bestie", "extra": "field"})
        assert "extra" in str(exc_info.value)

    def test_rejects_non_mapping(self) -> None:
        class User(TypedDict):
            name: str

        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(User, "not a dict")
        assert "expected User, got str" in str(exc_info.value)


class TestValidateUnion:
    """Tests for Union validation.

    Union types are tried in declaration order. The first type that
    successfully validates (including coercion) wins.

    Note: pyright complains about UnionType not being type[T], but this works
    at runtime. All validate() calls use pyright: ignore for this reason.
    """

    # Basic union - Union[A, B] syntax
    def test_union_first_type_matches(self) -> None:
        result = validator.validate(Union[int, str], 42)  # type: ignore[arg-type]
        assert result == 42
        assert isinstance(result, int)

    def test_union_second_type_matches(self) -> None:
        result = validator.validate(Union[int, str], "hello")  # type: ignore[arg-type]
        assert result == "hello"
        assert isinstance(result, str)

    # Basic union - A | B syntax
    def test_pipe_union_first_type_matches(self) -> None:
        result = validator.validate(int | str, 42)  # type: ignore[arg-type]
        assert result == 42
        assert isinstance(result, int)

    def test_pipe_union_second_type_matches(self) -> None:
        result = validator.validate(int | str, "hello")  # type: ignore[arg-type]
        assert result == "hello"
        assert isinstance(result, str)

    # Order matters with coercion
    def test_union_float_int_coerces_to_float(self) -> None:
        # int coerces to float, so float wins when it comes first
        result = validator.validate(float | int, 42)  # type: ignore[arg-type]
        assert result == 42.0
        assert isinstance(result, float)

    def test_union_int_float_keeps_int(self) -> None:
        # int comes first and matches exactly, no coercion needed
        result = validator.validate(int | float, 42)  # type: ignore[arg-type]
        assert result == 42
        assert isinstance(result, int)

    def test_union_float_str_coerces_int_to_float(self) -> None:
        # int isn't in union, but coerces to float
        result = validator.validate(float | str, 1)  # type: ignore[arg-type]
        assert result == 1.0
        assert isinstance(result, float)

    # Union with None (similar to Optional)
    def test_union_with_none_accepts_value(self) -> None:
        result = validator.validate(Union[int, None], 42)  # type: ignore[arg-type]
        assert result == 42
        assert isinstance(result, int)

    def test_union_with_none_accepts_none(self) -> None:
        result = validator.validate(Union[int, None], None)  # type: ignore[arg-type]
        assert result is None

    # Optional[T] using A | None syntax
    def test_optional_accepts_value(self) -> None:
        result = validator.validate(int | None, 42)  # type: ignore[arg-type]
        assert result == 42
        assert isinstance(result, int)

    def test_optional_accepts_none(self) -> None:
        result = validator.validate(int | None, None)  # type: ignore[arg-type]
        assert result is None

    def test_optional_rejects_wrong_type(self) -> None:
        with pytest.raises(validator.ValidationError):
            validator.validate(int | None, "not an int")  # type: ignore[arg-type]

    # Optional with coercion
    def test_optional_float_coerces_int(self) -> None:
        result = validator.validate(float | None, 42)  # type: ignore[arg-type]
        assert result == 42.0
        assert isinstance(result, float)

    # Complex unions
    def test_union_three_types(self) -> None:
        result = validator.validate(int | str | list[int], [1, 2, 3])  # type: ignore[arg-type]
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_union_with_list(self) -> None:
        result = validator.validate(str | list[int], [1, 2, 3])  # type: ignore[arg-type]
        assert result == [1, 2, 3]

    def test_union_with_dict(self) -> None:
        result = validator.validate(str | dict[str, int], {"a": 1})  # type: ignore[arg-type]
        assert result == {"a": 1}

    # Nested unions (Python flattens these)
    def test_nested_union_flattened(self) -> None:
        # Union[Union[int, str], bool] is flattened to Union[int, str, bool]
        result = validator.validate(Union[Union[int, str], bool], True)  # type: ignore[arg-type]
        # bool comes last, but int would reject bool, str would reject bool
        # so bool should match
        assert result is True
        assert isinstance(result, bool)

    # Bool handling in unions
    def test_union_int_str_rejects_bool(self) -> None:
        # bool is rejected by int (strict), and rejected by str
        with pytest.raises(validator.ValidationError):
            validator.validate(int | str, True)  # type: ignore[arg-type]

    def test_union_with_bool_accepts_bool(self) -> None:
        result = validator.validate(int | bool, True)  # type: ignore[arg-type]
        # int rejects bool, so bool matches
        assert result is True
        assert isinstance(result, bool)

    # Rejection tests
    def test_rejects_when_no_type_matches(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(int | str, [1, 2, 3])  # type: ignore[arg-type]
        # Error message format may vary
        error_msg = str(exc_info.value)
        assert "int" in error_msg or "str" in error_msg

    def test_rejects_none_when_not_in_union(self) -> None:
        with pytest.raises(validator.ValidationError):
            validator.validate(int | str, None)  # type: ignore[arg-type]


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
