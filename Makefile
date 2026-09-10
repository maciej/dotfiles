.SUFFIXES:

.DEFAULT_GOAL := test

KNOWN_TARGETS := lint test test-python
UNKNOWN_TARGETS := $(filter-out $(KNOWN_TARGETS),$(MAKECMDGOALS))

ifneq ($(UNKNOWN_TARGETS),)
$(error Unknown target(s): $(UNKNOWN_TARGETS))
endif

# Pin the root-level ruff so the lint gate uses a reproducible rule set.
# Bump deliberately and fix any new findings in the same change.
RUFF_VERSION ?= 0.16.6

.PHONY: $(KNOWN_TARGETS)

test: test-python
	uv run --with pytest pytest -q tests

test-python:
	cd toolbox && uv run --group dev pytest

lint:
	cd toolbox && uv run --group dev ruff check
	uv run --with ruff==$(RUFF_VERSION) ruff check --no-cache src tests
