CRS Transformation Platform (PyProj + FastAPI + React)

Overview
- Cloud-ready CRS transformation platform for directional drilling and anti-collision calculations.
- Backend: FastAPI + PyProj (PROJ 9.x), Redis cache.
- Frontend: React demo UI.
- Single-command Docker deployment with `docker-compose up --build`.

Quick Start
- Requirements: Docker + Docker Compose, network access for container builds.
- Run: `docker-compose up --build`
- Backend: http://localhost:3001 (FastAPI/OpenAPI at `/docs`)
- Frontend: http://localhost:3000

Environment
- PROJ network grids are enabled with `PROJ_NETWORK=ON`.
- Redis is available at hostname `redis:6379` inside the compose network.

Development Notes
- Hot reload is enabled via bind mounts for both backend and frontend.
- Python dependencies in `backend/requirements.txt`.
- Node dependencies from `frontend/package.json`.

Testing
- Basic pytest in `backend/tests/test_transformations.py`.
- Run inside backend container: `pytest -q`.

