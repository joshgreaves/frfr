"""Tests for structured type validation: TypedDict, dataclass, NamedTuple."""

import collections
import dataclasses
from typing import (
    NamedTuple,
    NotRequired,
    Required,
    TypedDict,
)

import pytest

import frfr


# ---------------------------------------------------------------------------
# Shared type definitions
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


class TestValidateTypedDict:
    """Tests for TypedDict validation."""

    def test_simple_typed_dict(self) -> None:
        result = frfr.validate(UserTypedDict, {"name": "bestie", "age": 25})
        assert result == {"name": "bestie", "age": 25}
        assert isinstance(result, dict)

    def test_typed_dict_coerces_values(self) -> None:
        result = frfr.validate(StatsTypedDict, {"score": 100, "count": 5})
        assert result == {"score": 100.0, "count": 5.0}
        assert all(isinstance(v, float) for v in result.values())

    def test_typed_dict_with_optional_keys(self) -> None:
        # With optional key present
        result = frfr.validate(ConfigTypedDict, {"name": "app", "debug": True})
        assert result == {"name": "app", "debug": True}

        # Without optional key
        result = frfr.validate(ConfigTypedDict, {"name": "app"})
        assert result == {"name": "app"}

    def test_typed_dict_with_required_keys(self) -> None:
        result = frfr.validate(ConfigTotalFalseTypedDict, {"name": "app"})
        assert result == {"name": "app"}

    def test_nested_typed_dict(self) -> None:
        result = frfr.validate(
            PersonTypedDict,
            {"name": "bestie", "address": {"city": "NYC", "zip_code": "10001"}},
        )
        assert result == {
            "name": "bestie",
            "address": {"city": "NYC", "zip_code": "10001"},
        }

    def test_typed_dict_from_mapping(self) -> None:
        data = collections.OrderedDict([("name", "bestie"), ("age", 25)])
        result = frfr.validate(UserTypedDict, data)
        assert result == {"name": "bestie", "age": 25}
        assert type(result) is dict

    def test_namedtuple_instance_to_typed_dict(self) -> None:
        user = UserNamedTuple(name="bestie", age=25)
        result = frfr.validate(UserTypedDict, user)
        assert result == {"name": "bestie", "age": 25}

    # Rejection tests
    def test_rejects_missing_required_key(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(UserTypedDict, {"name": "bestie"})
        assert "age" in str(exc_info.value)

    def test_rejects_wrong_value_type(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(UserTypedDict, {"name": "bestie", "age": "twenty five"})
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_extra_keys(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(
                UserTypedDict, {"name": "bestie", "age": 25, "extra": "field"}
            )
        assert "extra" in str(exc_info.value)
        assert "unexpected key" in str(exc_info.value)

    def test_rejects_non_mapping(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(UserTypedDict, "not a dict")
        assert "expected UserTypedDict, got str" in str(exc_info.value)

    # Error path tests
    def test_error_path_shows_field_name(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(UserTypedDict, {"name": "alice", "age": "bad"})
        assert exc_info.value.path == ".age"
        assert ".age - expected int" in str(exc_info.value)

    def test_error_path_nested_typed_dict(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(
                PersonTypedDict,
                {"name": "alice", "address": {"city": "NYC", "zip_code": 12345}},
            )
        assert exc_info.value.path == ".address.zip_code"
        assert ".address.zip_code - expected str" in str(exc_info.value)


class TestValidateDataclass:
    """Tests for dataclass validation.

    Dataclasses and dicts/Mappings are considered equivalent:
    - validate(MyDataclass, dict) constructs the dataclass from the dict
    - validate(dict, my_dataclass_instance) converts via dataclasses.asdict()
    - validate(MyDataclass, other_dataclass_instance) also works
    """

    # Basic construction from dict
    def test_simple_dataclass_from_dict(self) -> None:
        result = frfr.validate(UserDataclass, {"name": "bestie", "age": 25})
        assert isinstance(result, UserDataclass)
        assert result.name == "bestie"
        assert result.age == 25

    def test_dataclass_field_coercion(self) -> None:
        result = frfr.validate(StatsDataclass, {"score": 1, "count": 2})
        assert isinstance(result, StatsDataclass)
        assert result.score == 1.0
        assert result.count == 2.0
        assert isinstance(result.score, float)

    # Defaults
    def test_dataclass_with_defaults_all_provided(self) -> None:
        result = frfr.validate(
            UserWithDefaultsDataclass,
            {"name": "bestie", "age": 30, "active": False},
        )
        assert isinstance(result, UserWithDefaultsDataclass)
        assert result.age == 30
        assert result.active is False

    def test_dataclass_uses_defaults_for_missing_fields(self) -> None:
        result = frfr.validate(UserWithDefaultsDataclass, {"name": "bestie"})
        assert isinstance(result, UserWithDefaultsDataclass)
        assert result.age == 0
        assert result.active is True

    def test_dataclass_with_default_factory(self) -> None:
        result = frfr.validate(UserWithFactoryDataclass, {"name": "bestie"})
        assert isinstance(result, UserWithFactoryDataclass)
        assert result.tags == []

    def test_dataclass_with_default_factory_provided(self) -> None:
        result = frfr.validate(
            UserWithFactoryDataclass, {"name": "bestie", "tags": ["a", "b"]}
        )
        assert isinstance(result, UserWithFactoryDataclass)
        assert result.tags == ["a", "b"]

    # Nested dataclasses
    def test_nested_dataclass(self) -> None:
        result = frfr.validate(
            PersonDataclass,
            {"name": "bestie", "address": {"city": "NYC", "zip_code": "10001"}},
        )
        assert isinstance(result, PersonDataclass)
        assert isinstance(result.address, AddressDataclass)
        assert result.address.city == "NYC"

    # From Mapping types
    def test_dataclass_from_ordered_dict(self) -> None:
        data = collections.OrderedDict([("name", "bestie"), ("age", 25)])
        result = frfr.validate(UserDataclass, data)
        assert isinstance(result, UserDataclass)
        assert result.name == "bestie"

    # Dataclass <-> dict equivalence
    def test_dataclass_instance_to_dict(self) -> None:
        user = UserDataclass(name="bestie", age=25)
        result = frfr.validate(dict, user)
        assert result == {"name": "bestie", "age": 25}
        assert type(result) is dict

    def test_dataclass_instance_to_typed_dict(self) -> None:
        user = UserDataclass(name="bestie", age=25)
        result = frfr.validate(UserTypedDict, user)
        assert result == {"name": "bestie", "age": 25}

    def test_dataclass_instance_to_dataclass(self) -> None:
        user = UserDataclass(name="bestie", age=25)
        result = frfr.validate(UserDataclass, user)
        assert isinstance(result, UserDataclass)
        assert result.name == "bestie"
        assert result.age == 25

    def test_dataclass_init_false_fields_are_ignored(self) -> None:
        """Fields with init=False are excluded from validation and construction."""

        @dataclasses.dataclass
        class WithComputed:
            value: int
            doubled: int = dataclasses.field(init=False)

            def __post_init__(self) -> None:
                self.doubled = self.value * 2

        result = frfr.validate(WithComputed, {"value": 5})
        assert result.value == 5
        assert result.doubled == 10

    def test_dataclass_init_false_field_in_input_is_rejected(self) -> None:
        """Providing a value for an init=False field is treated as an unexpected field."""

        @dataclasses.dataclass
        class WithComputed:
            value: int
            doubled: int = dataclasses.field(init=False)

            def __post_init__(self) -> None:
                self.doubled = self.value * 2

        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(WithComputed, {"value": 5, "doubled": 10})
        assert "doubled" in str(exc_info.value)

    def test_namedtuple_instance_to_dataclass(self) -> None:
        user = UserNamedTuple(name="bestie", age=25)
        result = frfr.validate(UserDataclass, user)
        assert isinstance(result, UserDataclass)
        assert result.name == "bestie"
        assert result.age == 25

    # Rejection tests
    def test_rejects_missing_required_field(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(UserDataclass, {"name": "bestie"})
        assert "age" in str(exc_info.value)

    def test_rejects_extra_keys(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(
                UserDataclass, {"name": "bestie", "age": 25, "extra": "field"}
            )
        assert "extra" in str(exc_info.value)

    def test_rejects_invalid_field_type(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(UserDataclass, {"name": "bestie", "age": "twenty five"})
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_non_mapping(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(UserDataclass, "not a dict")
        assert "expected UserDataclass, got str" in str(exc_info.value)

    def test_rejects_list(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(UserDataclass, [("name", "bestie"), ("age", 25)])

    # Error path tests
    def test_error_path_shows_field_name(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(UserDataclass, {"name": "alice", "age": "bad"})
        assert exc_info.value.path == ".age"
        assert ".age - expected int" in str(exc_info.value)

    def test_error_path_nested_dataclass(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(
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
        result = frfr.validate(UserNamedTuple, {"name": "bestie", "age": 25})
        assert isinstance(result, UserNamedTuple)
        assert result.name == "bestie"
        assert result.age == 25

    def test_namedtuple_field_coercion_from_dict(self) -> None:
        result = frfr.validate(StatsNamedTuple, {"score": 1, "count": 2})
        assert isinstance(result, StatsNamedTuple)
        assert result.score == 1.0
        assert result.count == 2.0
        assert isinstance(result.score, float)

    # Construction from tuple/list (positional)
    def test_namedtuple_from_tuple(self) -> None:
        result = frfr.validate(UserNamedTuple, ("bestie", 25))
        assert isinstance(result, UserNamedTuple)
        assert result.name == "bestie"
        assert result.age == 25

    def test_namedtuple_from_list(self) -> None:
        result = frfr.validate(UserNamedTuple, ["bestie", 25])
        assert isinstance(result, UserNamedTuple)
        assert result.name == "bestie"
        assert result.age == 25

    def test_namedtuple_field_coercion_from_tuple(self) -> None:
        result = frfr.validate(StatsNamedTuple, (1, 2))
        assert isinstance(result, StatsNamedTuple)
        assert result.score == 1.0
        assert result.count == 2.0

    # Defaults
    def test_namedtuple_with_defaults_from_dict(self) -> None:
        result = frfr.validate(UserWithDefaultsNamedTuple, {"name": "bestie"})
        assert isinstance(result, UserWithDefaultsNamedTuple)
        assert result.name == "bestie"
        assert result.age == 0
        assert result.active is True

    def test_namedtuple_with_defaults_all_provided(self) -> None:
        result = frfr.validate(
            UserWithDefaultsNamedTuple, {"name": "bestie", "age": 30, "active": False}
        )
        assert isinstance(result, UserWithDefaultsNamedTuple)
        assert result.age == 30
        assert result.active is False

    # Nested NamedTuples
    def test_nested_namedtuple_from_dict(self) -> None:
        result = frfr.validate(
            PersonNamedTuple,
            {"name": "bestie", "address": {"city": "NYC", "zip_code": "10001"}},
        )
        assert isinstance(result, PersonNamedTuple)
        assert isinstance(result.address, AddressNamedTuple)
        assert result.address.city == "NYC"

    # From Mapping types
    def test_namedtuple_from_ordered_dict(self) -> None:
        data = collections.OrderedDict([("name", "bestie"), ("age", 25)])
        result = frfr.validate(UserNamedTuple, data)
        assert isinstance(result, UserNamedTuple)
        assert result.name == "bestie"

    # Cross-type conversions where target IS NamedTuple
    def test_namedtuple_from_namedtuple(self) -> None:
        user = UserNamedTuple(name="bestie", age=25)
        result = frfr.validate(UserNamedTuple, user)
        assert isinstance(result, UserNamedTuple)
        assert result.name == "bestie"
        assert result.age == 25

    def test_typed_dict_to_namedtuple(self) -> None:
        data: UserTypedDict = {"name": "bestie", "age": 25}
        result = frfr.validate(UserNamedTuple, data)
        assert isinstance(result, UserNamedTuple)
        assert result.name == "bestie"

    def test_dataclass_to_namedtuple(self) -> None:
        user = UserDataclass(name="bestie", age=25)
        result = frfr.validate(UserNamedTuple, user)
        assert isinstance(result, UserNamedTuple)
        assert result.name == "bestie"
        assert result.age == 25

    # Rejection tests
    def test_rejects_wrong_length_tuple(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(UserNamedTuple, ("bestie",))

    def test_rejects_too_many_positional(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(UserNamedTuple, ("bestie", 25, "extra"))

    def test_rejects_missing_required_field(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(UserNamedTuple, {"name": "bestie"})
        assert "age" in str(exc_info.value)

    def test_rejects_extra_keys(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(
                UserNamedTuple, {"name": "bestie", "age": 25, "extra": "field"}
            )
        assert "extra" in str(exc_info.value)

    def test_rejects_invalid_field_type_from_dict(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(UserNamedTuple, {"name": "bestie", "age": "twenty five"})
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_invalid_element_type_from_tuple(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(UserNamedTuple, ("bestie", "not an int"))
        assert "expected int, got str" in str(exc_info.value)

    def test_rejects_non_mapping_non_sequence(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(UserNamedTuple, "not a tuple or dict")
        assert "expected UserNamedTuple, got str" in str(exc_info.value)

    # Error path tests
    def test_error_path_from_dict_shows_field(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(UserNamedTuple, {"name": "alice", "age": "bad"})
        assert exc_info.value.path == ".age"
        assert ".age - expected int" in str(exc_info.value)

    def test_error_path_from_tuple_shows_index(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(UserNamedTuple, ("alice", "bad"))
        assert exc_info.value.path == "[1]"
        assert "[1] - expected int" in str(exc_info.value)

    def test_error_path_nested_from_dict(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(
                PersonNamedTuple,
                {"name": "alice", "address": {"city": 123, "zip_code": "12345"}},
            )
        assert exc_info.value.path == ".address.city"
        assert ".address.city - expected str" in str(exc_info.value)

    def test_error_path_nested_from_tuple(self) -> None:
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(PersonNamedTuple, ("alice", (123, "12345")))
        assert exc_info.value.path == "[1][0]"
        assert "[1][0] - expected str" in str(exc_info.value)

    # collections.namedtuple (untyped, no type hints)
    def test_collections_namedtuple_from_dict(self) -> None:
        """collections.namedtuple has no type hints, fields should be Any."""
        Point = collections.namedtuple("Point", ["x", "y"])
        result = frfr.validate(Point, {"x": 1, "y": 2})
        assert isinstance(result, Point)
        assert result.x == 1
        assert result.y == 2

    def test_collections_namedtuple_from_tuple(self) -> None:
        """collections.namedtuple from tuple input."""
        Point = collections.namedtuple("Point", ["x", "y"])
        result = frfr.validate(Point, (3, 4))
        assert isinstance(result, Point)
        assert result.x == 3
        assert result.y == 4

    def test_collections_namedtuple_accepts_any_types(self) -> None:
        """Untyped fields should accept any value (treated as Any)."""
        Point = collections.namedtuple("Point", ["x", "y"])
        result = frfr.validate(Point, {"x": "hello", "y": [1, 2, 3]})
        assert isinstance(result, Point)
        assert result.x == "hello"
        assert result.y == [1, 2, 3]

    def test_collections_namedtuple_with_defaults(self) -> None:
        """collections.namedtuple with defaults."""
        Point = collections.namedtuple("Point", ["x", "y"], defaults=[0])
        result = frfr.validate(Point, {"x": 5})
        assert isinstance(result, Point)
        assert result.x == 5
        assert result.y == 0
