.PHONY: up down logs test-worker

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

test-worker:
	docker compose run --rm worker pytest -q
