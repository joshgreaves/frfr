# frfr

[![CI](https://github.com/joshgreaves/frfr/actions/workflows/ci.yml/badge.svg)](https://github.com/joshgreaves/frfr/actions/workflows/ci.yml)

lightweight runtime validation. actually valid. for real.

## what is this

frfr (for real for real) validates your data at runtime against Python types. you pass a type and some data, and it either gives you back a properly typed instance or tells you exactly why your data is cap.

```python
import dataclasses

import frfr

@dataclasses.dataclass
class User:
    name: str
    age: int

data = {"name": "bestie", "age": 27}
user = frfr.validate(User, data)  # returns a User instance or throws
```

that's it. that's the whole api.

## install

```bash
uv add frfr
# or
pip install frfr
```

requires python 3.12+

## quickstart

```python
import dataclasses
import uuid
from typing import TypedDict

import frfr

@dataclasses.dataclass
class User:
    id: uuid.UUID
    name: str
    age: int

class UserPayload(TypedDict):
    id: uuid.UUID
    name: str
    age: int

payload = {
    "id": "12345678-1234-5678-1234-567812345678",
    "name": "bestie",
    "age": 27,
}

as_dataclass = frfr.validate(User, payload)        # User(...)
as_typed_dict = frfr.validate(UserPayload, payload)  # dict with validated values
```

## why frfr?

### it's strict

other validation libs play fast and loose with types. frfr doesn't.

```python
frfr.validate(int, "1")    # ValidationError - "1" is a string, not an int
frfr.validate(int, True)   # ValidationError - bool is not int, even in python
frfr.validate(int, 1.0)    # ValidationError - float is not int, even if it's 1.0
```

if you want string-to-int coercion, let your json parser handle it. frfr validates types, fr fr.

### it coerces when it makes sense

```python
frfr.validate(float, 7)              # 7.0 - int to float is lossless
frfr.validate(tuple[str, ...], ["a", "b"])  # ("a", "b") - list to tuple
```

### it handles the hard stuff

```python
import dataclasses
from typing import TypedDict

@dataclasses.dataclass
class User:
    name: str
    age: int

class UserDict(TypedDict):
    name: str
    age: int

# both work
frfr.validate(User, {"name": "bestie", "age": 27})      # returns User instance
frfr.validate(UserDict, {"name": "bestie", "age": 27})  # returns typed dict
```

### clear errors

when validation fails, you get clear errors that tell you exactly what's wrong:

```
ValidationError: .users[0].age - expected int, got str ('twenty five')
```

no cryptic stack traces. no guessing. just facts.

## supported types

- **scalars**: `Any`, `str`, `int`, `float`, `bool`, `None`, `bytes`
- **stdlib value types**: `decimal.Decimal`, `datetime.datetime`, `datetime.date`, `datetime.time`, `datetime.timedelta`, `uuid.UUID`, `pathlib.Path`
- **containers**: `list[T]`, `dict[K, V]`, `tuple[T, ...]`, `tuple[T1, T2, ...]`, `set[T]`, `frozenset[T]`
- **abstract collections**: `collections.abc.Sequence[T]`, `collections.abc.Mapping[K, V]`
- **typing constructs**: `Optional[T]`, `Union[T1, T2]` / `T1 | T2`, `Literal[...]`, `Annotated[T, ...]` (transparent), `NewType(...)`, `Final[T]`
- **structured types**: `TypedDict`, `@dataclass`, `NamedTuple`
- **nested generics**: compositions like `dict[str, list[tuple[int, str | None]]]`

frfr enforces strict structure by default:
- extra keys in `TypedDict`, `dataclass`, and `NamedTuple` inputs are rejected
- required keys/fields must be present
- mutable containers return new objects (so validated output can't mutate original input by accident)

## philosophy

1. **types mean what they say** - no sneaky coercion
2. **fail fast, fail clear** - know exactly what's wrong
3. **zero dependencies** - stdlib-only runtime dependency footprint
4. **your types, not ours** - validate into existing dataclasses, TypedDicts, NamedTuples, and stdlib types
5. **one primary entry point** - `validate()` for most usage, `Validator` when you need customization

## extending frfr

need custom validation? create your own `Validator` instance and register handlers.

```python
import frfr

# create a custom validator (comes with built-in handlers)
my_validator = frfr.Validator()

# register a handler for your type
class UserId:
    def __init__(self, value: int) -> None:
        self.value = value

def parse_user_id(
    validator: frfr.Validator, target: type[UserId], data: object, path: str
) -> UserId:
    if isinstance(data, int) and data > 0:
        return UserId(data)
    raise frfr.ValidationError(target, data, path=path)

my_validator.register_type_handler(UserId, parse_user_id)
my_validator.validate(UserId, 42)  # UserId(value=42)
```

### advanced handler api: `_validate_at`

for custom handlers that validate nested structures, use `validator._validate_at(...)` so nested errors keep correct paths.

```python
# inside a custom handler:
validated_item = validator._validate_at(UserId, data["user_id"], f"{path}.user_id")
```

`_validate_at` has a leading underscore, but in custom handler composition it's the intended path-aware tool.

### override built-in behavior

want different coercion rules? register your own handler for that exact type.

```python
import frfr

my_validator = frfr.Validator()

# allow float -> int coercion (frfr is strict by default)
def lenient_int(
    validator: frfr.Validator, target: type[int], data: object, path: str
) -> int:
    if isinstance(data, float) and data.is_integer():
        return int(data)
    if type(data) is int:
        return data
    raise frfr.ValidationError(target, data, path=path)

my_validator.register_type_handler(int, lenient_int)
my_validator.validate(int, 1.0)  # 1
```

the default `frfr.validate()` stays untouched - your custom validator is isolated.

## current scope

frfr is focused on strict structural validation and clear errors. it does **not** currently do:
- collect-all-errors mode (it fails fast on first validation error)
- field aliasing / key renaming
- field-level constraints like min/max/pattern

## frfr vs pydantic

use **frfr** when:
- you want zero runtime dependencies
- you need strict, predictable type semantics (minimal coercion)
- you're validating into existing stdlib/python typing shapes (`dataclass`, `TypedDict`, `NamedTuple`, enums, stdlib value types)
- you care about a small, auditable codebase and simple mental model

use **pydantic** when:
- you need rich field constraints and validators
- you need collect-all-errors behavior for user-facing forms/config APIs
- you need aliasing/model config and broader framework ecosystem integration (for example FastAPI/OpenAPI-heavy flows)
- you want built-in higher-level model features beyond structural validation

## contributing

see [CONTRIBUTING.md](CONTRIBUTING.md). we'd love to have you.

## license

MIT
