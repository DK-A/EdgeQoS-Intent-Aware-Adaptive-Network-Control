# EdgeQoS Makefile - Tata Elxsi TELIPORT S4 (Problem Statement 3)
CC ?= gcc
PYTHON ?= python3

all: reader verify

reader:
	$(MAKE) -C reader

verify: reader
	@echo "=========================================="
	@echo "Running EdgeQoS Verification & Test Suite"
	@echo "=========================================="
	PYTHONPATH=. $(PYTHON) tests/test_privacy.py
	PYTHONPATH=. $(PYTHON) tests/test_classifier.py
	PYTHONPATH=. $(PYTHON) tests/test_guard_capacity.py
	PYTHONPATH=. $(PYTHON) sim/benchmark.py
	PYTHONPATH=. $(PYTHON) analysis/plots.py
	@echo "=========================================="
	@echo "All EdgeQoS verification suites PASSED!"
	@echo "=========================================="

train:
	PYTHONPATH=. $(PYTHON) ml/train.py

bench:
	PYTHONPATH=. $(PYTHON) sim/benchmark.py

plots:
	PYTHONPATH=. $(PYTHON) analysis/plots.py

clean:
	$(MAKE) -C reader clean
	rm -rf __pycache__ */__pycache__ */*/__pycache__

.PHONY: all reader verify train bench plots clean
