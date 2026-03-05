"""Tests for the core validation machinery, error formatting, and integration."""

import dataclasses
from typing import (
    Literal,
    NamedTuple,
    TypedDict,
)

import pytest

import frfr.structured
import frfr.types
import frfr.validation

# ---------------------------------------------------------------------------
# Shared type definitions used by complex path and integration tests
# ---------------------------------------------------------------------------


class UserTypedDict(TypedDict):
    name: str
    age: int


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
class AddressDataclass:
    city: str
    zip_code: str


@dataclasses.dataclass
class PersonDataclass:
    name: str
    address: AddressDataclass


class UserNamedTuple(NamedTuple):
    name: str
    age: int


class AddressNamedTuple(NamedTuple):
    city: str
    zip_code: str


class PersonNamedTuple(NamedTuple):
    name: str
    address: AddressNamedTuple


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


class TestValidationError:
    """Tests for ValidationError formatting."""

    def test_error_includes_actual_value(self) -> None:
        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(int, "hello")
        assert "'hello'" in str(exc_info.value)

    def test_error_with_path(self) -> None:
        error = frfr.types.ValidationError(int, "bad", path="data.users[0].age")
        assert "data.users[0].age" in str(error)
        assert "expected int" in str(error)

    def test_error_without_path(self) -> None:
        error = frfr.types.ValidationError(int, "bad", path="")
        # Should not have leading dash when path is empty
        message = str(error)
        assert not message.startswith(" - ")
        assert "expected int" in message

    def test_root_level_validation_error_has_no_path(self) -> None:
        """Root level errors should have empty path."""
        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(int, "not an int")
        assert exc_info.value.path == ""
        # Message should not have path prefix
        assert str(exc_info.value).startswith("expected int")


