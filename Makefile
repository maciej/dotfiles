.SUFFIXES:

.DEFAULT_GOAL := test

KNOWN_TARGETS := test
UNKNOWN_TARGETS := $(filter-out $(KNOWN_TARGETS),$(MAKECMDGOALS))

ifneq ($(UNKNOWN_TARGETS),)
$(error Unknown target(s): $(UNKNOWN_TARGETS))
endif

.PHONY: $(KNOWN_TARGETS)

test:
	./scripts/test-install
