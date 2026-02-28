# Contributing to frfr

ayy welcome to the frfr codebase. here's how we keep things bussin.

## The vibe

frfr is a runtime type validation library. it does one thing and does it well - no bloat, no cap. when you call `frfr.validate(MyType, data)`, you either get back a valid instance or it throws. simple as.

## Dev setup

```bash
# clone it
git clone https://github.com/your-username/frfr.git
cd frfr

# install with dev deps
uv sync

# you're valid
```

## Code style

we follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html). here's the tldr:

### Imports hit different

```python
# slay
import os
import typing

# not it
from os import path
from typing import Optional, Union
```

import modules, not their contents. keeps things explicit and avoids namespace drama.

### Type checking is non-negotiable

we use `ty` and `pyright`. if it doesn't type check, it doesn't ship. no exceptions bestie.

```bash
uv run pyright
```

### Formatting

`ruff` handles this. don't even think about it.

```bash
uv run ruff format .
uv run ruff check --fix .
```

### Tests

tests live next to the code they test. no fixtures - we use helper functions because explicit is better than implicit (and fixtures are lowkey confusing).

```
src/frfr/validators.py
src/frfr/validators_test.py   # right here bestie
```

run tests with:

```bash
uv run pytest
```

## Adding a new type

when adding support for a new type, follow this order:

1. **Document it** - add to README and CLAUDE.md
2. **Test it** - write comprehensive tests first (tdd energy)
3. **Implement it** - make the tests pass
4. **Verify it** - run full test suite + type checks

## Design principles

### Strict by default

- types mean what they say
- `"1"` is not `1`, that's your json parser's job
- `True` is not `1`, even though python says otherwise
- we validate fr fr, not fr (kinda)

### Coercion rules

- lossless widening is valid (`int` → `float`)
- container types can coerce to equivalent types (`list` → `tuple[T, ...]`)
- everything else? nah

### Errors should slap

when validation fails, the error message should tell you exactly what went wrong and where. no cryptic nonsense.

## PR checklist

before you submit:

- [ ] tests pass (`uv run pytest`)
- [ ] types check (`uv run pyright`)
- [ ] code formatted (`uv run ruff format .`)
- [ ] lints pass (`uv run ruff check .`)
- [ ] you've actually tested your changes manually too

## Questions?

open an issue. we don't bite.

---

thanks for contributing. you're valid.
