# Deployment

Local development:

```bash
python database/seed.py
uvicorn backend.main:app --reload --port 8000
cd frontend
npm install
npm run dev
```

Docker:

```bash
docker compose up --build
```

The app uses `.env.example` defaults and does not require paid API keys for demo mode.
