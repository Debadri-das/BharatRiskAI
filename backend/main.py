from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import dashboard, emergencies, health, recommendations, reports, satellite, simulation, zones
from backend.config.settings import get_settings
from backend.database.connection import Base, SessionLocal, engine
from backend.database.seed_data import seed_demo
from backend.middleware.rate_limit import RateLimitMiddleware
from backend.middleware.request_id import RequestIdMiddleware
from starlette.middleware.gzip import GZipMiddleware


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RequestIdMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()


for router in [health.router, dashboard.router, zones.router, simulation.router, reports.router, emergencies.router, recommendations.router, satellite.router]:
    app.include_router(router, prefix="/api")
