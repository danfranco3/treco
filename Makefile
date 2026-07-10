.PHONY: dev backend-dev frontend-dev test lint migrate build-ui sync-backend build-package install-desktop

dev:
	docker compose up --build

backend-dev:
	cd backend && uvicorn app.main:app --reload --port 8001

frontend-dev:
	cd frontend && npm run dev

test:
	cd backend && pytest tests/ -v

lint:
	cd backend && ruff check . && mypy app/

migrate:
	cd backend && alembic upgrade head

install-desktop:
	@DESKTOP_DIR="$$HOME/.local/share/applications"; \
	mkdir -p "$$DESKTOP_DIR"; \
	REPO="$$(pwd)"; \
	sed "s|Exec=.*|Exec=bash -c \"$$REPO/launch.sh\"|" treco.desktop > "$$DESKTOP_DIR/treco.desktop"; \
	chmod +x "$$DESKTOP_DIR/treco.desktop"; \
	echo "Desktop shortcut installed. Look for Treco in your app launcher."

# Build pre-compiled static frontend (Next.js export mode)
build-ui:
	cd frontend && NEXT_OUTPUT=export npm run build
	rm -rf backend/sdk/python/treco/_ui
	cp -r frontend/out backend/sdk/python/treco/_ui
	@echo "UI built → backend/sdk/python/treco/_ui"

# Copy backend app into the pip package
sync-backend:
	rm -rf backend/sdk/python/treco/_backend
	cp -r backend/app backend/sdk/python/treco/_backend
	@echo "Backend synced → backend/sdk/python/treco/_backend"

# Build the pip-installable wheel (runs both above first)
build-package: build-ui sync-backend
	cd backend/sdk/python && python -m build
	@echo "Wheel built in backend/sdk/python/dist/"
