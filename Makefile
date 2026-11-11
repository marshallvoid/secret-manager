.DEFAULT_GOAL := help
.PHONY: help install hooks run test lint check format build clean
UV_RUN := uv run --no-env-file --locked --group build --group dev

help: ## Show available commands
	@echo "make install  Install app and build dependencies"
	@echo "make run      Open the app"
	@echo "make test     Run tests with synthetic data"
	@echo "make lint     Check Ruff, formatting, mypy and Pyright"
	@echo "make check    Run lint and tests"
	@echo "make format   Fix Ruff issues and format Python files"
	@echo "make hooks    Install pre-commit hooks"
	@echo "make build    Build a portable executable or macOS disk image for this OS and architecture"
	@echo "make clean    Remove generated portable builds"

install: ## Install app and build dependencies
	uv sync --locked --group build --group dev

hooks: install ## Install pre-commit hooks
	$(UV_RUN) pre-commit install

run: ## Open the app
	$(UV_RUN) secret-manager

test: ## Run tests
	$(UV_RUN) python -m unittest discover -s tests -v

lint: ## Check style, formatting and types
	$(UV_RUN) ruff check .
	$(UV_RUN) ruff format --check .
	$(UV_RUN) mypy
	$(UV_RUN) pyright

check: lint test ## Run all checks

format: ## Fix lint issues and format the code
	$(UV_RUN) ruff check --fix .
	$(UV_RUN) ruff format .

build: ## Build a portable executable or macOS disk image
	$(UV_RUN) python scripts/build.py

clean: ## Remove generated portable builds
	$(UV_RUN) python scripts/build.py --clean
