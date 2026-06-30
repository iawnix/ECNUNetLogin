# auth_ecnu — convenience targets. All real work lives in scripts/ and
# pyproject.toml; this is just a thin entry point so common workflows are
# `make install`, `make test`, `make uninstall`.

PYTHON ?= python3
VENV   ?= .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python

.PHONY: help install dev uninstall purge test lint build clean version

help:
	@echo "auth_ecnu make targets"
	@echo "  make install     Create $(VENV) and install auth_ecnu (editable)"
	@echo "  make dev         Install editable into the *current* environment"
	@echo "  make test        Run the offline unit tests"
	@echo "  make lint        Byte-compile the package to catch syntax errors"
	@echo "  make build       Build sdist/wheel into dist/"
	@echo "  make uninstall   Remove $(VENV)"
	@echo "  make purge       Remove $(VENV) and ~/.auth-setting"
	@echo "  make clean       Remove build artifacts and __pycache__"
	@echo "  make version     Print the installed version"

install:
	./scripts/install.sh

dev:
	$(PYTHON) -m pip install -e .

uninstall:
	./scripts/uninstall.sh

purge:
	./scripts/uninstall.sh --purge

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m compileall -q src tests

build:
	$(PYTHON) -m pip install --quiet --upgrade build
	$(PYTHON) -m build

version:
	@PYTHONPATH=src $(PYTHON) -c "import auth_ecnu; print(auth_ecnu.__version__)"

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
