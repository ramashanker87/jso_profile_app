.PHONY: setup dev backend mock-neeto test build deploy
setup:
	python3 -m venv .venv
	.venv/bin/pip install -r backend/requirements-dev.txt
	cd frontend && npm ci
	@test -f frontend/.env.local || cp frontend/.env.example frontend/.env.local
dev:
	cd frontend && npm run dev
backend:
	.venv/bin/python backend/local.py
mock-neeto:
	.venv/bin/python backend/mock_neeto.py
test:
	.venv/bin/python -m pytest -c backend/pytest.ini backend/tests -q
	cd frontend && npm test
build:
	./scripts/build-backend.sh
	cd frontend && npm run build
deploy:
	./scripts/deploy.sh
