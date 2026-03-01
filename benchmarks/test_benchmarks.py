"""Benchmarks comparing frfr against pydantic.

Models and input data mirror pydantic's own benchmark suite:
https://github.com/pydantic/pydantic/tree/main/tests/benchmarks

frfr validates already-parsed Python dicts. Two comparisons are made:
  - frfr:      validate(Model, dict_data)
  - frfr+json: json.loads(raw_json) + validate(Model, dict_data)
  - pydantic:  Model.model_validate(dict_data)
  - pydantic+json: Model.model_validate_json(raw_json)

Run with:
  uv run pytest src/frfr/benchmarks.py --benchmark-only -v
Compare across runs:
  uv run pytest src/frfr/benchmarks.py --benchmark-only --benchmark-autosave
  uv run pytest src/frfr/benchmarks.py --benchmark-only --benchmark-compare
"""

import dataclasses
import json

import pydantic
import pytest
import pytest_benchmark.fixture

import frfr


# ---------------------------------------------------------------------------
# frfr models (dataclasses) — mirror pydantic's shared.py exactly
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SimpleModel:
    field1: str
    field2: int
    field3: float


@dataclasses.dataclass
class NestedModel:
    field1: str
    field2: list[int]
    field3: dict[str, float]


@dataclasses.dataclass
class OuterModel:
    nested: NestedModel
    optional_nested: NestedModel | None


@dataclasses.dataclass
class ComplexModel:
    field1: str | int | float
    field2: list[dict[str, int | float]]
    field3: list[str | int] | None


@dataclasses.dataclass
class SimpleListModel:
    items: list[SimpleModel]


# ---------------------------------------------------------------------------
# pydantic models — same schemas
# ---------------------------------------------------------------------------


class PydanticSimpleModel(pydantic.BaseModel):
    field1: str
    field2: int
    field3: float


class PydanticNestedModel(pydantic.BaseModel):
    field1: str
    field2: list[int]
    field3: dict[str, float]


class PydanticOuterModel(pydantic.BaseModel):
    nested: PydanticNestedModel
    optional_nested: PydanticNestedModel | None


class PydanticComplexModel(pydantic.BaseModel):
    field1: str | int | float
    field2: list[dict[str, int | float]]
    field3: list[str | int] | None


class PydanticSimpleListModel(pydantic.BaseModel):
    items: list[PydanticSimpleModel]


# ---------------------------------------------------------------------------
# Input data — identical to pydantic's benchmark inputs
# ---------------------------------------------------------------------------

SIMPLE_DATA = {"field1": "test", "field2": 42, "field3": 3.14}

NESTED_DATA = {
    "nested": {"field1": "test", "field2": [1, 2, 3], "field3": {"a": 1.1, "b": 2.2}},
    "optional_nested": None,
}

COMPLEX_DATA = {
    "field1": "test",
    "field2": [{"a": 1, "b": 2.2}, {"c": 3, "d": 4.4}],
    "field3": ["test", 1, 2, "test2"],
}

LIST_DATA = {
    "items": [
        {"field1": f"test{i}", "field2": i, "field3": float(i)} for i in range(10)
    ]
}

SIMPLE_JSON = json.dumps(SIMPLE_DATA)
NESTED_JSON = json.dumps(NESTED_DATA)
COMPLEX_JSON = json.dumps(COMPLEX_DATA)
LIST_JSON = json.dumps(LIST_DATA)


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


@pytest.mark.benchmark(group="simple")
class TestSimple:
    def test_frfr(self, benchmark: pytest_benchmark.fixture.BenchmarkFixture) -> None:
        benchmark(frfr.validate, SimpleModel, SIMPLE_DATA)

    def test_frfr_json(
        self, benchmark: pytest_benchmark.fixture.BenchmarkFixture
    ) -> None:
        benchmark(lambda: frfr.validate(SimpleModel, json.loads(SIMPLE_JSON)))

    def test_pydantic(
        self, benchmark: pytest_benchmark.fixture.BenchmarkFixture
    ) -> None:
        benchmark(PydanticSimpleModel.model_validate, SIMPLE_DATA)

    def test_pydantic_json(
        self, benchmark: pytest_benchmark.fixture.BenchmarkFixture
    ) -> None:
        benchmark(PydanticSimpleModel.model_validate_json, SIMPLE_JSON)


@pytest.mark.benchmark(group="nested")
class TestNested:
    def test_frfr(self, benchmark: pytest_benchmark.fixture.BenchmarkFixture) -> None:
        benchmark(frfr.validate, OuterModel, NESTED_DATA)

    def test_frfr_json(
        self, benchmark: pytest_benchmark.fixture.BenchmarkFixture
    ) -> None:
        benchmark(lambda: frfr.validate(OuterModel, json.loads(NESTED_JSON)))

    def test_pydantic(
        self, benchmark: pytest_benchmark.fixture.BenchmarkFixture
    ) -> None:
        benchmark(PydanticOuterModel.model_validate, NESTED_DATA)

    def test_pydantic_json(
        self, benchmark: pytest_benchmark.fixture.BenchmarkFixture
    ) -> None:
        benchmark(PydanticOuterModel.model_validate_json, NESTED_JSON)


@pytest.mark.benchmark(group="complex")
class TestComplex:
    def test_frfr(self, benchmark: pytest_benchmark.fixture.BenchmarkFixture) -> None:
        benchmark(frfr.validate, ComplexModel, COMPLEX_DATA)

    def test_frfr_json(
        self, benchmark: pytest_benchmark.fixture.BenchmarkFixture
    ) -> None:
        benchmark(lambda: frfr.validate(ComplexModel, json.loads(COMPLEX_JSON)))

    def test_pydantic(
        self, benchmark: pytest_benchmark.fixture.BenchmarkFixture
    ) -> None:
        benchmark(PydanticComplexModel.model_validate, COMPLEX_DATA)

    def test_pydantic_json(
        self, benchmark: pytest_benchmark.fixture.BenchmarkFixture
    ) -> None:
        benchmark(PydanticComplexModel.model_validate_json, COMPLEX_JSON)


@pytest.mark.benchmark(group="list_of_models")
class TestListOfModels:
    def test_frfr(self, benchmark: pytest_benchmark.fixture.BenchmarkFixture) -> None:
        benchmark(frfr.validate, SimpleListModel, LIST_DATA)

    def test_frfr_json(
        self, benchmark: pytest_benchmark.fixture.BenchmarkFixture
    ) -> None:
        benchmark(lambda: frfr.validate(SimpleListModel, json.loads(LIST_JSON)))

    def test_pydantic(
        self, benchmark: pytest_benchmark.fixture.BenchmarkFixture
    ) -> None:
        benchmark(PydanticSimpleListModel.model_validate, LIST_DATA)

    def test_pydantic_json(
        self, benchmark: pytest_benchmark.fixture.BenchmarkFixture
    ) -> None:
        benchmark(PydanticSimpleListModel.model_validate_json, LIST_JSON)
