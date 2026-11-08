# ForgeGuard developer tasks. Requires uv (https://docs.astral.sh/uv/) and Node 22+.
# Windows without make: run the commands under each target directly.

.PHONY: setup weights web test lint typecheck audit check up

setup: ## Install locked Python deps, fetch verified weights, build the web UI
	uv sync --frozen
	uv run python scripts/download_weights.py --allow-missing
	cd web && npm ci --no-audit --no-fund && npm run build

weights: ## Download and verify every weight file (fails if one has no URL)
	uv run python scripts/download_weights.py

web: ## Typecheck and build the web UI into frontend/static/app
	cd web && npm run build

test: ## Run the test suite (model tests skip when weights are missing)
	uv run pytest

lint: ## Ruff
	uv run ruff check .

typecheck: ## mypy (settings in pyproject.toml)
	uv run mypy api core

audit: ## Known-vulnerability scan of the locked environment and the web UI
	uv run --with pip-audit pip-audit
	cd web && npm audit --audit-level=high

check: lint typecheck test ## What CI's blocking Python jobs run

up: ## Production-like stack (needs .env with DJANGO_SECRET_KEY)
	docker compose up --build
