# PatchR — Root Makefile
# Orchestrates backend (FastAPI) and frontend (Next.js) independently.
#
# Usage:
#   make install   — install all dependencies
#   make dev       — start backend + frontend concurrently
#   make api       — start backend only  (port 8000)
#   make web       — start frontend only (port 3000)
#   make db        — run database migrations
#   make lint      — lint backend (ruff) + frontend (eslint)
#   make clean     — remove build artifacts

.PHONY: install dev api web db lint clean

# ── Install ────────────────────────────────────────────────────────────────────
install:
	@echo "[backend]  installing Python dependencies..."
	cd backend && pip install -e ".[dev]"
	@echo "[frontend] installing Node dependencies..."
	cd frontend && npm install
	@echo "Done. Run 'make dev' to start both services."

# ── Dev (both services) ────────────────────────────────────────────────────────
dev:
	@echo "Starting backend on :8000 and frontend on :3000..."
	@start "PatchR-API" cmd /k "cd backend && uvicorn patchr.main:app --reload --port 8000"
	@start "PatchR-Web" cmd /k "cd frontend && npm run dev"
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"

# ── Backend only ───────────────────────────────────────────────────────────────
api:
	@echo "Starting PatchR backend on http://localhost:8000 ..."
	cd backend && uvicorn patchr.main:app --reload --port 8000

# ── Frontend only ──────────────────────────────────────────────────────────────
web:
	@echo "Starting PatchR frontend on http://localhost:3000 ..."
	cd frontend && npm run dev

# ── Database migrations ────────────────────────────────────────────────────────
db:
	@echo "Running Alembic migrations..."
	cd backend && alembic upgrade head

# ── Lint ───────────────────────────────────────────────────────────────────────
lint:
	@echo "[backend]  running ruff..."
	cd backend && ruff check patchr/
	@echo "[frontend] running eslint..."
	cd frontend && npm run lint

# ── Clean ──────────────────────────────────────────────────────────────────────
clean:
	@echo "Cleaning build artifacts..."
	cd frontend && rm -rf .next
	find backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean done."
