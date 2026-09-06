.PHONY: backend frontend train test seed

backend:
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

train:
	python -m ml.training.train

seed:
	python database/seed.py

test:
	pytest
