.PHONY: up down logs test test-all lint fmt demo health init-bucket

# Override on the CLI: make demo SOURCE_URI=s3://pdf-preprocessing/incoming/doc.pdf
SOURCE_URI ?= s3://pdf-preprocessing/incoming/example.pdf

up:                ## Start Redis, SeaweedFS, and the worker
	docker compose up --build -d
	docker compose --profile init run --rm bucket-init
	@echo "Worker health on http://localhost:8000/health"
	@echo "SeaweedFS S3 on http://localhost:8333"

init-bucket:       ## Create the local pdf-preprocessing bucket if needed
	docker compose --profile init run --rm bucket-init

down:
	docker compose down

logs:
	docker compose logs -f worker

health:
	@curl -s -i http://localhost:8000/health

test:              ## Unit tests only — no Docker required
	poetry run pytest -m "not integration" --junitxml=reports/junit.xml --cov=. --cov-report=xml:reports/coverage.xml --cov-report=html:reports/htmlcov

test-all:          ## Everything, including testcontainers
	poetry run pytest --junitxml=reports/junit.xml --cov=. --cov-report=xml:reports/coverage.xml --cov-report=html:reports/htmlcov

lint:
	poetry run ruff check .

fmt:
	poetry run black . && poetry run ruff check --fix .

demo:              ## Publish one request twice; watch it process exactly once
	@echo "--- publishing PdfPreprocessingRequested x2 (same job-id)"
	@docker compose exec worker python -m cli publish --job-id demo-1 --source-uri "$(SOURCE_URI)" --count 2
	@echo "--- waiting for the worker..."
	@sleep 5
	@echo "--- dedup state in Redis"
	@docker compose exec redis redis-cli -a redis --no-auth-warning -n 1 HGETALL preprocessing:demo-1
	@echo "--- PdfPreprocessingCompleted on the output stream"
	@docker compose exec redis redis-cli -a redis --no-auth-warning -n 1 XRANGE pdf.preprocessing.completed - +
	@echo "--- worker log (one processed, one already-processed)"
	@docker compose logs --tail=30 worker
