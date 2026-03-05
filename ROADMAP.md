# roadmap

## v0.1.0 — primitive type coverage

Expand supported types so frfr works on real-world schemas without gaps. Targeted for initial PyPI release.

### enums
- `Enum`, `IntEnum`, `StrEnum`, `Flag`

### stdlib types
- `datetime.datetime`, `datetime.date`, `datetime.time`, `datetime.timedelta`
- `uuid.UUID`
- `pathlib.Path`
- `decimal.Decimal`
- `bytes`

### abstract collection types
- `Sequence[T]` — accepts list or tuple
- `Mapping[K, V]` — abstract mapping input

### typing constructs
- `typing.Final[T]` — treat as `T`

---

## v0.2.0 — features

### collect all errors
`frfr.validate` will collect all validation errors in a payload instead of failing on the first. Raises a `ValidationErrors` (plural) exception containing every error found. Useful for user-facing validation (forms, config files, API request bodies) where you need to report everything at once.

Minor version bump because this changes the error-reporting behavior of the public API.

### extra field policy
Currently frfr always raises on extra fields. Add support for an `ignore` policy — silently drop unknown keys — which is important for forward compatibility (new API fields shouldn't break old clients). Configurable on the `Validator` instance, with a per-type override via `Annotated`.

### alias support
Map between API field names (camelCase, kebab-case) and Python field names (snake_case):
- **Global strategy** on the `Validator` instance — zero annotation, zero changes to existing types. Covers the common case where an entire API follows one convention.
- **Per-field alias** via `Annotated[str, frfr.Alias("firstName")]` — for when field names don't follow a simple pattern.

### custom compiled handlers
Expose `CompileFunc` registration so users can add their own pre-compiled handlers (`register_type_compiler`, `register_predicate_compiler`). Currently only the slower `Handler`-based registration is available; compiled handlers avoid per-call type introspection for maximum performance on custom types.

### `__frfr_validate__` protocol
Let types declare their own validation logic as a classmethod:

```python
import frfr

class MyType:
    @classmethod
    def __frfr_validate__(cls, data: object) -> "MyType":
        ...
```

More ergonomic than registering a handler on a `Validator` instance, especially for library authors who can't change how their users instantiate validators.

---

## under consideration

### field-level constraints via `Annotated`
Lightweight constraint markers checked post-type-validation:

```python
import frfr
from typing import Annotated

age: Annotated[int, frfr.Gt(0), frfr.Lt(150)]
slug: Annotated[str, frfr.MinLen(1), frfr.Pattern(r'^[a-z0-9-]+$')]
```

Purely additive — types without constraints behave identically to today. Initial set: `Gt`, `Lt`, `Ge`, `Le`, `MinLen`, `MaxLen`, `Pattern`. Cross-field validation and computed fields are explicitly out of scope.

The tension: keeps frfr minimal (structural type validation only) vs. giving users a clean built-in pattern instead of pushing them toward custom handlers for basic value checks.

### transforms via `Annotated`
Post-validation normalisation, e.g. `Annotated[str, frfr.Transform(str.strip)]`. Natural companion to constraints; would only make sense to add if constraints land.

### generic class support
`class Box(Generic[T])` with `Box[int]`. Common in Python but requires meaningful extra complexity to implement correctly.

### `attrs` support
Validate into `attrs` classes alongside the existing dataclass support.

