from fastapi import FastAPI

from app.api.routes import data, health, stats

app = FastAPI(title="Crypto ETL Backend")

app.include_router(data.router)
app.include_router(health.router)
app.include_router(stats.router)
