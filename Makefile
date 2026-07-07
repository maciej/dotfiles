.SUFFIXES:

.DEFAULT_GOAL := test

KNOWN_TARGETS := lint test test-python
UNKNOWN_TARGETS := $(filter-out $(KNOWN_TARGETS),$(MAKECMDGOALS))

ifneq ($(UNKNOWN_TARGETS),)
$(error Unknown target(s): $(UNKNOWN_TARGETS))
endif

.PHONY: $(KNOWN_TARGETS)

test: test-python
	uv run --with pytest pytest -q tests

test-python:
	cd toolbox && uv run --group dev pytest

lint:
	cd toolbox && uv run --group dev ruff check
	uv run --with ruff ruff check --no-cache src tests
