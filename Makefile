.PHONY: test test-all test-cov test-unit test-integration

## Run fast unit tests only (default)
test: test-unit

## Run only unit tests
test-unit:
	python -m pytest tests/unit/ --tb=short -q

## Run only integration tests
test-integration:
	python -m pytest tests/integration/ --tb=short -q

## Run all tests (unit + integration)
test-all:
	python -m pytest tests/ -m "" --tb=short -q

## Run all tests with coverage report
test-cov:
	python -m pytest tests/ -m "" --cov=src --cov-report=term-missing --tb=short

## Install pre-commit hook
install-hooks:
	pre-commit install

## Install project dependencies
install:
	pip install -r requirements.txt
