"""Tests for the core validation logic."""

# TODO: Add tests for custom Validator instances (register, override handlers, composition)

import collections
import dataclasses
import types
from typing import Any, Literal, NotRequired, Required, TypedDict, Union

import pytest

from frfr import validator


# ---------------------------------------------------------------------------
# Shared data structures used across multiple test classes.
# Named with type suffix so dataclass/TypedDict pairs are easy to compare.
# ---------------------------------------------------------------------------


class UserTypedDict(TypedDict):
    name: str
    age: int


class StatsTypedDict(TypedDict):
    score: float
    count: float


class ConfigTypedDict(TypedDict):
    name: str
    debug: NotRequired[bool]


class ConfigTotalFalseTypedDict(TypedDict, total=False):
    name: Required[str]
    debug: bool


class AddressTypedDict(TypedDict):
    city: str
    zip_code: str


class PersonTypedDict(TypedDict):
    name: str
    address: AddressTypedDict


@dataclasses.dataclass
class UserDataclass:
    name: str
    age: int


@dataclasses.dataclass
class StatsDataclass:
    score: float
    count: float


@dataclasses.dataclass
class AddressDataclass:
    city: str
    zip_code: str


@dataclasses.dataclass
class PersonDataclass:
    name: str
    address: AddressDataclass


@dataclasses.dataclass
class UserWithDefaultsDataclass:
    name: str
    age: int = 0
    active: bool = True


@dataclasses.dataclass
class UserWithFactoryDataclass:
    name: str
    tags: list[str] = dataclasses.field(default_factory=list)


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
        result = validator.validate(UserTypedDict, {"name": "bestie", "age": 25})
        assert result == {"name": "bestie", "age": 25}
        assert isinstance(result, dict)

    def test_typed_dict_coerces_values(self) -> None:
        result = validator.validate(StatsTypedDict, {"score": 100, "count": 5})
        assert result == {"score": 100.0, "count": 5.0}
        assert all(isinstance(v, float) for v in result.values())

    def test_typed_dict_with_optional_keys(self) -> None:
        # With optional key present
        result = validator.validate(ConfigTypedDict, {"name": "app", "debug": True})
        assert result == {"name": "app", "debug": True}

        # Without optional key
        result = validator.validate(ConfigTypedDict, {"name": "app"})
        assert result == {"name": "app"}

    def test_typed_dict_with_required_keys(self) -> None:
        result = validator.validate(ConfigTotalFalseTypedDict, {"name": "app"})
        assert result == {"name": "app"}

    def test_nested_typed_dict(self) -> None:
        result = validator.validate(
            PersonTypedDict,
            {"name": "bestie", "address": {"city": "NYC", "zip_code": "10001"}},
        )
        assert result == {
            "name": "bestie",
            "address": {"city": "NYC", "zip_code": "10001"},
        }

    def test_typed_dict_from_mapping(self) -> None:
        data = collections.OrderedDict([("name", "bestie"), ("age", 25)])
        result = validator.validate(UserTypedDict, data)
        assert result == {"name": "bestie", "age": 25}
        assert type(result) is dict

    # Rejection tests
    def test_rejects_missing_required_key(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserTypedDict, {"name": "bestie"})
        assert "age" in str(exc_info.value)

    def test_rejects_wrong_value_type(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserTypedDict, {"name": "bestie", "age": "twenty five"})
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_extra_keys(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserTypedDict, {"name": "bestie", "extra": "field"})
        assert "extra" in str(exc_info.value)

    def test_rejects_non_mapping(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserTypedDict, "not a dict")
        assert "expected UserTypedDict, got str" in str(exc_info.value)


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


