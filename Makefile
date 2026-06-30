# auth_ecnu — convenience targets. Real install logic lives in
# scripts/setup.sh; this just wraps the common workflows.

PYTHON ?= python3
VENV   ?= .venv

.PHONY: help install uninstall purge status dev test lint build clean version

help:
	@echo "auth_ecnu make targets"
	@echo "  make install     Run interactive installer (scripts/setup.sh install)"
	@echo "  make uninstall   Run interactive uninstaller"
	@echo "  make purge       Uninstall and remove config + state file"
	@echo "  make status      Show current install info"
	@echo "  make dev         pip install -e . into the current environment"
	@echo "  make test        Run offline unit tests"
	@echo "  make lint        Byte-compile the package"
	@echo "  make build       Build sdist/wheel into dist/"
	@echo "  make clean       Remove build artefacts and __pycache__"
	@echo "  make version     Print the package version"

install:
	./scripts/setup.sh install

uninstall:
	./scripts/setup.sh uninstall

purge:
	./scripts/setup.sh uninstall --purge

status:
	./scripts/setup.sh status

dev:
	$(PYTHON) -m pip install -e .

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
