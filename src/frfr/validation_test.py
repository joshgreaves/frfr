"""Tests for the core validation logic."""

import collections
import dataclasses
import types
from typing import Any, Literal, NamedTuple, NotRequired, Required, TypedDict, Union

import pytest

from frfr import validation as validator


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


class UserNamedTuple(NamedTuple):
    name: str
    age: int


class StatsNamedTuple(NamedTuple):
    score: float
    count: float  # pyright: ignore[reportIncompatibleMethodOverride]


class AddressNamedTuple(NamedTuple):
    city: str
    zip_code: str


class PersonNamedTuple(NamedTuple):
    name: str
    address: AddressNamedTuple


class UserWithDefaultsNamedTuple(NamedTuple):
    name: str
    age: int = 0
    active: bool = True


# ---------------------------------------------------------------------------
# Types for large-scale integration tests
# ---------------------------------------------------------------------------


class AuthorTypedDict(TypedDict):
    id: int
    username: str
    display_name: str | None


class CommentTypedDict(TypedDict):
    id: int
    author: AuthorTypedDict
    body: str
    score: int


class PostTypedDict(TypedDict):
    id: int
    title: str
    author: AuthorTypedDict
    comments: list[CommentTypedDict]
    stats: dict[str, int]


class TagNamedTuple(NamedTuple):
    id: int
    name: str
    slug: str


@dataclasses.dataclass
class CoordinateDataclass:
    lat: float
    lng: float