class TestValidationErrorPathsComplex:
    """Tests for error path tracking through complex composed types.

    These tests cover combinations of multiple types nested together.
    """

    def test_list_of_dicts_error(self) -> None:
        """Error in list of dicts should show [index].key."""
        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(
                list[dict[str, int]],
                [{"a": 1}, {"b": "bad"}],
            )
        assert exc_info.value.path == "[1].b"
        assert "[1].b - expected int" in str(exc_info.value)

    def test_dict_of_lists_error(self) -> None:
        """Error in dict of lists should show .key[index]."""
        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(
                dict[str, list[int]],
                {"nums": [1, 2, "bad"]},
            )
        assert exc_info.value.path == ".nums[2]"
        assert ".nums[2] - expected int" in str(exc_info.value)

    def test_deeply_nested_structure_error(self) -> None:
        """Error in deeply nested structure."""
        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(
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

        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(ContainerTypedDict, data)
        assert exc_info.value.path == ".items[1].tags[1]"
        assert ".items[1].tags[1] - expected str" in str(exc_info.value)

    def test_list_of_dataclasses_error(self) -> None:
        """Error in list of dataclasses."""
        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(
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
        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(
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
        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(
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

        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(StatusTypedDict, {"name": "test", "status": "bad"})
        assert exc_info.value.path == ".status"
        assert ".status - expected" in str(exc_info.value)

    def test_triple_nested_lists(self) -> None:
        """Error in triple nested lists."""
        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(list[list[list[int]]], [[[1]], [[2], [3, "bad"]]])
        assert exc_info.value.path == "[1][1][1]"
        assert "[1][1][1] - expected int" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Custom Validator tests
# ---------------------------------------------------------------------------


class TestCustomValidator:
    """Tests for custom Validator instances: registration, overrides, composition."""

    def test_default_validator_is_frozen(self) -> None:
        """The module-level default validator rejects registration."""

        def noop_int(
            validator: frfr.types.ValidatorProtocol,
            target: type,
            data: object,
            path: str,
        ) -> int:
            return int(data)  # type: ignore[arg-type]

        with pytest.raises(RuntimeError, match="frozen"):
            frfr.validation._DEFAULT_VALIDATOR.register_type_handler(int, noop_int)

    def test_explicit_frozen_validator_rejects_registration(self) -> None:
        """An explicitly frozen Validator instance rejects registration."""

        def noop_int(
            validator: frfr.types.ValidatorProtocol,
            target: type[int],
            data: object,
            path: str,
        ) -> int:
            return int(data)  # type: ignore[arg-type]

        v = frfr.validation.Validator(frozen=True)
        with pytest.raises(RuntimeError, match="frozen"):
            v.register_type_handler(int, noop_int)

    def test_register_new_type(self) -> None:
        """A custom handler for an unknown type is called during validation."""

        class Celsius:
            def __init__(self, value: float) -> None:
                self.value = value

        def parse_celsius(
            validator: frfr.types.ValidatorProtocol,
            target: type[Celsius],
            data: object,
            path: str,
        ) -> Celsius:
            if not isinstance(data, int | float):
                raise frfr.types.ValidationError(target, data, path=path)
            return Celsius(float(data))

        v = frfr.validation.Validator()
        v.register_type_handler(Celsius, parse_celsius)
        result = v.validate(Celsius, 100)
        assert isinstance(result, Celsius)
        assert result.value == 100.0

    def test_override_builtin_handler(self) -> None:
        """A registered handler for int replaces the built-in one."""

        def coercing_int(
            validator: frfr.types.ValidatorProtocol,
            target: type,
            data: object,
            path: str,
        ) -> int:
            try:
                return int(data)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                raise frfr.types.ValidationError(target, data, path=path)

        v = frfr.validation.Validator()
        v.register_type_handler(int, coercing_int)
        assert v.validate(int, "42") == 42
        assert v.validate(int, 3.9) == 3
        assert v.validate(int, True) == 1

    def test_override_does_not_affect_default_validator(self) -> None:
        """Overriding a handler on a custom instance leaves the default validator unchanged."""
        v = frfr.validation.Validator()
        v.register_type_handler(int, lambda validator, target, data, path: 999)
        assert v.validate(int, 1) == 999
        assert frfr.validation.validate(int, 1) == 1

    def test_handler_receives_validator_for_recursion(self) -> None:
        """Custom handler can call frfr.validation.validate() to recurse into nested types."""

        @dataclasses.dataclass
        class Tagged:
            value: int
            tag: str

        def parse_tagged(
            validator: frfr.types.ValidatorProtocol,
            target: type,
            data: object,
            path: str,
        ) -> Tagged:
            if not isinstance(data, dict):
                raise frfr.types.ValidationError(target, data, path=path)
            return Tagged(
                value=validator._validate_at(int, data.get("value"), f"{path}.value"),  # type: ignore[arg-type]
                tag=validator._validate_at(str, data.get("tag"), f"{path}.tag"),  # type: ignore[arg-type]
            )

        v = frfr.validation.Validator()
        v.register_type_handler(Tagged, parse_tagged)
        result = v.validate(Tagged, {"value": 7, "tag": "hello"})
        assert result.value == 7
        assert result.tag == "hello"

    def test_handler_recursion_uses_overridden_handlers(self) -> None:
        """When a custom handler recurses, it uses the same validator's handlers."""
        call_log: list[str] = []

        def tracking_str(
            validator: frfr.types.ValidatorProtocol,
            target: type,
            data: object,
            path: str,
        ) -> str:
            call_log.append(str(data))
            if type(data) is not str:
                raise frfr.types.ValidationError(target, data, path=path)
            return data

        v = frfr.validation.Validator()
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
            validator: frfr.types.ValidatorProtocol,
            target: type,
            data: object,
            path: str,
        ) -> object:
            return target()

        v = frfr.validation.Validator()
        v.register_predicate_handler(lambda t: isinstance(t, MyMeta), parse_mymeta)
        assert isinstance(v.validate(MyA, {}), MyA)
        assert isinstance(v.validate(MyB, {}), MyB)

    def test_predicate_handler_overrides_builtin(self) -> None:
        """A predicate handler registered last takes priority over built-in predicate handlers."""
        seen: list[type] = []

        def spy_dataclass[T](
            validator: frfr.types.ValidatorProtocol,
            target: type[T],
            data: object,
            path: str,
        ) -> T:
            seen.append(target)
            return frfr.structured.compile_dataclass(
                target, frfr.validation._DEFAULT_VALIDATOR._get_compiled
            )(data, path)

        @dataclasses.dataclass
        class Point:
            x: int
            y: int

        v = frfr.validation.Validator()
        v.register_predicate_handler(dataclasses.is_dataclass, spy_dataclass)
        result = v.validate(Point, {"x": 1, "y": 2})
        assert seen == [Point]
        assert result == Point(x=1, y=2)

    def test_unfrozen_validator_has_all_builtins(self) -> None:
        """A fresh custom Validator has all built-in handlers."""
        v = frfr.validation.Validator()
        assert v.validate(int, 1) == 1
        assert v.validate(str, "hi") == "hi"
        assert v.validate(list[int], [1, 2, 3]) == [1, 2, 3]
        assert v.validate(UserDataclass, {"name": "alice", "age": 25}) == UserDataclass(
            "alice", 25
        )

    def test_register_type_handler_after_cache_invalidates(self) -> None:
        """Registering a new type handler invalidates compiled cache for that type."""
        v = frfr.validation.Validator()
        # Warm the cache for int
        assert v.validate(int, 5) == 5
        # Override int handler after the cache is warm
        v.register_type_handler(int, lambda validator, target, data, path: 999)
        # The new handler should be used, not the cached one
        assert v.validate(int, 5) == 999

    def test_register_type_handler_after_cache_invalidates_composite(self) -> None:
        """Registering a new handler for a child type invalidates composite compiled cache."""
        v = frfr.validation.Validator()
        # Warm the cache for list[int]
        assert v.validate(list[int], [1, 2]) == [1, 2]
        # Override int handler after the cache is warm
        v.register_type_handler(int, lambda validator, target, data, path: 0)
        # The compiled list[int] must be rebuilt to pick up the new int handler
        assert v.validate(list[int], [1, 2]) == [0, 0]

    def test_register_predicate_handler_after_cache_invalidates(self) -> None:
        """Registering a new predicate handler invalidates compiled cache."""

        @dataclasses.dataclass
        class Box:
            value: int

        v = frfr.validation.Validator()
        # Warm the cache for Box
        assert v.validate(Box, {"value": 1}) == Box(value=1)
        # Register a predicate handler that intercepts all dataclasses
        v.register_predicate_handler(
            dataclasses.is_dataclass,
            lambda validator, target, data, path: "intercepted",
        )
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
        result = frfr.validation.validate(list[PostTypedDict], data)
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
        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(list[PostTypedDict], data)
        assert exc_info.value.path == "[0].comments[1].score"

    def test_dataclass_with_nested_namedtuples_success(self) -> None:
        """Dataclass containing a list of NamedTuples validates correctly."""
        result = frfr.validation.validate(
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
        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(
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
        result = frfr.validation.validate(
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
        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(
                dict[str, list[tuple[int, str | None]]],
                {"scores": [(1, "ok"), (2, 3.14)]},  # 3.14 is not str | None
            )
        assert exc_info.value.path == ".scores[1][1]"

    def test_large_collection_validates_all_items(self) -> None:
        """All 100 items in a list must pass validation."""
        data = [
            {"id": i, "username": f"user{i}", "display_name": None} for i in range(100)
        ]
        result = frfr.validation.validate(list[AuthorTypedDict], data)
        assert len(result) == 100
        assert result[0]["id"] == 0
        assert result[99]["username"] == "user99"

    def test_large_collection_error_index(self) -> None:
        """Error in item 50 of a 51-element list reports index [50]."""
        data: list[dict[str, object]] = [
            {"id": i, "username": f"user{i}", "display_name": None} for i in range(50)
        ]
        data.append({"id": "not_an_int", "username": "bad", "display_name": None})
        with pytest.raises(frfr.types.ValidationError) as exc_info:
            frfr.validation.validate(list[AuthorTypedDict], data)
        assert exc_info.value.path == "[50].id"

    def test_int_to_float_coercion_in_nested_dataclass(self) -> None:
        """Int-to-float coercion works through dict → dataclass nesting."""
        result = frfr.validation.validate(
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
        result = frfr.validation.validate(list[PostTypedDict], data)
        assert result[0]["author"]["display_name"] == "Alice"
        assert result[0]["comments"][0]["author"]["display_name"] is None

    def test_union_inside_dict_inside_list(self) -> None:
        """list[dict[str, int | str]] validates mixed-value dicts correctly."""
        result = frfr.validation.validate(
            list[dict[str, int | str]],
            [
                {"count": 5, "label": "foo"},
                {"count": 10, "label": "bar"},
            ],
        )
        assert result[0]["count"] == 5
        assert result[0]["label"] == "foo"
        assert result[1]["label"] == "bar"
