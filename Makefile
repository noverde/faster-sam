# project settings
PROJECT_PATH := faster_sam

# venv settings
export VIRTUALENV := $(PWD)/.venv
export PATH       := $(VIRTUALENV)/bin:$(PATH)

# fix make < 3.81 (macOS and old Linux distros)
ifeq ($(filter undefine,$(value .FEATURES)),)
SHELL = env PATH="$(PATH)" /bin/bash
endif

.PHONY: .venv docs

build:
	python -m build

.venv:
	python -m venv $(VIRTUALENV)
	pip install --upgrade pip

clean:
	rm -rf .pytest_cache .coverage dist .mypy_cache *.egg-info
	find $(PROJECT_PATH) -name __pycache__ | xargs rm -rf
	find tests -name __pycache__ | xargs rm -rf

install-hook:
	echo "make lint" > .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit

install-dev: .venv install-hook
	if [ -f requirements-dev.txt ]; then pip install -r requirements-dev.txt; fi

lint:
	black --line-length=100 --target-version=py312 --check .
	flake8 --max-line-length=100 --exclude .venv

format:
	black --line-length=100 --target-version=py312 .

test:
	coverage run --source=$(PROJECT_PATH) -m unittest

coverage: test .coverage
	coverage report -m --fail-under=90

check:
	twine check dist/*

docs:
	sphinx-apidoc -feMT -o docs/ faster_sam
	sphinx-build -M html docs/ docs/_build
