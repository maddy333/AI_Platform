# Developer entrypoints. CI runs the same commands (see .github/workflows/ci.yml).

.PHONY: install lint format typecheck test coverage run clean check

install:
	uv sync --all-groups

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

format:
	uv run ruff check --fix src tests
	uv run ruff format src tests

typecheck:
	uv run mypy

test:
	uv run pytest

coverage:
	uv run pytest --cov --cov-report=term-missing --cov-report=xml

run:
	uv run aiplatform

check: lint typecheck coverage

clean:
	rm -rf .mypy_cache .ruff_cache .pytest_cache .coverage coverage.xml htmlcov dist build
