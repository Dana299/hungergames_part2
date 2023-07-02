build:
	docker compose -f docker-compose.yaml build

up:
	docker compose -f docker-compose.yaml up -d

down:
	docker compose -f docker-compose.yaml down && docker network prune --force