@dataclasses.dataclass
class RegionDataclass:
    name: str
    center: CoordinateDataclass
    tags: list[TagNamedTuple]


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

    # Error path tests
    def test_error_path_shows_index(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(list[int], [1, 2, "bad", 4])
        assert exc_info.value.path == "[2]"
        assert "[2] - expected int" in str(exc_info.value)

    def test_error_path_first_element(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(list[int], ["bad", 2, 3])
        assert exc_info.value.path == "[0]"
        assert "[0] - expected int" in str(exc_info.value)

    def test_error_path_nested_list(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(list[list[int]], [[1, 2], [3, "bad"]])
        assert exc_info.value.path == "[1][1]"
        assert "[1][1] - expected int" in str(exc_info.value)


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

    # Error path tests
    def test_error_path_homogeneous_tuple(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(tuple[int, ...], (1, "bad", 3))
        assert exc_info.value.path == "[1]"
        assert "[1] - expected int" in str(exc_info.value)

    def test_error_path_fixed_tuple(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(tuple[int, str, bool], (1, "ok", "not bool"))
        assert exc_info.value.path == "[2]"
        assert "[2] - expected bool" in str(exc_info.value)

    def test_error_path_fixed_tuple_first_element(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(tuple[int, str], ("bad", "ok"))
        assert exc_info.value.path == "[0]"
        assert "[0] - expected int" in str(exc_info.value)


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

    def test_namedtuple_instance_to_dict(self) -> None:
        user = UserNamedTuple(name="bestie", age=25)
        result = validator.validate(dict, user)
        assert result == {"name": "bestie", "age": 25}
        assert type(result) is dict

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

    # Error path tests
    def test_error_path_shows_key(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(dict[str, int], {"a": 1, "b": "bad"})
        assert exc_info.value.path == ".b"
        assert ".b - expected int" in str(exc_info.value)

    def test_error_path_nested_dict(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(dict[str, dict[str, int]], {"outer": {"inner": "bad"}})
        assert exc_info.value.path == ".outer.inner"
        assert ".outer.inner - expected int" in str(exc_info.value)

    def test_error_path_invalid_key_shows_key_marker(self) -> None:
        """Invalid key should show [key] marker to distinguish from value errors."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(dict[int, str], {"foo": "bar"})
        assert exc_info.value.path == ".foo[key]"
        assert ".foo[key] - expected int" in str(exc_info.value)

    def test_error_path_invalid_key_nested(self) -> None:
        """Invalid key in nested dict should show full path with [key] marker."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(dict[str, dict[int, str]], {"outer": {"bad": "val"}})
        assert exc_info.value.path == ".outer.bad[key]"
        assert ".outer.bad[key] - expected int" in str(exc_info.value)

    def test_error_path_non_identifier_key_uses_brackets(self) -> None:
        """Non-identifier keys should use bracket notation."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(dict[str, int], {"a.b": "bad"})
        assert exc_info.value.path == "['a.b']"
        assert "['a.b'] - expected int" in str(exc_info.value)

    def test_error_path_key_with_spaces_uses_brackets(self) -> None:
        """Keys with spaces should use bracket notation."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(dict[str, int], {"my key": "bad"})
        assert exc_info.value.path == "['my key']"
        assert "['my key'] - expected int" in str(exc_info.value)

    def test_error_path_numeric_key_uses_brackets(self) -> None:
        """Numeric keys should use bracket notation."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(dict[int, int], {123: "bad"})
        assert exc_info.value.path == "[123]"
        assert "[123] - expected int" in str(exc_info.value)


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

    def test_namedtuple_instance_to_typed_dict(self) -> None:
        user = UserNamedTuple(name="bestie", age=25)
        result = validator.validate(UserTypedDict, user)
        assert result == {"name": "bestie", "age": 25}

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
            validator.validate(
                UserTypedDict, {"name": "bestie", "age": 25, "extra": "field"}
            )
        assert "extra" in str(exc_info.value)
        assert "unexpected key" in str(exc_info.value)

    def test_rejects_non_mapping(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserTypedDict, "not a dict")
        assert "expected UserTypedDict, got str" in str(exc_info.value)

    # Error path tests
    def test_error_path_shows_field_name(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserTypedDict, {"name": "alice", "age": "bad"})
        assert exc_info.value.path == ".age"
        assert ".age - expected int" in str(exc_info.value)

    def test_error_path_nested_typed_dict(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                PersonTypedDict,
                {"name": "alice", "address": {"city": "NYC", "zip_code": 12345}},
            )
        assert exc_info.value.path == ".address.zip_code"
        assert ".address.zip_code - expected str" in str(exc_info.value)


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

    # Error path tests
    def test_error_path_preserved_in_nested_union(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                list[int | str],
                [1, "two", ["not int or str"]],
            )
        assert exc_info.value.path == "[2]"
        assert "[2] - expected" in str(exc_info.value)

    def test_error_path_optional_in_dict(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                dict[str, int | None],
                {"a": 1, "b": "bad"},
            )
        assert exc_info.value.path == ".b"
        assert ".b - expected" in str(exc_info.value)


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

    def test_namedtuple_instance_to_dataclass(self) -> None:
        user = UserNamedTuple(name="bestie", age=25)
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

    # Error path tests
    def test_error_path_shows_field_name(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserDataclass, {"name": "alice", "age": "bad"})
        assert exc_info.value.path == ".age"
        assert ".age - expected int" in str(exc_info.value)

    def test_error_path_nested_dataclass(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                PersonDataclass,
                {"name": "alice", "address": {"city": 123, "zip_code": "12345"}},
            )
        assert exc_info.value.path == ".address.city"
        assert ".address.city - expected str" in str(exc_info.value)


class TestValidateNamedTuple:
    """Tests for NamedTuple validation.

    NamedTuples have dual nature: they are tuples (positional) AND mappings
    (named fields). Both construction modes are supported.
    """

    # Construction from dict (by field name)
    def test_namedtuple_from_dict(self) -> None:
        result = validator.validate(UserNamedTuple, {"name": "bestie", "age": 25})
        assert isinstance(result, UserNamedTuple)
        assert result.name == "bestie"
        assert result.age == 25

    def test_namedtuple_field_coercion_from_dict(self) -> None:
        result = validator.validate(StatsNamedTuple, {"score": 1, "count": 2})
        assert isinstance(result, StatsNamedTuple)
        assert result.score == 1.0
        assert result.count == 2.0
        assert isinstance(result.score, float)

    # Construction from tuple/list (positional)
    def test_namedtuple_from_tuple(self) -> None:
        result = validator.validate(UserNamedTuple, ("bestie", 25))
        assert isinstance(result, UserNamedTuple)
        assert result.name == "bestie"
        assert result.age == 25

    def test_namedtuple_from_list(self) -> None:
        result = validator.validate(UserNamedTuple, ["bestie", 25])
        assert isinstance(result, UserNamedTuple)
        assert result.name == "bestie"
        assert result.age == 25

    def test_namedtuple_field_coercion_from_tuple(self) -> None:
        result = validator.validate(StatsNamedTuple, (1, 2))
        assert isinstance(result, StatsNamedTuple)
        assert result.score == 1.0
        assert result.count == 2.0

    # Defaults
    def test_namedtuple_with_defaults_from_dict(self) -> None:
        result = validator.validate(UserWithDefaultsNamedTuple, {"name": "bestie"})
        assert isinstance(result, UserWithDefaultsNamedTuple)
        assert result.name == "bestie"
        assert result.age == 0
        assert result.active is True

    def test_namedtuple_with_defaults_all_provided(self) -> None:
        result = validator.validate(
            UserWithDefaultsNamedTuple, {"name": "bestie", "age": 30, "active": False}
        )
        assert isinstance(result, UserWithDefaultsNamedTuple)
        assert result.age == 30
        assert result.active is False

    # Nested NamedTuples
    def test_nested_namedtuple_from_dict(self) -> None:
        result = validator.validate(
            PersonNamedTuple,
            {"name": "bestie", "address": {"city": "NYC", "zip_code": "10001"}},
        )
        assert isinstance(result, PersonNamedTuple)
        assert isinstance(result.address, AddressNamedTuple)
        assert result.address.city == "NYC"

    # From Mapping types
    def test_namedtuple_from_ordered_dict(self) -> None:
        data = collections.OrderedDict([("name", "bestie"), ("age", 25)])
        result = validator.validate(UserNamedTuple, data)
        assert isinstance(result, UserNamedTuple)
        assert result.name == "bestie"

    # Cross-type conversions where target IS NamedTuple
    def test_namedtuple_from_namedtuple(self) -> None:
        user = UserNamedTuple(name="bestie", age=25)
        result = validator.validate(UserNamedTuple, user)
        assert isinstance(result, UserNamedTuple)
        assert result.name == "bestie"
        assert result.age == 25

    def test_typed_dict_to_namedtuple(self) -> None:
        data: UserTypedDict = {"name": "bestie", "age": 25}
        result = validator.validate(UserNamedTuple, data)
        assert isinstance(result, UserNamedTuple)
        assert result.name == "bestie"

    def test_dataclass_to_namedtuple(self) -> None:
        user = UserDataclass(name="bestie", age=25)
        result = validator.validate(UserNamedTuple, user)
        assert isinstance(result, UserNamedTuple)
        assert result.name == "bestie"
        assert result.age == 25

    # Rejection tests
    def test_rejects_wrong_length_tuple(self) -> None:
        with pytest.raises(validator.ValidationError):
            validator.validate(UserNamedTuple, ("bestie",))

    def test_rejects_too_many_positional(self) -> None:
        with pytest.raises(validator.ValidationError):
            validator.validate(UserNamedTuple, ("bestie", 25, "extra"))

    def test_rejects_missing_required_field(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserNamedTuple, {"name": "bestie"})
        assert "age" in str(exc_info.value)

    def test_rejects_extra_keys(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                UserNamedTuple, {"name": "bestie", "age": 25, "extra": "field"}
            )
        assert "extra" in str(exc_info.value)

    def test_rejects_invalid_field_type_from_dict(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserNamedTuple, {"name": "bestie", "age": "twenty five"})
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_invalid_element_type_from_tuple(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserNamedTuple, ("bestie", "not an int"))
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_non_mapping_non_sequence(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserNamedTuple, "not a tuple or dict")
        assert "expected UserNamedTuple, got str" in str(exc_info.value)

    # Error path tests
    def test_error_path_from_dict_shows_field(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserNamedTuple, {"name": "alice", "age": "bad"})
        assert exc_info.value.path == ".age"
        assert ".age - expected int" in str(exc_info.value)

    def test_error_path_from_tuple_shows_index(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(UserNamedTuple, ("alice", "bad"))
        assert exc_info.value.path == "[1]"
        assert "[1] - expected int" in str(exc_info.value)

    def test_error_path_nested_from_dict(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                PersonNamedTuple,
                {"name": "alice", "address": {"city": 123, "zip_code": "12345"}},
            )
        assert exc_info.value.path == ".address.city"
        assert ".address.city - expected str" in str(exc_info.value)

    def test_error_path_nested_from_tuple(self) -> None:
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(PersonNamedTuple, ("alice", (123, "12345")))
        assert exc_info.value.path == "[1][0]"
        assert "[1][0] - expected str" in str(exc_info.value)


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

    def test_root_level_validation_error_has_no_path(self) -> None:
        """Root level errors should have empty path."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(int, "not an int")
        assert exc_info.value.path == ""
        # Message should not have path prefix
        assert str(exc_info.value).startswith("expected int")


class TestValidationErrorPathsComplex:
    """Tests for error path tracking through complex composed types.

    These tests cover combinations of multiple types nested together.
    """

    def test_list_of_dicts_error(self) -> None:
        """Error in list of dicts should show [index].key."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                list[dict[str, int]],
                [{"a": 1}, {"b": "bad"}],
            )
        assert exc_info.value.path == "[1].b"
        assert "[1].b - expected int" in str(exc_info.value)

    def test_dict_of_lists_error(self) -> None:
        """Error in dict of lists should show .key[index]."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                dict[str, list[int]],
                {"nums": [1, 2, "bad"]},
            )
        assert exc_info.value.path == ".nums[2]"
        assert ".nums[2] - expected int" in str(exc_info.value)

    def test_deeply_nested_structure_error(self) -> None:
        """Error in deeply nested structure."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                dict[str, list[dict[str, list[int]]]],
                {"users": [{"scores": [1, 2, "bad"]}]},
            )
        assert exc_info.value.path == ".users[0].scores[2]"
        assert ".users[0].scores[2] - expected int" in str(exc_info.value)

    def test_deeply_nested_typed_dict(self) -> None:
        """Test path tracking through deeply nested TypedDicts."""

        class ItemTypedDict(TypedDict):
            id: int
            tags: list[str]

        class ContainerTypedDict(TypedDict):
            items: list[ItemTypedDict]

        data = {
            "items": [
                {"id": 1, "tags": ["a", "b"]},
                {"id": 2, "tags": ["c", 123]},  # Error here
            ]
        }

        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(ContainerTypedDict, data)
        assert exc_info.value.path == ".items[1].tags[1]"
        assert ".items[1].tags[1] - expected str" in str(exc_info.value)

    def test_list_of_dataclasses_error(self) -> None:
        """Error in list of dataclasses."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                list[UserDataclass],
                [
                    {"name": "alice", "age": 25},
                    {"name": "bob", "age": "thirty"},
                ],
            )
        assert exc_info.value.path == "[1].age"
        assert "[1].age - expected int" in str(exc_info.value)

    def test_dict_of_namedtuples_error(self) -> None:
        """Error in dict of NamedTuples."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                dict[str, UserNamedTuple],
                {
                    "user1": {"name": "alice", "age": 25},
                    "user2": {"name": "bob", "age": "thirty"},
                },
            )
        assert exc_info.value.path == ".user2.age"
        assert ".user2.age - expected int" in str(exc_info.value)

    def test_tuple_of_typed_dicts_error(self) -> None:
        """Error in tuple of TypedDicts."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                tuple[UserTypedDict, UserTypedDict],
                (
                    {"name": "alice", "age": 25},
                    {"name": "bob", "age": "thirty"},
                ),
            )
        assert exc_info.value.path == "[1].age"
        assert "[1].age - expected int" in str(exc_info.value)

    def test_literal_in_nested_typed_dict(self) -> None:
        """Literal error should preserve the path context."""

        class StatusTypedDict(TypedDict):
            name: str
            status: Literal["active", "inactive"]

        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(StatusTypedDict, {"name": "test", "status": "bad"})
        assert exc_info.value.path == ".status"
        assert ".status - expected" in str(exc_info.value)

    def test_triple_nested_lists(self) -> None:
        """Error in triple nested lists."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(list[list[list[int]]], [[[1]], [[2], [3, "bad"]]])
        assert exc_info.value.path == "[1][1][1]"
        assert "[1][1][1] - expected int" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Custom Validator tests
# ---------------------------------------------------------------------------


class TestCustomValidator:
    """Tests for custom Validator instances: registration, overrides, composition."""

    def test_default_validator_is_frozen(self) -> None:
        """The module-level validate() uses a frozen validator that rejects registration."""
        v = validator.Validator(frozen=True)
        with pytest.raises(RuntimeError, match="frozen"):
            v.register_type_handler(int, lambda _v, _t, data, _p: data)  # type: ignore[arg-type]

    def test_register_new_type(self) -> None:
        """A custom handler for an unknown type is called during validation."""

        class Celsius:
            def __init__(self, value: float) -> None:
                self.value = value

        def parse_celsius(
            v: validator.ValidatorProtocol, target: type, data: object, path: str
        ) -> Celsius:
            if not isinstance(data, int | float):
                raise validator.ValidationError(target, data, path=path)
            return Celsius(float(data))

        v = validator.Validator()
        v.register_type_handler(Celsius, parse_celsius)
        result = v.validate(Celsius, 100)
        assert isinstance(result, Celsius)
        assert result.value == 100.0

    def test_override_builtin_handler(self) -> None:
        """A registered handler for int replaces the built-in one."""

        def coercing_int(
            v: validator.ValidatorProtocol, target: type, data: object, path: str
        ) -> int:
            try:
                return int(data)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                raise validator.ValidationError(target, data, path=path)

        v = validator.Validator()
        v.register_type_handler(int, coercing_int)
        assert v.validate(int, "42") == 42
        assert v.validate(int, 3.9) == 3
        assert v.validate(int, True) == 1

    def test_override_does_not_affect_default_validator(self) -> None:
        """Overriding a handler on a custom instance leaves the default validator unchanged."""
        v = validator.Validator()
        v.register_type_handler(int, lambda _v, _t, data, _p: 999)
        assert v.validate(int, 1) == 999
        assert validator.validate(int, 1) == 1

    def test_handler_receives_validator_for_recursion(self) -> None:
        """Custom handler can call validator.validate() to recurse into nested types."""

        @dataclasses.dataclass
        class Tagged:
            value: int
            tag: str

        def parse_tagged(
            v: validator.ValidatorProtocol, target: type, data: object, path: str
        ) -> Tagged:
            if not isinstance(data, dict):
                raise validator.ValidationError(target, data, path=path)
            return Tagged(
                value=v._validate_at(int, data.get("value"), f"{path}.value"),  # type: ignore[arg-type]
                tag=v._validate_at(str, data.get("tag"), f"{path}.tag"),  # type: ignore[arg-type]
            )

        v = validator.Validator()
        v.register_type_handler(Tagged, parse_tagged)
        result = v.validate(Tagged, {"value": 7, "tag": "hello"})
        assert result.value == 7
        assert result.tag == "hello"

    def test_handler_recursion_uses_overridden_handlers(self) -> None:
        """When a custom handler recurses, it uses the same validator's handlers."""
        call_log: list[str] = []

        def tracking_str(
            v: validator.ValidatorProtocol, target: type, data: object, path: str
        ) -> str:
            call_log.append(str(data))
            if type(data) is not str:
                raise validator.ValidationError(target, data, path=path)  # type: ignore[arg-type]
            return data  # type: ignore[return-value]

        v = validator.Validator()
        v.register_type_handler(str, tracking_str)
        v.validate(list[str], ["a", "b", "c"])
        assert call_log == ["a", "b", "c"]

    def test_register_predicate_handler(self) -> None:
        """A predicate handler is called for any type matching the predicate."""

        class MyMeta(type):
            pass

        class MyA(metaclass=MyMeta):
            pass

        class MyB(metaclass=MyMeta):
            pass

        def parse_mymeta(
            v: validator.ValidatorProtocol, target: type, data: object, path: str
        ) -> object:
            return target()

        v = validator.Validator()
        v.register_predicate_handler(lambda t: isinstance(t, MyMeta), parse_mymeta)
        assert isinstance(v.validate(MyA, {}), MyA)
        assert isinstance(v.validate(MyB, {}), MyB)

    def test_predicate_handler_overrides_builtin(self) -> None:
        """A predicate handler registered last takes priority over built-in predicate handlers."""
        seen: list[type] = []

        def spy_dataclass(
            v: validator.ValidatorProtocol, target: type, data: object, path: str
        ) -> object:
            seen.append(target)
            return validator.compile_dataclass(target, v._get_compiled)(data, path)  # type: ignore[attr-defined]

        @dataclasses.dataclass
        class Point:
            x: int
            y: int

        v = validator.Validator()
        v.register_predicate_handler(dataclasses.is_dataclass, spy_dataclass)
        result = v.validate(Point, {"x": 1, "y": 2})
        assert seen == [Point]
        assert result == Point(x=1, y=2)

    def test_unfrozen_validator_has_all_builtins(self) -> None:
        """A fresh custom Validator has all built-in handlers."""
        v = validator.Validator()
        assert v.validate(int, 1) == 1
        assert v.validate(str, "hi") == "hi"
        assert v.validate(list[int], [1, 2, 3]) == [1, 2, 3]
        assert v.validate(UserDataclass, {"name": "alice", "age": 25}) == UserDataclass(
            "alice", 25
        )

    def test_register_type_handler_after_cache_invalidates(self) -> None:
        """Registering a new type handler invalidates compiled cache for that type."""
        v = validator.Validator()
        # Warm the cache for int
        assert v.validate(int, 5) == 5
        # Override int handler after the cache is warm
        v.register_type_handler(int, lambda _v, _t, data, _p: 999)
        # The new handler should be used, not the cached one
        assert v.validate(int, 5) == 999

    def test_register_type_handler_after_cache_invalidates_composite(self) -> None:
        """Registering a new handler for a child type invalidates composite compiled cache."""
        v = validator.Validator()
        # Warm the cache for list[int]
        assert v.validate(list[int], [1, 2]) == [1, 2]
        # Override int handler after the cache is warm
        v.register_type_handler(int, lambda _v, _t, data, _p: 0)
        # The compiled list[int] must be rebuilt to pick up the new int handler
        assert v.validate(list[int], [1, 2]) == [0, 0]

    def test_register_predicate_handler_after_cache_invalidates(self) -> None:
        """Registering a new predicate handler invalidates compiled cache."""

        @dataclasses.dataclass
        class Box:
            value: int

        v = validator.Validator()
        # Warm the cache for Box
        assert v.validate(Box, {"value": 1}) == Box(value=1)
        # Register a predicate handler that intercepts all dataclasses
        v.register_predicate_handler(dataclasses.is_dataclass, lambda _v, _t, _d, _p: "intercepted")
        # The new predicate handler should take effect
        assert v.validate(Box, {"value": 1}) == "intercepted"


# ---------------------------------------------------------------------------
# Large-scale integration tests
# ---------------------------------------------------------------------------


class TestLargeScaleIntegration:
    """Integration tests with complex, deeply-nested real-world-style structures."""

    def test_nested_typeddict_list_success(self) -> None:
        """Large payload: list of posts with nested authors and comments validates fully."""
        data = [
            {
                "id": 1,
                "title": "Hello world",
                "author": {"id": 1, "username": "alice", "display_name": "Alice"},
                "comments": [
                    {
                        "id": 1,
                        "author": {"id": 2, "username": "bob", "display_name": None},
                        "body": "great post!",
                        "score": 10,
                    },
                    {
                        "id": 2,
                        "author": {
                            "id": 3,
                            "username": "carol",
                            "display_name": "Carol",
                        },
                        "body": "thanks for sharing",
                        "score": 5,
                    },
                ],
                "stats": {"views": 1000, "likes": 42, "shares": 7},
            },
            {
                "id": 2,
                "title": "Follow-up",
                "author": {"id": 1, "username": "alice", "display_name": "Alice"},
                "comments": [],
                "stats": {"views": 200, "likes": 8, "shares": 1},
            },
        ]
        result = validator.validate(list[PostTypedDict], data)
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["author"]["username"] == "alice"
        assert result[0]["author"]["display_name"] == "Alice"
        assert len(result[0]["comments"]) == 2
        assert result[0]["comments"][0]["author"]["display_name"] is None
        assert result[0]["comments"][1]["author"]["display_name"] == "Carol"
        assert result[0]["stats"]["views"] == 1000
        assert result[1]["comments"] == []

    def test_nested_typeddict_error_path(self) -> None:
        """Error deep in nested TypedDicts reports the full path."""
        data = [
            {
                "id": 1,
                "title": "Post 1",
                "author": {"id": 1, "username": "alice", "display_name": None},
                "comments": [
                    {
                        "id": 1,
                        "author": {"id": 2, "username": "bob", "display_name": None},
                        "body": "good",
                        "score": 5,
                    },
                    {
                        "id": 2,
                        "author": {"id": 3, "username": "carol", "display_name": None},
                        "body": "oops",
                        "score": "not_an_int",  # error
                    },
                ],
                "stats": {"views": 100},
            },
        ]
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(list[PostTypedDict], data)
        assert exc_info.value.path == "[0].comments[1].score"

    def test_dataclass_with_nested_namedtuples_success(self) -> None:
        """Dataclass containing a list of NamedTuples validates correctly."""
        result = validator.validate(
            RegionDataclass,
            {
                "name": "Pacific Northwest",
                "center": {"lat": 47.6, "lng": -122.3},
                "tags": [
                    {"id": 1, "name": "mountains", "slug": "mountains"},
                    {"id": 2, "name": "forests", "slug": "forests"},
                    {"id": 3, "name": "coast", "slug": "coast"},
                ],
            },
        )
        assert isinstance(result, RegionDataclass)
        assert isinstance(result.center, CoordinateDataclass)
        assert result.center.lat == 47.6
        assert result.center.lng == -122.3
        assert len(result.tags) == 3
        assert all(isinstance(t, TagNamedTuple) for t in result.tags)
        assert result.tags[0].name == "mountains"
        assert result.tags[2].slug == "coast"

    def test_dataclass_with_nested_namedtuple_error_path(self) -> None:
        """Error in a NamedTuple nested inside a dataclass shows the full path."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                RegionDataclass,
                {
                    "name": "Cascades",
                    "center": {"lat": 47.6, "lng": -122.3},
                    "tags": [
                        {"id": 1, "name": "alpine", "slug": "alpine"},
                        {"id": "not_an_int", "name": "lakes", "slug": "lakes"},  # error
                    ],
                },
            )
        assert exc_info.value.path == ".tags[1].id"

    def test_dict_of_list_of_fixed_tuples_success(self) -> None:
        """dict[str, list[tuple[int, str | None]]] validates correctly."""
        result = validator.validate(
            dict[str, list[tuple[int, str | None]]],
            {
                "scores": [(1, "alpha"), (2, None), (3, "gamma")],
                "counts": [(10, "x"), (20, "y")],
                "empty": [],
            },
        )
        assert result["scores"] == [(1, "alpha"), (2, None), (3, "gamma")]
        assert result["counts"] == [(10, "x"), (20, "y")]
        assert result["empty"] == []

    def test_dict_of_list_of_fixed_tuples_error_path(self) -> None:
        """Error in dict[str, list[tuple[int, str | None]]] reports correct path."""
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(
                dict[str, list[tuple[int, str | None]]],
                {"scores": [(1, "ok"), (2, 3.14)]},  # 3.14 is not str | None
            )
        assert exc_info.value.path == ".scores[1][1]"

    def test_large_collection_validates_all_items(self) -> None:
        """All 100 items in a list must pass validation."""
        data = [
            {"id": i, "username": f"user{i}", "display_name": None} for i in range(100)
        ]
        result = validator.validate(list[AuthorTypedDict], data)
        assert len(result) == 100
        assert result[0]["id"] == 0
        assert result[99]["username"] == "user99"

    def test_large_collection_error_index(self) -> None:
        """Error in item 50 of a 51-element list reports index [50]."""
        data: list[dict[str, object]] = [
            {"id": i, "username": f"user{i}", "display_name": None} for i in range(50)
        ]
        data.append({"id": "not_an_int", "username": "bad", "display_name": None})
        with pytest.raises(validator.ValidationError) as exc_info:
            validator.validate(list[AuthorTypedDict], data)
        assert exc_info.value.path == "[50].id"

    def test_int_to_float_coercion_in_nested_dataclass(self) -> None:
        """Int-to-float coercion works through dict → dataclass nesting."""
        result = validator.validate(
            dict[str, CoordinateDataclass],
            {
                "a": {"lat": 1, "lng": 2},
                "b": {"lat": 47, "lng": -122},
            },
        )
        assert result["a"].lat == 1.0
        assert result["a"].lng == 2.0
        assert isinstance(result["a"].lat, float)
        assert isinstance(result["b"].lng, float)

    def test_optional_field_none_and_str_at_multiple_levels(self) -> None:
        """display_name: str | None resolves correctly for both values in nested structs."""
        data = [
            {
                "id": 1,
                "title": "Post",
                "author": {"id": 1, "username": "alice", "display_name": "Alice"},
                "comments": [
                    {
                        "id": 1,
                        "author": {"id": 2, "username": "bob", "display_name": None},
                        "body": "hi",
                        "score": 1,
                    }
                ],
                "stats": {},
            }
        ]
        result = validator.validate(list[PostTypedDict], data)
        assert result[0]["author"]["display_name"] == "Alice"
        assert result[0]["comments"][0]["author"]["display_name"] is None

    def test_union_inside_dict_inside_list(self) -> None:
        """list[dict[str, int | str]] validates mixed-value dicts correctly."""
        result = validator.validate(
            list[dict[str, int | str]],
            [
                {"count": 5, "label": "foo"},
                {"count": 10, "label": "bar"},
            ],
        )
        assert result[0]["count"] == 5
        assert result[0]["label"] == "foo"
        assert result[1]["label"] == "bar"
