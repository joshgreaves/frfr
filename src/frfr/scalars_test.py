"""Tests for scalar/primitive type validation."""

import dataclasses
import datetime as dt
import decimal
import enum
import pathlib
import uuid
from typing import Any, TypedDict

import pytest

import frfr


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
        result = frfr.validate(int, value)
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
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(int, value)
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
        result = frfr.validate(float, value)
        assert result == value
        assert isinstance(result, float)

    def test_valid_nan(self) -> None:
        result = frfr.validate(float, float("nan"))
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
        result = frfr.validate(float, value)
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
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(float, value)
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
        result = frfr.validate(str, value)
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
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(str, value)
        assert f"expected str, got {expected_type_name}" in str(exc_info.value)


class TestValidateBool:
    """Tests for bool validation."""

    @pytest.mark.parametrize(
        "value",
        [True, False],
        ids=["true", "false"],
    )
    def test_valid_bool(self, value: bool) -> None:
        result = frfr.validate(bool, value)
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
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(bool, value)
        assert f"expected bool, got {expected_type_name}" in str(exc_info.value)


class TestValidateNone:
    """Tests for None validation."""

    def test_valid_none(self) -> None:
        result = frfr.validate(type(None), None)
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
        with pytest.raises(frfr.ValidationError) as exc_info:
            frfr.validate(type(None), value)
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
        result = frfr.validate(Any, value)  # pyright: ignore[reportArgumentType]
        assert result is value  # Returns the exact same object


# ---------------------------------------------------------------------------
# bytes
# ---------------------------------------------------------------------------


