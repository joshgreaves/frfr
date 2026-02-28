# frfr

[![CI](https://github.com/joshgreaves/frfr/actions/workflows/ci.yml/badge.svg)](https://github.com/joshgreaves/frfr/actions/workflows/ci.yml)

runtime type validation that's actually valid. no cap.

## what is this

frfr (for real for real) validates your data at runtime against Python types. you pass a type and some data, and it either gives you back a properly typed instance or tells you exactly why your data is cap.

```python
import frfr

data = {"name": "bestie", "age": 25}
user = frfr.validate(User, data)  # returns a User instance or throws
```

that's it. that's the whole api.

## install

```bash
pip install frfr
# or
uv add frfr
```

requires python 3.12+

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
frfr.validate(float, 1)              # 1.0 - int to float is lossless, we're chill
frfr.validate(tuple[str, ...], ["a", "b"])  # ("a", "b") - list to tuple, same energy
```

### it handles the hard stuff

```python
from dataclasses import dataclass
from typing import TypedDict

@dataclass
class User:
    name: str
    age: int

class UserDict(TypedDict):
    name: str
    age: int

# both work
frfr.validate(User, {"name": "bestie", "age": 25})      # returns User instance
frfr.validate(UserDict, {"name": "bestie", "age": 25})  # returns typed dict
```

### errors hit different

when validation fails, you get clear errors that tell you exactly what's wrong:

```
ValidationError: data.users[0].age - expected int, got str ("twenty five")
```

no cryptic stack traces. no guessing. just facts.

## supported types

- **primitives**: `str`, `int`, `float`, `bool`, `None`
- **containers**: `list[T]`, `dict[K, V]`, `tuple[T, ...]`, `set[T]`
- **typing**: `Optional[T]`, `Union[T1, T2]`, `Literal["a", "b"]`
- **structured**: `TypedDict`, `@dataclass`, `NamedTuple`
- **generics**: nested types like `list[dict[str, User]]`

## philosophy

1. **types mean what they say** - no sneaky coercion
2. **fail fast, fail clear** - know exactly what's wrong
3. **one function** - `validate()` does everything
4. **no magic** - explicit is better than implicit

## contributing

see [CONTRIBUTING.md](CONTRIBUTING.md). we'd love to have you.

## license

MIT
