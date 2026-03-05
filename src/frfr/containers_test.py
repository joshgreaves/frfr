"""Tests for container and parameterized type validation."""

import collections
import collections.abc
import dataclasses
import types
from typing import (
    Annotated,
    Final,
    Literal,
    NamedTuple,
    NewType,
    Sequence,
    TypedDict,
    Union,
)

import pytest

import frfr


# ---------------------------------------------------------------------------
# Shared types used across tests in this file
# ---------------------------------------------------------------------------

UserId = NewType("UserId", int)
Username = NewType("Username", str)
SpecialUserId = NewType("SpecialUserId", UserId)  # NewType of NewType


class UserNamedTuple(NamedTuple):
    name: str
    age: int


class TestValidateList:
    """Tests for list validation."""

    # Unparameterized list
    def test_unparameterized_list(self) -> None:
        result = frfr.validate(list, [1, "two", 3.0])
        assert result == [1, "two", 3.0]
        assert isinstance(result, list)

    def test_empty_list(self) -> None:
        result = frfr.validate(list, [])
        assert result == []
        assert isinstance(result, list)

    # Always returns new object (mutable containers are copied)
    def test_returns_new_list_unparameterized(self) -> None:
        original = [1, 2, 3]
        result = frfr.validate(list, original)
        assert result == original
        assert result is not original

    def test_returns_new_list_parameterized(self) -> None:
        original = [1, 2, 3]
        result = frfr.validate(list[int], original)
        assert result == original
        assert result is not original

    # Parameterized list[T]
    def test_list_of_int(self) -> None:
        result = frfr.validate(list[int], [1, 2, 3])
        assert result == [1, 2, 3]
        assert isinstance(result, list)
        assert all(isinstance(x, int) for x in result)

    def test_list_of_str(self) -> None:
        result = frfr.validate(list[str], ["a", "b", "c"])
        assert result == ["a", "b", "c"]
        assert isinstance(result, list)

    def test_empty_parameterized_list(self) -> None:
        result = frfr.validate(list[int], [])
        assert result == []
        assert isinstance(result, list)

    # Coercion within elements
    def test_list_of_float_coerces_int(self) -> None:
        result = frfr.validate(list[float], [1, 2, 3])
        assert result == [1.0, 2.0, 3.0]
        assert all(isinstance(x, float) for x in result)

    # Nested lists
    def test_nested_list(self) -> None:
        result = frfr.validate(list[list[int]], [[1, 2], [3, 4]])
        assert result == [[1, 2], [3, 4]]
        assert isinstance(result, list)
        assert all(isinstance(inner, list) for inner in result)

    # Tuple coercion
    def test_tuple_coerces_to_list(self) -> None:
        result = frfr.validate(list, (1, 2, 3))
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_tuple_coerces_to_parameterized_list(self) -> None:
        result = frfr.validate(list[int], (1, 2, 3))
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_nested_tuple_coerces_to_list(self) -> None:
        result = frfr.validate(list[list[int]], [(1, 2), (3, 4)])
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
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(list, value)
        assert f"expected list, got {expected_type_name}" in str(exc_info.value)

    def test_rejects_invalid_element_type(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(list[int], [1, 2, "three"])
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_bool_in_int_list(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(list[int], [1, True, 3])
        assert "expected int, got bool" in str(exc_info.value)

    # Error path tests
    def test_error_path_shows_index(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(list[int], [1, 2, "bad", 4])
        assert exc_info.value.path == "[2]"
        assert "[2] - expected int" in str(exc_info.value)

    def test_error_path_first_element(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(list[int], ["bad", 2, 3])
        assert exc_info.value.path == "[0]"
        assert "[0] - expected int" in str(exc_info.value)

    def test_error_path_nested_list(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(list[list[int]], [[1, 2], [3, "bad"]])
        assert exc_info.value.path == "[1][1]"
        assert "[1][1] - expected int" in str(exc_info.value)


class TestValidateTuple:
    """Tests for tuple validation."""

    # Unparameterized tuple
    def test_unparameterized_tuple(self) -> None:
        result = frfr.validate(tuple, (1, "two", 3.0))
        assert result == (1, "two", 3.0)
        assert isinstance(result, tuple)

    def test_empty_tuple(self) -> None:
        result = frfr.validate(tuple, ())
        assert result == ()
        assert isinstance(result, tuple)

    # List coercion
    def test_list_coerces_to_tuple(self) -> None:
        result = frfr.validate(tuple, [1, 2, 3])
        assert result == (1, 2, 3)
        assert isinstance(result, tuple)

    # Homogeneous tuple[T, ...]
    def test_homogeneous_tuple(self) -> None:
        result = frfr.validate(tuple[int, ...], (1, 2, 3))
        assert result == (1, 2, 3)
        assert isinstance(result, tuple)
        assert all(isinstance(x, int) for x in result)

    def test_homogeneous_tuple_empty(self) -> None:
        result = frfr.validate(tuple[int, ...], ())
        assert result == ()
        assert isinstance(result, tuple)

    def test_homogeneous_tuple_coerces_elements(self) -> None:
        result = frfr.validate(tuple[float, ...], (1, 2, 3))
        assert result == (1.0, 2.0, 3.0)
        assert all(isinstance(x, float) for x in result)

    def test_homogeneous_tuple_from_list(self) -> None:
        result = frfr.validate(tuple[int, ...], [1, 2, 3])
        assert result == (1, 2, 3)
        assert isinstance(result, tuple)

    # Fixed-length tuple[T1, T2, ...]
    def test_fixed_tuple(self) -> None:
        result = frfr.validate(tuple[int, str, bool], (1, "two", True))
        assert result == (1, "two", True)
        assert isinstance(result, tuple)

    def test_fixed_tuple_single_element(self) -> None:
        result = frfr.validate(tuple[int], (42,))
        assert result == (42,)
        assert isinstance(result, tuple)

    def test_fixed_tuple_coerces_elements(self) -> None:
        result = frfr.validate(tuple[float, float], (1, 2))
        assert result == (1.0, 2.0)
        assert all(isinstance(x, float) for x in result)

    def test_fixed_tuple_from_list(self) -> None:
        result = frfr.validate(tuple[int, str], [1, "two"])
        assert result == (1, "two")
        assert isinstance(result, tuple)

    # Nested tuples
    def test_nested_tuple(self) -> None:
        result = frfr.validate(tuple[tuple[int, ...], ...], ((1, 2), (3, 4)))
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
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(tuple, value)
        assert f"expected tuple, got {expected_type_name}" in str(exc_info.value)

    def test_rejects_invalid_element_in_homogeneous(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(tuple[int, ...], (1, 2, "three"))
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_wrong_length_fixed_tuple(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(tuple[int, str], (1, "two", 3))
        assert "expected tuple" in str(exc_info.value)

    def test_rejects_too_short_fixed_tuple(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(tuple[int, str, bool], (1, "two"))
        assert "expected tuple" in str(exc_info.value)

    def test_rejects_invalid_element_in_fixed_tuple(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(tuple[int, str], (1, 2))
        assert "expected str, got int" in str(exc_info.value)

    def test_rejects_bool_in_int_tuple(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(tuple[int, ...], (1, True, 3))
        assert "expected int, got bool" in str(exc_info.value)

    # Error path tests
    def test_error_path_homogeneous_tuple(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(tuple[int, ...], (1, "bad", 3))
        assert exc_info.value.path == "[1]"
        assert "[1] - expected int" in str(exc_info.value)

    def test_error_path_fixed_tuple(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(tuple[int, str, bool], (1, "ok", "not bool"))
        assert exc_info.value.path == "[2]"
        assert "[2] - expected bool" in str(exc_info.value)

    def test_error_path_fixed_tuple_first_element(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(tuple[int, str], ("bad", "ok"))
        assert exc_info.value.path == "[0]"
        assert "[0] - expected int" in str(exc_info.value)


class TestValidateDict:
    """Tests for dict validation."""

    # Unparameterized dict
    def test_unparameterized_dict(self) -> None:
        result = frfr.validate(dict, {"a": 1, "b": "two"})
        assert result == {"a": 1, "b": "two"}
        assert isinstance(result, dict)

    def test_empty_dict(self) -> None:
        result = frfr.validate(dict, {})
        assert result == {}
        assert isinstance(result, dict)

    # Always returns new dict
    def test_returns_new_dict(self) -> None:
        original = {"a": 1}
        result = frfr.validate(dict, original)
        assert result == original
        assert result is not original

    def test_returns_new_dict_parameterized(self) -> None:
        original = {"a": 1}
        result = frfr.validate(dict[str, int], original)
        assert result == original
        assert result is not original

    # Parameterized dict[K, V]
    def test_dict_str_int(self) -> None:
        result = frfr.validate(dict[str, int], {"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}
        assert isinstance(result, dict)

    def test_dict_int_str(self) -> None:
        result = frfr.validate(dict[int, str], {1: "a", 2: "b"})
        assert result == {1: "a", 2: "b"}
        assert isinstance(result, dict)

    def test_empty_parameterized_dict(self) -> None:
        result = frfr.validate(dict[str, int], {})
        assert result == {}
        assert isinstance(result, dict)

    # Key coercion (same rules as values)
    def test_dict_key_coercion(self) -> None:
        result = frfr.validate(dict[float, str], {1: "a", 2: "b"})
        assert result == {1.0: "a", 2.0: "b"}
        assert all(isinstance(k, float) for k in result.keys())

    # Value coercion
    def test_dict_value_coercion(self) -> None:
        result = frfr.validate(dict[str, float], {"a": 1, "b": 2})
        assert result == {"a": 1.0, "b": 2.0}
        assert all(isinstance(v, float) for v in result.values())

    # Nested dicts
    def test_nested_dict(self) -> None:
        result = frfr.validate(dict[str, dict[str, int]], {"outer": {"inner": 42}})
        assert result == {"outer": {"inner": 42}}
        assert isinstance(result["outer"], dict)

    # Mapping coercion
    def test_ordered_dict_coerces_to_dict(self) -> None:
        data = collections.OrderedDict([("a", 1), ("b", 2)])
        result = frfr.validate(dict[str, int], data)
        assert result == {"a": 1, "b": 2}
        assert type(result) is dict

    def test_mapping_proxy_coerces_to_dict(self) -> None:
        data = types.MappingProxyType({"a": 1, "b": 2})
        result = frfr.validate(dict[str, int], data)
        assert result == {"a": 1, "b": 2}
        assert type(result) is dict

    def test_defaultdict_coerces_to_dict(self) -> None:
        data: collections.defaultdict[str, int] = collections.defaultdict(int)
        data["a"] = 1
        data["b"] = 2
        result = frfr.validate(dict[str, int], data)
        assert result == {"a": 1, "b": 2}
        assert type(result) is dict

    def test_counter_coerces_to_dict(self) -> None:
        data = collections.Counter({"a": 1, "b": 2})
        result = frfr.validate(dict[str, int], data)
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
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(dict, value)
        assert f"expected dict, got {expected_type_name}" in str(exc_info.value)

    def test_namedtuple_instance_to_dict(self) -> None:
        user = UserNamedTuple(name="bestie", age=25)
        result = frfr.validate(dict, user)
        assert result == {"name": "bestie", "age": 25}
        assert type(result) is dict

    def test_rejects_invalid_key_type(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(dict[str, int], {1: 1})
        assert "expected str, got int" in str(exc_info.value)

    def test_rejects_invalid_value_type(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(dict[str, int], {"a": "not an int"})
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_bool_key_for_int_key(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(dict[int, str], {True: "a"})
        assert "expected int, got bool" in str(exc_info.value)

    # Error path tests
    def test_error_path_shows_key(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(dict[str, int], {"a": 1, "b": "bad"})
        assert exc_info.value.path == ".b"
        assert ".b - expected int" in str(exc_info.value)

    def test_error_path_nested_dict(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(dict[str, dict[str, int]], {"outer": {"inner": "bad"}})
        assert exc_info.value.path == ".outer.inner"
        assert ".outer.inner - expected int" in str(exc_info.value)

    def test_error_path_invalid_key_shows_key_marker(self) -> None:
        """Invalid key should show [key] marker to distinguish from value errors."""
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(dict[int, str], {"foo": "bar"})
        assert exc_info.value.path == ".foo[key]"
        assert ".foo[key] - expected int" in str(exc_info.value)

    def test_error_path_invalid_key_nested(self) -> None:
        """Invalid key in nested dict should show full path with [key] marker."""
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(dict[str, dict[int, str]], {"outer": {"bad": "val"}})
        assert exc_info.value.path == ".outer.bad[key]"
        assert ".outer.bad[key] - expected int" in str(exc_info.value)

    def test_error_path_non_identifier_key_uses_brackets(self) -> None:
        """Non-identifier keys should use bracket notation."""
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(dict[str, int], {"a.b": "bad"})
        assert exc_info.value.path == "['a.b']"
        assert "['a.b'] - expected int" in str(exc_info.value)

    def test_error_path_key_with_spaces_uses_brackets(self) -> None:
        """Keys with spaces should use bracket notation."""
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(dict[str, int], {"my key": "bad"})
        assert exc_info.value.path == "['my key']"
        assert "['my key'] - expected int" in str(exc_info.value)

    def test_error_path_numeric_key_uses_brackets(self) -> None:
        """Numeric keys should use bracket notation."""
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(dict[int, int], {123: "bad"})
        assert exc_info.value.path == "[123]"
        assert "[123] - expected int" in str(exc_info.value)


class TestValidateUnion:
    """Tests for Union validation.

    Union types are tried in declaration order. The first type that
    successfully validates (including coercion) wins.

    Note: pyright complains about UnionType not being type[T], but this works
    at runtime. All validate() calls use pyright: ignore for this reason.
    """

    # Basic union - Union[A, B] syntax
    def test_union_first_type_matches(self) -> None:
        result = frfr.validate(Union[int, str], 42)  # type: ignore[arg-type]
        assert result == 42
        assert isinstance(result, int)

    def test_union_second_type_matches(self) -> None:
        result = frfr.validate(Union[int, str], "hello")  # type: ignore[arg-type]
        assert result == "hello"
        assert isinstance(result, str)

    # Basic union - A | B syntax
    def test_pipe_union_first_type_matches(self) -> None:
        result = frfr.validate(int | str, 42)  # type: ignore[arg-type]
        assert result == 42
        assert isinstance(result, int)

    def test_pipe_union_second_type_matches(self) -> None:
        result = frfr.validate(int | str, "hello")  # type: ignore[arg-type]
        assert result == "hello"
        assert isinstance(result, str)

    # Order matters with coercion
    def test_union_float_int_coerces_to_float(self) -> None:
        # int coerces to float, so float wins when it comes first
        result = frfr.validate(float | int, 42)  # type: ignore[arg-type]
        assert result == 42.0
        assert isinstance(result, float)

    def test_union_int_float_keeps_int(self) -> None:
        # int comes first and matches exactly, no coercion needed
        result = frfr.validate(int | float, 42)  # type: ignore[arg-type]
        assert result == 42
        assert isinstance(result, int)

    def test_union_float_str_coerces_int_to_float(self) -> None:
        # int isn't in union, but coerces to float
        result = frfr.validate(float | str, 1)  # type: ignore[arg-type]
        assert result == 1.0
        assert isinstance(result, float)

    # Union with None (similar to Optional)
    def test_union_with_none_accepts_value(self) -> None:
        result = frfr.validate(Union[int, None], 42)  # type: ignore[arg-type]
        assert result == 42
        assert isinstance(result, int)

    def test_union_with_none_accepts_none(self) -> None:
        result = frfr.validate(Union[int, None], None)  # type: ignore[arg-type]
        assert result is None

    # Optional[T] using A | None syntax
    def test_optional_accepts_value(self) -> None:
        result = frfr.validate(int | None, 42)  # type: ignore[arg-type]
        assert result == 42
        assert isinstance(result, int)

    def test_optional_accepts_none(self) -> None:
        result = frfr.validate(int | None, None)  # type: ignore[arg-type]
        assert result is None

    def test_optional_rejects_wrong_type(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(int | None, "not an int")  # type: ignore[arg-type]

    # Optional with coercion
    def test_optional_float_coerces_int(self) -> None:
        result = frfr.validate(float | None, 42)  # type: ignore[arg-type]
        assert result == 42.0
        assert isinstance(result, float)

    # Complex unions
    def test_union_three_types(self) -> None:
        result = frfr.validate(int | str | list[int], [1, 2, 3])  # type: ignore[arg-type]
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_union_with_list(self) -> None:
        result = frfr.validate(str | list[int], [1, 2, 3])  # type: ignore[arg-type]
        assert result == [1, 2, 3]

    def test_union_with_dict(self) -> None:
        result = frfr.validate(str | dict[str, int], {"a": 1})  # type: ignore[arg-type]
        assert result == {"a": 1}

    # Nested unions (Python flattens these)
    def test_nested_union_flattened(self) -> None:
        # Union[Union[int, str], bool] is flattened to Union[int, str, bool]
        result = frfr.validate(Union[Union[int, str], bool], True)  # type: ignore[arg-type]
        # bool comes last, but int would reject bool, str would reject bool
        # so bool should match
        assert result is True
        assert isinstance(result, bool)

    # Bool handling in unions
    def test_union_int_str_rejects_bool(self) -> None:
        # bool is rejected by int (strict), and rejected by str
        with pytest.raises(frfr.ValidationError):
            frfr.validate(int | str, True)  # type: ignore[arg-type]

    def test_union_with_bool_accepts_bool(self) -> None:
        result = frfr.validate(int | bool, True)  # type: ignore[arg-type]
        # int rejects bool, so bool matches
        assert result is True
        assert isinstance(result, bool)

    # Rejection tests
    def test_rejects_when_no_type_matches(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(int | str, [1, 2, 3])  # type: ignore[arg-type]
        # Error message format may vary
        error_msg = str(exc_info.value)
        assert "int" in error_msg or "str" in error_msg

    def test_rejects_none_when_not_in_union(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(int | str, None)  # type: ignore[arg-type]

    # Error path tests
    def test_error_path_preserved_in_nested_union(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(
                list[int | str],
                [1, "two", ["not int or str"]],
            )
        assert exc_info.value.path == "[2]"
        assert "[2] - expected" in str(exc_info.value)

    def test_error_path_optional_in_dict(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(
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
        result = frfr.validate(set, {1, 2, 3})
        assert result == {1, 2, 3}
        assert isinstance(result, set)

    def test_empty_set(self) -> None:
        result = frfr.validate(set, set())
        assert result == set()
        assert isinstance(result, set)

    # Always returns new set (mutable container)
    def test_returns_new_set(self) -> None:
        original = {1, 2, 3}
        result = frfr.validate(set, original)
        assert result == original
        assert result is not original

    def test_returns_new_set_parameterized(self) -> None:
        original = {1, 2, 3}
        result = frfr.validate(set[int], original)
        assert result == original
        assert result is not original

    # Parameterized set[T]
    def test_set_of_int(self) -> None:
        result = frfr.validate(set[int], {1, 2, 3})
        assert result == {1, 2, 3}
        assert isinstance(result, set)
        assert all(isinstance(x, int) for x in result)

    def test_set_of_str(self) -> None:
        result = frfr.validate(set[str], {"a", "b", "c"})
        assert result == {"a", "b", "c"}
        assert isinstance(result, set)

    # Frozenset coerces to set (lossless, both are set-like)
    def test_frozenset_coerces_to_set(self) -> None:
        result = frfr.validate(set[int], frozenset({1, 2, 3}))
        assert result == {1, 2, 3}
        assert isinstance(result, set)

    # Element coercion (int -> float still works)
    def test_set_element_coercion(self) -> None:
        result = frfr.validate(set[float], {1, 2, 3})
        assert result == {1.0, 2.0, 3.0}
        assert all(isinstance(x, float) for x in result)

    # Rejection tests - no list/tuple coercion
    def test_rejects_list(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(set, [1, 2, 3])
        assert "expected set, got list" in str(exc_info.value)

    def test_rejects_tuple(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(set, (1, 2, 3))
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
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(set, value)
        assert f"expected set, got {expected_type_name}" in str(exc_info.value)

    def test_rejects_invalid_element_type(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(set[int], {1, 2, "three"})
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_bool_in_int_set(self) -> None:
        # Note: {1, True} collapses to {1} in Python since True == 1
        # Use {True, 2} which becomes {True, 2} to test bool rejection
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(set[int], {True, 2, 3})
        assert "expected int, got bool" in str(exc_info.value)


class TestValidateFrozenset:
    """Tests for frozenset validation.

    Only accepts set/frozenset as input - same reasoning as set.
    """

    # Unparameterized frozenset
    def test_unparameterized_frozenset(self) -> None:
        result = frfr.validate(frozenset, frozenset({1, 2, 3}))
        assert result == frozenset({1, 2, 3})
        assert isinstance(result, frozenset)

    def test_empty_frozenset(self) -> None:
        result = frfr.validate(frozenset, frozenset())
        assert result == frozenset()
        assert isinstance(result, frozenset)

    # Parameterized frozenset[T]
    def test_frozenset_of_int(self) -> None:
        result = frfr.validate(frozenset[int], frozenset({1, 2, 3}))
        assert result == frozenset({1, 2, 3})
        assert isinstance(result, frozenset)
        assert all(isinstance(x, int) for x in result)

    # Set coerces to frozenset (lossless)
    def test_set_coerces_to_frozenset(self) -> None:
        result = frfr.validate(frozenset[int], {1, 2, 3})
        assert result == frozenset({1, 2, 3})
        assert isinstance(result, frozenset)

    # Element coercion
    def test_frozenset_element_coercion(self) -> None:
        result = frfr.validate(frozenset[float], {1, 2, 3})
        assert result == frozenset({1.0, 2.0, 3.0})
        assert all(isinstance(x, float) for x in result)

    # Rejection tests - no list/tuple coercion
    def test_rejects_list(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(frozenset, [1, 2, 3])
        assert "expected frozenset, got list" in str(exc_info.value)

    def test_rejects_tuple(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(frozenset, (1, 2, 3))
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
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(frozenset, value)
        assert f"expected frozenset, got {expected_type_name}" in str(exc_info.value)

    def test_rejects_invalid_element_type(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(frozenset[int], {1, 2, "three"})
        assert "expected int, got str" in str(exc_info.value)


class TestValidateLiteral:
    """Tests for Literal validation.

    Literal types validate that a value is exactly one of the specified
    literal values. Uses strict type matching (no coercion).
    """

    # String literals
    def test_literal_string_valid(self) -> None:
        result = frfr.validate(Literal["a", "b", "c"], "a")  # type: ignore[arg-type]
        assert result == "a"

    def test_literal_string_second_option(self) -> None:
        result = frfr.validate(Literal["a", "b", "c"], "b")  # type: ignore[arg-type]
        assert result == "b"

    def test_literal_single_string(self) -> None:
        result = frfr.validate(Literal["only"], "only")  # type: ignore[arg-type]
        assert result == "only"

    # Int literals
    def test_literal_int_valid(self) -> None:
        result = frfr.validate(Literal[1, 2, 3], 1)  # type: ignore[arg-type]
        assert result == 1
        assert isinstance(result, int)

    def test_literal_negative_int(self) -> None:
        result = frfr.validate(Literal[-1, 0, 1], -1)  # type: ignore[arg-type]
        assert result == -1

    # Bool literals
    def test_literal_bool_true(self) -> None:
        result = frfr.validate(Literal[True], True)  # type: ignore[arg-type]
        assert result is True

    def test_literal_bool_false(self) -> None:
        result = frfr.validate(Literal[False], False)  # type: ignore[arg-type]
        assert result is False

    def test_literal_bool_both(self) -> None:
        result = frfr.validate(Literal[True, False], True)  # type: ignore[arg-type]
        assert result is True
        result = frfr.validate(Literal[True, False], False)  # type: ignore[arg-type]
        assert result is False

    # None literal
    def test_literal_none(self) -> None:
        result = frfr.validate(Literal[None], None)  # type: ignore[arg-type]
        assert result is None

    # Mixed literals
    def test_literal_mixed_types(self) -> None:
        result = frfr.validate(Literal["a", 1, None], "a")  # type: ignore[arg-type]
        assert result == "a"
        result = frfr.validate(Literal["a", 1, None], 1)  # type: ignore[arg-type]
        assert result == 1
        result = frfr.validate(Literal["a", 1, None], None)  # type: ignore[arg-type]
        assert result is None

    # Strict matching - no coercion
    def test_literal_int_rejects_float(self) -> None:
        # 1.0 is not 1 for Literal purposes
        with pytest.raises(frfr.ValidationError):
            frfr.validate(Literal[1, 2, 3], 1.0)  # type: ignore[arg-type]

    def test_literal_int_rejects_bool(self) -> None:
        # True is not 1 for Literal purposes (strict)
        with pytest.raises(frfr.ValidationError):
            frfr.validate(Literal[1], True)  # type: ignore[arg-type]

    def test_literal_bool_rejects_int(self) -> None:
        # 1 is not True for Literal purposes (strict)
        with pytest.raises(frfr.ValidationError):
            frfr.validate(Literal[True], 1)  # type: ignore[arg-type]

    # Rejection tests
    def test_rejects_invalid_string(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(Literal["a", "b"], "c")  # type: ignore[arg-type]
        assert "Literal" in str(exc_info.value) or "'c'" in str(exc_info.value)

    def test_rejects_invalid_int(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(Literal[1, 2, 3], 4)  # type: ignore[arg-type]
        assert "Literal" in str(exc_info.value) or "4" in str(exc_info.value)

    def test_rejects_wrong_type(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(Literal["a", "b"], 1)  # type: ignore[arg-type]

    def test_rejects_none_when_not_in_literal(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(Literal["a", "b"], None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Sequence[T]
# ---------------------------------------------------------------------------


class TestValidateSequence:
    def test_sequence_from_list(self) -> None:
        result = frfr.validate(Sequence[int], [1, 2, 3])
        assert list(result) == [1, 2, 3]

    def test_sequence_from_tuple(self) -> None:
        result = frfr.validate(Sequence[int], (1, 2, 3))
        assert list(result) == [1, 2, 3]

    def test_sequence_validates_elements(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(Sequence[int], [1, "two", 3])

    def test_sequence_coerces_elements(self) -> None:
        result = frfr.validate(Sequence[float], [1, 2, 3])
        assert all(type(x) is float for x in result)

    def test_sequence_rejects_str(self) -> None:
        # str is technically a Sequence but should not match Sequence[str]
        with pytest.raises(frfr.ValidationError):
            frfr.validate(Sequence[str], "hello")

    def test_sequence_rejects_dict(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(Sequence[str], {"a": 1})

    def test_sequence_empty(self) -> None:
        result = frfr.validate(Sequence[int], [])
        assert list(result) == []

    def test_sequence_nested(self) -> None:
        result = frfr.validate(Sequence[Sequence[int]], [[1, 2], [3, 4]])
        assert [list(row) for row in result] == [[1, 2], [3, 4]]


# ---------------------------------------------------------------------------
# Mapping[K, V]
# ---------------------------------------------------------------------------


class TestValidateMapping:
    def test_mapping_from_dict(self) -> None:
        result = frfr.validate(collections.abc.Mapping[str, int], {"a": 1, "b": 2})
        assert dict(result) == {"a": 1, "b": 2}

    def test_mapping_validates_values(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(collections.abc.Mapping[str, int], {"a": "not-int"})

    def test_mapping_validates_keys(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(collections.abc.Mapping[int, str], {"not-int": "val"})

    def test_mapping_coerces_values(self) -> None:
        result = frfr.validate(collections.abc.Mapping[str, float], {"a": 1, "b": 2})
        assert dict(result) == {"a": 1.0, "b": 2.0}

    def test_mapping_from_ordered_dict(self) -> None:
        od = collections.OrderedDict([("x", 1), ("y", 2)])
        result = frfr.validate(collections.abc.Mapping[str, int], od)
        assert dict(result) == {"x": 1, "y": 2}

    def test_mapping_rejects_list(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(collections.abc.Mapping[str, int], [("a", 1)])

    def test_mapping_empty(self) -> None:
        result = frfr.validate(collections.abc.Mapping[str, int], {})
        assert dict(result) == {}


# ---------------------------------------------------------------------------
# Final[T]
# ---------------------------------------------------------------------------


class TestValidateFinal:
    def test_final_int(self) -> None:
        result = frfr.validate(Final[int], 42)  # type: ignore[arg-type]
        assert result == 42
        assert type(result) is int

    def test_final_str(self) -> None:
        result = frfr.validate(Final[str], "hello")  # type: ignore[arg-type]
        assert result == "hello"

    def test_final_rejects_wrong_type(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(Final[int], "not-an-int")  # type: ignore[arg-type]

    def test_final_in_dataclass(self) -> None:
        @dataclasses.dataclass
        class Config:
            max_retries: Final[int]

        result = frfr.validate(Config, {"max_retries": 3})
        assert result.max_retries == 3


# ---------------------------------------------------------------------------
# NewType
# ---------------------------------------------------------------------------


class TestNewType:
    """Tests for NewType validation — should unwrap and validate as the base type."""

    def test_newtype_int_valid(self) -> None:
        result = frfr.validate(UserId, 42)  # ty: ignore[invalid-argument-type]
        assert result == 42
        assert type(result) is int

    def test_newtype_str_valid(self) -> None:
        result = frfr.validate(Username, "alice")  # ty: ignore[invalid-argument-type]
        assert result == "alice"
        assert type(result) is str

    def test_newtype_rejects_wrong_type(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(UserId, "not-an-int")  # type: ignore[arg-type]

    def test_newtype_rejects_bool(self) -> None:
        # bool is a subclass of int, but frfr rejects it for int
        with pytest.raises(frfr.ValidationError):
            frfr.validate(UserId, True)  # type: ignore[arg-type]

    def test_newtype_rejects_float(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(UserId, 1.0)  # type: ignore[arg-type]

    def test_newtype_of_newtype(self) -> None:
        # SpecialUserId -> UserId -> int; should validate as int
        result = frfr.validate(SpecialUserId, 99)  # ty: ignore[invalid-argument-type]
        assert result == 99
        assert type(result) is int

    def test_newtype_in_list(self) -> None:
        result = frfr.validate(list[UserId], [1, 2, 3])
        assert result == [1, 2, 3]

    def test_newtype_in_optional(self) -> None:
        assert frfr.validate(UserId | None, None) is None  # type: ignore[arg-type]
        assert frfr.validate(UserId | None, 5) == 5  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Annotated (transparent)
# ---------------------------------------------------------------------------


class TestAnnotatedTransparent:
    """Tests for Annotated — metadata is ignored, inner type is used for validation."""

    def test_annotated_int(self) -> None:
        result = frfr.validate(Annotated[int, "some metadata"], 42)  # type: ignore[arg-type]
        assert result == 42
        assert type(result) is int

    def test_annotated_str(self) -> None:
        result = frfr.validate(Annotated[str, 99], "hello")  # type: ignore[arg-type]
        assert result == "hello"

    def test_annotated_rejects_wrong_type(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(Annotated[int, "meta"], "not-an-int")  # type: ignore[arg-type]

    def test_annotated_with_multiple_metadata(self) -> None:
        result = frfr.validate(Annotated[int, "a", "b", "c"], 7)  # type: ignore[arg-type]
        assert result == 7

    def test_annotated_list(self) -> None:
        result = frfr.validate(Annotated[list[int], "note"], [1, 2, 3])  # type: ignore[arg-type]
        assert result == [1, 2, 3]

    def test_annotated_optional(self) -> None:
        result = frfr.validate(Annotated[int | None, "nullable"], None)  # type: ignore[arg-type]
        assert result is None

    def test_annotated_in_dataclass_field(self) -> None:
        @dataclasses.dataclass
        class Model:
            value: Annotated[int, "must be positive"]

        result = frfr.validate(Model, {"value": 10})
        assert result.value == 10

    def test_annotated_in_typed_dict_field(self) -> None:
        class Model(TypedDict):
            value: Annotated[str, "description"]

        result = frfr.validate(Model, {"value": "hello"})
        assert result["value"] == "hello"

    def test_annotated_newtype(self) -> None:
        # Annotated wrapping a NewType should unwrap both
        result = frfr.validate(Annotated[UserId, "annotated newtype"], 5)  # type: ignore[arg-type]
        assert result == 5
        assert type(result) is int
