.PHONY: format lint typecheck test ci bench bench-save bench-compare

format:
	uv run ruff format .

lint:
	uv run ruff check --fix .

typecheck:
	uv run pyright

test:
	uv run pytest

ci: format lint typecheck test

bench:
	uv run pytest benchmarks/ --benchmark-only -v

bench-save:
	uv run pytest benchmarks/ --benchmark-only --benchmark-autosave

bench-compare:
	uv run pytest benchmarks/ --benchmark-only --benchmark-compare
