# ═══════════════════════════════════════════════════════════════
# PriceRadar v2 — Makefile
# ═══════════════════════════════════════════════════════════════

.PHONY: up down build logs restart \
        k8s-apply k8s-delete k8s-status \
        scale-amazon scale-gateway \
        lint health test

# ── Docker Compose ──────────────────────────────────────────
up:
	docker-compose up --build -d

down:
	docker-compose down

build:
	docker-compose build

logs:
	docker-compose logs -f --tail=100

restart:
	docker-compose restart

# ── Kubernetes ──────────────────────────────────────────────
k8s-apply:
	kubectl apply -f k8s/

k8s-delete:
	kubectl delete -f k8s/

k8s-status:
	kubectl get pods,svc,hpa -l app=priceradar

# ── Scaling shortcuts ──────────────────────────────────────
scale-amazon:
	kubectl scale deployment scraper-amazon --replicas=5

scale-gateway:
	kubectl scale deployment api-gateway --replicas=4

# ── Development ────────────────────────────────────────────
lint:
	@echo "Running ruff on all Python services..."
	find services -name "*.py" | xargs ruff check --fix

health:
	@echo "Checking gateway health..."
	curl -s http://localhost:8000/health | python3 -m json.tool
	@echo "\nChecking platform statuses..."
	curl -s http://localhost:8000/platforms | python3 -m json.tool

test:
	@echo "Running integration health check..."
	docker-compose up -d
	sleep 10
	curl -sf http://localhost:8000/health || (echo "FAIL: gateway unhealthy" && exit 1)
	curl -sf http://localhost:3000/health || (echo "FAIL: frontend unhealthy" && exit 1)
	@echo "\nAll health checks passed!"
