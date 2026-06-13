.PHONY: up down logs test smoke test-worker

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

test: test-worker

test-worker:
	docker compose run --rm worker pytest -q

smoke:
	curl -X POST http://localhost:8080/analyze \
		-H "Content-Type: application/json" \
		--data @examples/local_job.json
