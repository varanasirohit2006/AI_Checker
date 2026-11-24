"""FastAPI Application Entrypoint (Step 9).

Main backend service exposing REST endpoints for:
  * Teacher authentication
  * Class & Assignment management
  * Async document uploads & status polling
  * Unified report retrieval
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import Base, engine
from api.routes import assignments, auth, reports, submissions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database schema is created
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized.")
    yield


app = FastAPI(
    title="Originality Checker API",
    description="Backend API for AI Writing Detection, Plagiarism/Similarity Analysis, and Red Flag Tamper Inspection.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(assignments.router)
app.include_router(submissions.router)
app.include_router(reports.router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "healthy", "service": "originality-checker-api", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
