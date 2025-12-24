from app.api.routes.data import router as data_router
from app.api.routes.etl import router as etl_router
from app.api.routes.health import router as health_router
from app.api.routes.stats import router as stats_router

__all__ = ["data_router", "etl_router", "health_router", "stats_router"]
