# Contributing to frfr

welcome to frfr. this doc covers how we keep the project small, strict, and maintainable.

## The vibe

frfr is a runtime type validation library. it does one thing well: validate data against Python types with clear behavior and clear errors.

when you call `frfr.validate(MyType, data)`, you either get a valid typed value or a `ValidationError`. no mystery mode.

## Dev setup

```bash
# clone it
git clone https://github.com/your-username/frfr.git
cd frfr

# install with dev deps
uv sync

# you're ready
```

## Code style

we follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html). quick summary:

### Imports

```python
# good
import os
import collections
from typing import Any, Union, Optional

# avoid
from os import path
from collections import OrderedDict
```

import modules, not their contents — except for `typing`, where `from typing import ...` is preferred. keeps things explicit and avoids namespace drama.

### Type checking is non-negotiable

we use both `ty` and `pyright`. if it doesn't type check, it doesn't ship.

```bash
uv run ty check
uv run pyright
```

### Formatting

`ruff` handles formatting and linting.

```bash
uv run ruff format .
uv run ruff check --fix .
```

### Tests

tests live next to the code they test. NO fixtures — use explicit helper functions for setup.

```text
src/frfr/validation.py
src/frfr/validation_test.py   # alongside source
```

run tests with:

```bash
uv run pytest
```

## Adding a new type

when adding support for a new type, follow this order:

1. **Document it** - add to README and CLAUDE.md
2. **Test it** - add comprehensive tests first when practical
3. **Implement it** - make the tests pass
4. **Verify it** - run full CI locally (`make ci`)

## Design principles

### Strict by default

- types mean what they say
- `"1"` is not `1`, that's your json parser's job
- `True` is not `1`, even though python says otherwise
- we optimize for predictable behavior over "helpful" coercion

### Coercion rules

coercion changes the container, not the meaning. we accept:

- lossless widening (`int` → `float`)
- structurally equivalent containers (`list` ↔ `tuple` — same elements, different wrapper)
- mapping types → `dict` (`OrderedDict`, `MappingProxyType`, etc.)

we reject:

- parsing operations (`"1"` → `int` — that's your deserializer's job)
- lossy conversions (`list` → `set` — duplicates would disappear silently)

### Errors should be clear

when validation fails, the error should tell you exactly what went wrong and where. no cryptic output.

## PR checklist

before you submit:

- [ ] tests pass (`uv run pytest`)
- [ ] types check (`uv run ty check`)
- [ ] types check (`uv run pyright`)
- [ ] code formatted (`uv run ruff format .`)
- [ ] lints pass (`uv run ruff check .`)
- [ ] you've actually tested your changes manually too

## Questions?

open an issue. we don't bite.