class TestValidateSet:
    """Tests for set validation.

    Only accepts set/frozenset as input - no coercion from list/tuple
    since that could lose data (duplicates) and ordering doesn't transfer.
    """

    # Unparameterized set
    def test_unparameterized_set(self) -> None:
        result = validator.validate(set, {1, 2, 3})
        assert result == {1, 2, 3}
        assert isinstance(result, set)

    def test_empty_set(self) -> None:
        result = validator.validate(set, set())
        assert result == set()
        assert isinstance(result, set)

    # Always returns new set (mutable container)
    def test_returns_new_set(self) -> None:
        original = {1, 2, 3}
        result = validator.validate(set, original)
        assert result == original
        assert result is not original

    def test_returns_new_set_parameterized(self) -> None:
        original = {1, 2, 3}
        result = validator.validate(set[int], original)
        assert result == original
        assert result is not original

    # Parameterized set[T]
    def test_set_of_int(self) -> None:
        result = validator.validate(set[int], {1, 2, 3})
        assert result == {1, 2, 3}
        assert isinstance(result, set)
        assert all(isinstance(x, int) for x in result)

    def test_set_of_str(self) -> None:
        result = validator.validate(set[str], {"a", "b", "c"})
        assert result == {"a", "b", "c"}
        assert isinstance(result, set)

    # Frozenset coerces to set (lossless, both are set-like)
    def test_frozenset_coerces_to_set(self) -> None:
        result = validator.validate(set[int], frozenset({1, 2, 3}))
        assert result == {1, 2, 3}
        assert isinstance(result, set)

    # Element coercion (int -> float still works)
    def test_set_element_coercion(self) -> None:
        result = validator.validate(set[float], {1, 2, 3})
        assert result == {1.0, 2.0, 3.0}
        assert all(isinstance(x, float) for x in result)

    # Rejection tests - no list/tuple coercion
    def test_rejects_list(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(set, [1, 2, 3])
        assert "expected set, got list" in str(exc_info.value)

    def test_rejects_tuple(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(set, (1, 2, 3))
        assert "expected set, got tuple" in str(exc_info.value)

    @pytest.mark.parametrize(
        ("value", "expected_type_name"),
        [
            ("not a set", "str"),
            (123, "int"),
            ({"a": 1}, "dict"),
            (None, "NoneType"),
        ],
        ids=["str", "int", "dict", "none"],
    )
    def test_rejects_non_set(self, value: object, expected_type_name: str) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(set, value)
        assert f"expected set, got {expected_type_name}" in str(exc_info.value)

    def test_rejects_invalid_element_type(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(set[int], {1, 2, "three"})
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_bool_in_int_set(self) -> None:
        # Note: {1, True} collapses to {1} in Python since True == 1
        # Use {True, 2} which becomes {True, 2} to test bool rejection
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(set[int], {True, 2, 3})
        assert "expected int, got bool" in str(exc_info.value)


class TestValidateFrozenset:
    """Tests for frozenset validation.

    Only accepts set/frozenset as input - same reasoning as set.
    """

    # Unparameterized frozenset
    def test_unparameterized_frozenset(self) -> None:
        result = validator.validate(frozenset, frozenset({1, 2, 3}))
        assert result == frozenset({1, 2, 3})
        assert isinstance(result, frozenset)

    def test_empty_frozenset(self) -> None:
        result = validator.validate(frozenset, frozenset())
        assert result == frozenset()
        assert isinstance(result, frozenset)

    # Parameterized frozenset[T]
    def test_frozenset_of_int(self) -> None:
        result = validator.validate(frozenset[int], frozenset({1, 2, 3}))
        assert result == frozenset({1, 2, 3})
        assert isinstance(result, frozenset)
        assert all(isinstance(x, int) for x in result)

    # Set coerces to frozenset (lossless)
    def test_set_coerces_to_frozenset(self) -> None:
        result = validator.validate(frozenset[int], {1, 2, 3})
        assert result == frozenset({1, 2, 3})
        assert isinstance(result, frozenset)

    # Element coercion
    def test_frozenset_element_coercion(self) -> None:
        result = validator.validate(frozenset[float], {1, 2, 3})
        assert result == frozenset({1.0, 2.0, 3.0})
        assert all(isinstance(x, float) for x in result)

    # Rejection tests - no list/tuple coercion
    def test_rejects_list(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(frozenset, [1, 2, 3])
        assert "expected frozenset, got list" in str(exc_info.value)

    def test_rejects_tuple(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(frozenset, (1, 2, 3))
        assert "expected frozenset, got tuple" in str(exc_info.value)

    @pytest.mark.parametrize(
        ("value", "expected_type_name"),
        [
            ("not a frozenset", "str"),
            (123, "int"),
            ({"a": 1}, "dict"),
            (None, "NoneType"),
        ],
        ids=["str", "int", "dict", "none"],
    )
    def test_rejects_non_frozenset(
        self, value: object, expected_type_name: str
    ) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(frozenset, value)
        assert f"expected frozenset, got {expected_type_name}" in str(exc_info.value)

    def test_rejects_invalid_element_type(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(frozenset[int], {1, 2, "three"})
        assert "expected int, got str" in str(exc_info.value)


class TestValidateLiteral:
    """Tests for Literal validation.

    Literal types validate that a value is exactly one of the specified
    literal values. Uses strict type matching (no coercion).
    """

    # String literals
    def test_literal_string_valid(self) -> None:
        result = validator.validate(Literal["a", "b", "c"], "a")  # type: ignore[arg-type]
        assert result == "a"

    def test_literal_string_second_option(self) -> None:
        result = validator.validate(Literal["a", "b", "c"], "b")  # type: ignore[arg-type]
        assert result == "b"

    def test_literal_single_string(self) -> None:
        result = validator.validate(Literal["only"], "only")  # type: ignore[arg-type]
        assert result == "only"

    # Int literals
    def test_literal_int_valid(self) -> None:
        result = validator.validate(Literal[1, 2, 3], 1)  # type: ignore[arg-type]
        assert result == 1
        assert isinstance(result, int)

    def test_literal_negative_int(self) -> None:
        result = validator.validate(Literal[-1, 0, 1], -1)  # type: ignore[arg-type]
        assert result == -1

    # Bool literals
    def test_literal_bool_true(self) -> None:
        result = validator.validate(Literal[True], True)  # type: ignore[arg-type]
        assert result is True

    def test_literal_bool_false(self) -> None:
        result = validator.validate(Literal[False], False)  # type: ignore[arg-type]
        assert result is False

    def test_literal_bool_both(self) -> None:
        result = validator.validate(Literal[True, False], True)  # type: ignore[arg-type]
        assert result is True
        result = validator.validate(Literal[True, False], False)  # type: ignore[arg-type]
        assert result is False

    # None literal
    def test_literal_none(self) -> None:
        result = validator.validate(Literal[None], None)  # type: ignore[arg-type]
        assert result is None

    # Mixed literals
    def test_literal_mixed_types(self) -> None:
        result = validator.validate(Literal["a", 1, None], "a")  # type: ignore[arg-type]
        assert result == "a"
        result = validator.validate(Literal["a", 1, None], 1)  # type: ignore[arg-type]
        assert result == 1
        result = validator.validate(Literal["a", 1, None], None)  # type: ignore[arg-type]
        assert result is None

    # Strict matching - no coercion
    def test_literal_int_rejects_float(self) -> None:
        # 1.0 is not 1 for Literal purposes
        with pytest.raises(validator.ValidationError):
            validator.validate(Literal[1, 2, 3], 1.0)  # type: ignore[arg-type]

    def test_literal_int_rejects_bool(self) -> None:
        # True is not 1 for Literal purposes (strict)
        with pytest.raises(validator.ValidationError):
            validator.validate(Literal[1], True)  # type: ignore[arg-type]

    def test_literal_bool_rejects_int(self) -> None:
        # 1 is not True for Literal purposes (strict)
        with pytest.raises(validator.ValidationError):
            validator.validate(Literal[True], 1)  # type: ignore[arg-type]

    # Rejection tests
    def test_rejects_invalid_string(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(Literal["a", "b"], "c")  # type: ignore[arg-type]
        assert "Literal" in str(exc_info.value) or "'c'" in str(exc_info.value)

    def test_rejects_invalid_int(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(Literal[1, 2, 3], 4)  # type: ignore[arg-type]
        assert "Literal" in str(exc_info.value) or "4" in str(exc_info.value)

    def test_rejects_wrong_type(self) -> None:
        with pytest.raises(validator.ValidationError):
            validator.validate(Literal["a", "b"], 1)  # type: ignore[arg-type]

    def test_rejects_none_when_not_in_literal(self) -> None:
        with pytest.raises(validator.ValidationError):
            validator.validate(Literal["a", "b"], None)  # type: ignore[arg-type]


class TestValidateDataclass:
    """Tests for dataclass validation.

    Dataclasses and dicts/Mappings are considered equivalent:
    - validate(MyDataclass, dict) constructs the dataclass from the dict
    - validate(dict, my_dataclass_instance) converts via dataclasses.asdict()
    - validate(MyDataclass, other_dataclass_instance) also works
    """

    # Basic construction from dict
    def test_simple_dataclass_from_dict(self) -> None:
        result = validator.validate(UserDataclass, {"name": "bestie", "age": 25})
        assert isinstance(result, UserDataclass)
        assert result.name == "bestie"
        assert result.age == 25

    def test_dataclass_field_coercion(self) -> None:
        result = validator.validate(StatsDataclass, {"score": 1, "count": 2})
        assert isinstance(result, StatsDataclass)
        assert result.score == 1.0
        assert result.count == 2.0
        assert isinstance(result.score, float)

    # Defaults
    def test_dataclass_with_defaults_all_provided(self) -> None:
        result = validator.validate(
            UserWithDefaultsDataclass,
            {"name": "bestie", "age": 30, "active": False},
        )
        assert isinstance(result, UserWithDefaultsDataclass)
        assert result.age == 30
        assert result.active is False

    def test_dataclass_uses_defaults_for_missing_fields(self) -> None:
        result = validator.validate(UserWithDefaultsDataclass, {"name": "bestie"})
        assert isinstance(result, UserWithDefaultsDataclass)
        assert result.age == 0
        assert result.active is True

    def test_dataclass_with_default_factory(self) -> None:
        result = validator.validate(UserWithFactoryDataclass, {"name": "bestie"})
        assert isinstance(result, UserWithFactoryDataclass)
        assert result.tags == []

    def test_dataclass_with_default_factory_provided(self) -> None:
        result = validator.validate(
            UserWithFactoryDataclass, {"name": "bestie", "tags": ["a", "b"]}
        )
        assert isinstance(result, UserWithFactoryDataclass)
        assert result.tags == ["a", "b"]

    # Nested dataclasses
    def test_nested_dataclass(self) -> None:
        result = validator.validate(
            PersonDataclass,
            {"name": "bestie", "address": {"city": "NYC", "zip_code": "10001"}},
        )
        assert isinstance(result, PersonDataclass)
        assert isinstance(result.address, AddressDataclass)
        assert result.address.city == "NYC"

    # From Mapping types
    def test_dataclass_from_ordered_dict(self) -> None:
        data = collections.OrderedDict([("name", "bestie"), ("age", 25)])
        result = validator.validate(UserDataclass, data)
        assert isinstance(result, UserDataclass)
        assert result.name == "bestie"

    # Dataclass <-> dict equivalence
    def test_dataclass_instance_to_dict(self) -> None:
        user = UserDataclass(name="bestie", age=25)
        result = validator.validate(dict, user)
        assert result == {"name": "bestie", "age": 25}
        assert type(result) is dict

    def test_dataclass_instance_to_typed_dict(self) -> None:
        user = UserDataclass(name="bestie", age=25)
        result = validator.validate(UserTypedDict, user)
        assert result == {"name": "bestie", "age": 25}

    def test_dataclass_instance_to_dataclass(self) -> None:
        user = UserDataclass(name="bestie", age=25)
        result = validator.validate(UserDataclass, user)
        assert isinstance(result, UserDataclass)
        assert result.name == "bestie"
        assert result.age == 25

    # Rejection tests
    def test_rejects_missing_required_field(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserDataclass, {"name": "bestie"})
        assert "age" in str(exc_info.value)

    def test_rejects_extra_keys(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                UserDataclass, {"name": "bestie", "age": 25, "extra": "field"}
            )
        assert "extra" in str(exc_info.value)

    def test_rejects_invalid_field_type(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserDataclass, {"name": "bestie", "age": "twenty five"})
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_non_mapping(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserDataclass, "not a dict")
        assert "expected UserDataclass, got str" in str(exc_info.value)

    def test_rejects_list(self) -> None:
        with pytest.raises(validator.ValidationError):
            validator.validate(UserDataclass, [("name", "bestie"), ("age", 25)])


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
