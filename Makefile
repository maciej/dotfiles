.SUFFIXES:

.DEFAULT_GOAL := test

KNOWN_TARGETS := lint test test-python
UNKNOWN_TARGETS := $(filter-out $(KNOWN_TARGETS),$(MAKECMDGOALS))

ifneq ($(UNKNOWN_TARGETS),)
$(error Unknown target(s): $(UNKNOWN_TARGETS))
endif

.PHONY: $(KNOWN_TARGETS)

test: test-python
	./scripts/test-install

test-python:
	cd toolbox && uv run --group dev pytest

lint:
	cd toolbox && uv run --group dev ruff check
