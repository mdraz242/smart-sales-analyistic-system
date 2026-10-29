from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.database import init_db, SessionLocal
from backend.app.models.order import Order
from backend.app.services.sample_data_generator import generate_sample_dataset
from backend.app.api.routers import (
    analytics_router, sync_router, imports_router, reports_router
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema
    init_db()
    # Check if DB has orders; if not, seed realistic sample dataset automatically
    db = SessionLocal()
    try:
        order_count = db.query(Order).count()
        if order_count == 0:
            print("Database empty: Auto-seeding comprehensive realistic B2C dataset...")
            generate_sample_dataset(db, seed=42)
            print("Sample dataset seeded successfully.")
    except Exception as e:
        print(f"Notice on seed check: {e}")
    finally:
        db.close()
    yield


app = FastAPI(
    title="WooCommerce B2C Sales Intelligence & Analytics Platform",
    description="Production-grade business intelligence and analytics engine for WooCommerce B2C stores.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration for future React/Vue/Next.js frontend migration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(analytics_router)
app.include_router(sync_router)
app.include_router(imports_router)
app.include_router(reports_router)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app_env": settings.APP_ENV,
        "database": "connected"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.api.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)
