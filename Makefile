# `make lint` and `make test` are the contract called by epam/ai-dial-ci.
# Everything else is developer convenience.

PORT ?= 5000
IMAGE_NAME ?= ai-dial-model-adapter
PLATFORM ?= linux/amd64
VENV_DIR ?= .venv
POETRY ?= poetry
ARGS ?=

# fastapi >= 0.136 refuses pydantic.v1 response models and aidial-sdk only
# exposes v2 models when this is set. Mandatory, not a preference.
PYDANTIC_V2 ?= 1

# One arithmetic question per model. bedrock and vertexai call that test
# `test_2_plus_3`, openai has a `simple math` case in its table-driven chat
# suite whose id is `simple_math`, and neither name matches the other's suite,
# so one expression serves all three.
SMOKE ?= -k 'test_2_plus_3 or simple_math'

.PHONY: all install lint format test integration_tests integration_tests_smoke \
	serve docker install_git_hooks help

-include .env.dev
export

all: lint test

install:
	$(POETRY) install

lint: install
	$(POETRY) run ruff check .
	$(POETRY) run ruff format --check .
	$(POETRY) run pyright aidial_model_provider tests

format: install
	$(POETRY) run ruff check --fix .
	$(POETRY) run ruff format .

test: install
	$(POETRY) run pytest tests/unit_tests $(ARGS)

integration_tests: install
	$(POETRY) run pytest tests/integration_tests $(ARGS)

integration_tests_smoke: install
	$(POETRY) run pytest tests/integration_tests $(SMOKE) $(ARGS)

serve: install
	$(POETRY) run uvicorn aidial_model_provider.app:app \
		--reload --host "0.0.0.0" --port $(PORT) --workers=1 --env-file ./.env

docker:
	docker build --platform $(PLATFORM) -t $(IMAGE_NAME):dev .
	docker run --platform $(PLATFORM) --env-file ./.env --rm -p $(PORT):5000 $(IMAGE_NAME):dev

install_git_hooks: install
	$(VENV_DIR)/bin/pre-commit install

help:
	@echo 'install                      - install dependencies'
	@echo 'install_git_hooks            - install the git hooks'
	@echo '-- LINTING --'
	@echo 'format                       - run code formatters'
	@echo 'lint                         - run linters'
	@echo '-- RUN --'
	@echo 'serve                        - run the dev server locally'
	@echo 'docker                       - build and run the image'
	@echo '-- TESTS --'
	@echo 'test                         - run all unit tests (ARGS=... passed to pytest)'
	@echo 'integration_tests            - run all integration tests (live providers)'
	@echo 'integration_tests_smoke      - one 2+3 question per model'