class TestValidateBytes:
    def test_bytes_instance(self) -> None:
        b = b"hello"
        result = frfr.validate(bytes, b)
        assert result == b

    def test_bytes_empty(self) -> None:
        result = frfr.validate(bytes, b"")
        assert result == b""

    def test_bytes_rejects_str(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(bytes, "hello")

    def test_bytes_rejects_bytearray(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(bytes, bytearray(b"hello"))

    def test_bytes_rejects_list(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(bytes, [104, 101, 108, 108, 111])

    def test_bytes_rejects_int(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(bytes, 42)


# ---------------------------------------------------------------------------
# decimal.Decimal
# ---------------------------------------------------------------------------


class TestValidateDecimal:
    def test_decimal_instance(self) -> None:
        d = decimal.Decimal("3.14")
        result = frfr.validate(decimal.Decimal, d)
        assert result == d

    def test_decimal_from_int(self) -> None:
        result = frfr.validate(decimal.Decimal, 42)
        assert result == decimal.Decimal(42)
        assert type(result) is decimal.Decimal

    def test_decimal_from_string(self) -> None:
        result = frfr.validate(decimal.Decimal, "3.14")
        assert result == decimal.Decimal("3.14")

    def test_decimal_from_negative_string(self) -> None:
        result = frfr.validate(decimal.Decimal, "-1.5")
        assert result == decimal.Decimal("-1.5")

    def test_decimal_from_scientific_string(self) -> None:
        result = frfr.validate(decimal.Decimal, "1e10")
        assert result == decimal.Decimal("1e10")

    def test_decimal_rejects_float(self) -> None:
        # float -> Decimal is NOT lossless: Decimal(0.1) captures binary imprecision
        with pytest.raises(frfr.ValidationError):
            frfr.validate(decimal.Decimal, 1.5)

    def test_decimal_rejects_bool(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(decimal.Decimal, True)

    def test_decimal_rejects_invalid_string(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(decimal.Decimal, "not-a-number")

    def test_decimal_rejects_none(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(decimal.Decimal, None)


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class Color(enum.Enum):
    red = "red"
    green = "green"
    blue = "blue"


class Priority(enum.IntEnum):
    low = 1
    medium = 2
    high = 3


class Direction(enum.StrEnum):
    north = "north"
    south = "south"


class Permission(enum.Flag):
    read = enum.auto()
    write = enum.auto()
    execute = enum.auto()


class TestValidateEnum:
    def test_enum_from_value(self) -> None:
        result = frfr.validate(Color, "red")
        assert result is Color.red

    def test_enum_instance_passthrough(self) -> None:
        result = frfr.validate(Color, Color.green)
        assert result is Color.green

    def test_enum_all_members(self) -> None:
        assert frfr.validate(Color, "red") is Color.red
        assert frfr.validate(Color, "green") is Color.green
        assert frfr.validate(Color, "blue") is Color.blue

    def test_enum_rejects_invalid_value(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(Color, "yellow")

    def test_enum_rejects_wrong_type(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(Color, 1)

    def test_intenum_from_value(self) -> None:
        result = frfr.validate(Priority, 1)
        assert result is Priority.low

    def test_intenum_rejects_invalid_value(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(Priority, 99)

    def test_strenum_from_value(self) -> None:
        result = frfr.validate(Direction, "north")
        assert result is Direction.north

    def test_flag_from_value(self) -> None:
        result = frfr.validate(Permission, Permission.read.value)
        assert result is Permission.read

    def test_enum_in_dataclass(self) -> None:
        @dataclasses.dataclass
        class Task:
            priority: Priority

        result = frfr.validate(Task, {"priority": 2})
        assert result.priority is Priority.medium

    def test_enum_in_typed_dict(self) -> None:
        class Payload(TypedDict):
            color: Color

        result = frfr.validate(Payload, {"color": "blue"})
        assert result["color"] is Color.blue

    def test_enum_in_list(self) -> None:
        result = frfr.validate(list[Color], ["red", "green"])
        assert result == [Color.red, Color.green]


# ---------------------------------------------------------------------------
# datetime
# ---------------------------------------------------------------------------


class TestValidateDatetime:
    def test_datetime_instance(self) -> None:
        now = dt.datetime(2024, 1, 15, 12, 30, 0)
        result = frfr.validate(dt.datetime, now)
        assert result == now

    def test_datetime_from_iso_string(self) -> None:
        result = frfr.validate(dt.datetime, "2024-01-15T12:30:00")
        assert result == dt.datetime(2024, 1, 15, 12, 30, 0)

    def test_datetime_from_iso_string_with_tz(self) -> None:
        result = frfr.validate(dt.datetime, "2024-01-15T12:30:00+00:00")
        assert result.tzinfo is not None

    def test_datetime_rejects_date_instance(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(dt.datetime, dt.date(2024, 1, 15))

    def test_datetime_rejects_invalid_string(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(dt.datetime, "not-a-date")

    def test_datetime_rejects_int(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(dt.datetime, 1705316400)

    def test_date_instance(self) -> None:
        d = dt.date(2024, 1, 15)
        result = frfr.validate(dt.date, d)
        assert result == d

    def test_date_from_iso_string(self) -> None:
        result = frfr.validate(dt.date, "2024-01-15")
        assert result == dt.date(2024, 1, 15)

    def test_date_accepts_datetime_instance(self) -> None:
        # datetime is a subclass of date; accepting it is not surprising
        result = frfr.validate(dt.date, dt.datetime(2024, 1, 15, 12, 0))
        assert result == dt.date(2024, 1, 15)

    def test_date_rejects_invalid_string(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(dt.date, "not-a-date")

    def test_date_rejects_int(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(dt.date, 20240115)

    def test_time_instance(self) -> None:
        t = dt.time(12, 30, 0)
        result = frfr.validate(dt.time, t)
        assert result == t

    def test_time_from_iso_string(self) -> None:
        result = frfr.validate(dt.time, "12:30:00")
        assert result == dt.time(12, 30, 0)

    def test_time_rejects_invalid_string(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(dt.time, "25:00:00")

    def test_timedelta_instance(self) -> None:
        delta = dt.timedelta(days=3, hours=2)
        result = frfr.validate(dt.timedelta, delta)
        assert result == delta

    def test_timedelta_rejects_int(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(dt.timedelta, 86400)

    def test_timedelta_rejects_string(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(dt.timedelta, "3 days")

    def test_datetime_in_dataclass(self) -> None:
        @dataclasses.dataclass
        class Event:
            name: str
            starts_at: dt.datetime

        result = frfr.validate(
            Event, {"name": "launch", "starts_at": "2024-06-01T09:00:00"}
        )
        assert result.starts_at == dt.datetime(2024, 6, 1, 9, 0, 0)


# ---------------------------------------------------------------------------
# uuid.UUID
# ---------------------------------------------------------------------------


class TestValidateUUID:
    def test_uuid_instance(self) -> None:
        u = uuid.UUID("12345678-1234-5678-1234-567812345678")
        result = frfr.validate(uuid.UUID, u)
        assert result == u

    def test_uuid_from_string(self) -> None:
        result = frfr.validate(uuid.UUID, "12345678-1234-5678-1234-567812345678")
        assert result == uuid.UUID("12345678-1234-5678-1234-567812345678")

    def test_uuid_rejects_invalid_string(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(uuid.UUID, "not-a-uuid")

    def test_uuid_rejects_int(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(uuid.UUID, 12345678)

    def test_uuid_in_typed_dict(self) -> None:
        class Record(TypedDict):
            id: uuid.UUID

        result = frfr.validate(Record, {"id": "12345678-1234-5678-1234-567812345678"})
        assert result["id"] == uuid.UUID("12345678-1234-5678-1234-567812345678")


# ---------------------------------------------------------------------------
# pathlib.Path
# ---------------------------------------------------------------------------


class TestValidatePath:
    def test_path_instance(self) -> None:
        p = pathlib.Path("/tmp/foo")
        result = frfr.validate(pathlib.Path, p)
        assert result == p

    def test_path_from_string(self) -> None:
        result = frfr.validate(pathlib.Path, "/tmp/foo")
        assert result == pathlib.Path("/tmp/foo")

    def test_path_from_relative_string(self) -> None:
        result = frfr.validate(pathlib.Path, "foo/bar/baz.txt")
        assert result == pathlib.Path("foo/bar/baz.txt")

    def test_path_rejects_int(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(pathlib.Path, 42)

    def test_path_rejects_none(self) -> None:
        with pytest.raises(frfr.ValidationError):
            frfr.validate(pathlib.Path, None)

    def test_path_in_dataclass(self) -> None:
        @dataclasses.dataclass
        class Config:
            output: pathlib.Path

        result = frfr.validate(Config, {"output": "/tmp/out"})
        assert result.output == pathlib.Path("/tmp/out")
