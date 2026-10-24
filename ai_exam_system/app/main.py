"""
AI Adaptive Exam System - main application entry point.

This module creates the FastAPI application, configures CORS,
and registers all route modules. Startup only verifies database 
connectivity; schema management is handled exclusively by Alembic migrations.

To start the development server:
    cd ai_exam_system
    uvicorn app.main:app --reload

Environment variables required (see .env.example):
    DATABASE_URL     - PostgreSQL connection string
    JWT_SECRET_KEY   - Random string used to sign JWT tokens
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Set up structured logging so errors are visible without crashing the app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)
logger = logging.getLogger("ai_exam_system")

# Import all route modules
from app.routes.user_routes import router as user_router
from app.routes.auth_routes import router as auth_router
from app.routes.student_profile_routes import router as student_profile_router
from app.routes.question_routes import router as question_router
from app.routes.question_attempt_routes import router as question_attempt_router
from app.routes.adaptive_routes import router as adaptive_router
from app.routes.knowledge_state_routes import router as knowledge_state_router
from app.routes.retention_routes import router as retention_router
from app.routes.ml_routes import router as ml_router
from app.routes.ml_dataset_routes import router as ml_dataset_router
from app.routes.performance_routes import router as performance_router
from app.routes.skill_performance_routes import router as skill_performance_router
from app.routes.exam_session_routes import router as exam_session_router
from app.routes.proctoring_routes import router as proctoring_router
from app.routes.admin_routes import router as admin_router
from app.routes.tutor_routes import router as tutor_router


# ---------------------------------------------------------------------------
# Startup / shutdown lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Run tasks at startup and shutdown.

    On startup: Verify database connectivity.
    Schema management is handled by Alembic migrations.
    """

    try:
        from sqlalchemy import text
        from app.database.connection import engine
        
        # We no longer run Base.metadata.create_all() automatically in production.
        # Ensure database is accessible.
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified on startup. (Schema should be managed by Alembic)")
    except Exception as exc:
        logger.warning(
            "Database initialization failed: %s. "
            "Check DATABASE_URL in your .env file. "
            "Application is starting in a degraded state.",
            exc
        )
        # Do not crash the app - some routes may still work.

    yield  # Application runs here

    # Shutdown cleanup would go here if needed
    logger.info("Application shutting down.")


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Adaptive Exam System",
    description=(
        "Adaptive examination platform with ML-powered question selection, "
        "skill mastery tracking, retention modeling, and proctoring support."
    ),
    version="1.0.0",
    lifespan=lifespan
)


# ---------------------------------------------------------------------------
# CORS configuration
# Allows the React frontend (running on localhost:5173 in dev) to call
# the API. In production, replace these origins with your actual domain.
# ---------------------------------------------------------------------------

import os

default_origins = [
    "http://localhost:5173",   # Vite dev server
    "http://localhost:3000",   # Alternative React dev port
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
env_origins = os.getenv("CORS_ORIGINS")
allowed_origins = [o.strip() for o in env_origins.split(",") if o.strip()] if env_origins else default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

# Authentication - register and login
app.include_router(user_router, tags=["Authentication"])
app.include_router(auth_router, tags=["Authentication"])

# Student profile
app.include_router(student_profile_router, tags=["Student Profile"])

# Question bank
app.include_router(question_router)

# Exam lifecycle
app.include_router(exam_session_router)
app.include_router(question_attempt_router)

# Adaptive question selection
app.include_router(adaptive_router, tags=["Adaptive Engine"])

# Knowledge state and retention
app.include_router(knowledge_state_router, tags=["Knowledge State"])
app.include_router(retention_router, tags=["Retention"])

# Performance analytics
app.include_router(performance_router, tags=["Performance"])
app.include_router(skill_performance_router, tags=["Performance"])

# ML feature export and dataset export
app.include_router(ml_router, tags=["ML"])
app.include_router(ml_dataset_router, tags=["ML"])

# Proctoring and review workflow
app.include_router(proctoring_router)

# Admin user management
app.include_router(admin_router)

# LLM Tutor - explains answers and gives study recommendations
app.include_router(tutor_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
def health_check():
    """Simple health check endpoint."""
    return {
        "status": "running",
        "application": "AI Adaptive Exam System",
        "version": "1.0.0"
    }


@app.get("/ready", tags=["Health"])
def readiness_check():
    """
    Readiness check including database connectivity.

    Returns the database connection status so that load balancers
    and monitoring tools can verify the full stack is healthy.
    """

    from app.database.connection import engine
    from sqlalchemy import text
    from fastapi import HTTPException

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        db_status = "unreachable"
        raise HTTPException(
            status_code=503,
            detail={
                "status": "degraded",
                "database": "unreachable",
                "version": "1.0.0"
            }
        )

    return {
        "status": "running",
        "database": db_status,
        "version": "1.0.0"
    }
