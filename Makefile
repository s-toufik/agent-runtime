venv:
	uv venv

install:
	uv sync

install_dev:
	uv sync --group dev

update_dependency:
ifdef PACKAGE
	uv lock --upgrade-package $(PACKAGE)
else
	uv lock --upgrade
endif
	uv sync

test:
	uv run pytest --disable-warnings

# --- evaluation: a running agent, driven by src/agent_evaluation/control_panel.json -----
#   make evaluate KINDS=SECURITY,MEMORY CASES='memory-*' RUNS=1 PAUSE=0 DRY_RUN=1
EVAL_PANEL ?= src/agent_evaluation/control_panel.json

evaluate:
	uv run python -m agent_evaluation --panel $(EVAL_PANEL) \
		$(if $(KINDS),--kinds $(KINDS)) \
		$(if $(CASES),--cases '$(CASES)') \
		$(if $(RUNS),--runs $(RUNS)) \
		$(if $(PAUSE),--pause $(PAUSE)) \
		$(if $(AGENT_URL),--agent-url $(AGENT_URL)) \
		$(if $(ENDPOINT),--endpoint $(ENDPOINT)) \
		$(if $(MODEL),--model $(MODEL)) \
		$(if $(OUTPUT_DIR),--output-dir $(OUTPUT_DIR)) \
		$(if $(DRY_RUN),--dry-run)

lint:
	uv run ruff check .

fix:
	uv run ruff check --fix .

format:
	uv run ruff format .

typecheck:
	uv run ty check

check:
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test

# --- run -------------------------------------------------------------------
run:
	uv run uvicorn bootstrap.application.agent_application:app --host 0.0.0.0 --port 8000

clean:
	rm -rf dist src/*.egg-info

build:
	rm -rf dist src/*.egg-info
	uv build

docker_build:
	docker build -f devops/docker/Dockerfile -t agent:local .
