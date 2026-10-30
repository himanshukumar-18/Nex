.PHONY: help lint format format-check typecheck test check

help:
	@echo "NEX development commands"
	@echo "  make lint         Check Python code quality"
	@echo "  make format       Format Python code"
	@echo "  make format-check Check formatting without changing files"
	@echo "  make typecheck    Run static type checks"
	@echo "  make test         Run automated tests"
	@echo "  make check        Run all quality checks"

lint:
	ruff check .

format:
	ruff format .

format-check:
	ruff format --check .

typecheck:
	mypy apps cli tests

test:
	pytest

check: lint format-check typecheck test
