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

from api.auth import hash_password
from api.database import Base, SessionLocal, engine
from api.models import Assignment, User
from api.routes import assignments, auth, reports, submissions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")


def seed_default_data() -> None:
    """Ensure default teacher and assignments exist for development / quickstart."""
    db = SessionLocal()
    try:
        teacher = db.query(User).filter(User.email == "teacher@university.edu").first()
        if not teacher:
            logger.info("Creating default teacher: teacher@university.edu")
            teacher = User(
                email="teacher@university.edu",
                hashed_password=hash_password("password123"),
                full_name="Professor Smith",
                role="teacher",
            )
            db.add(teacher)
            db.commit()
            db.refresh(teacher)
            logger.info("Default teacher created.")

        default_assignments = [
            {
                "id": "general",
                "title": "General Submissions",
                "class_name": "General Class",
                "description": "General submissions and ad-hoc document checks.",
            },
            {
                "id": "ethics-final",
                "title": "Ethics in Computing - Term Paper",
                "class_name": "Philosophy 101",
                "description": "Ethics in Computing term paper submissions.",
            },
        ]

        for item in default_assignments:
            assign = db.query(Assignment).filter(Assignment.id == item["id"]).first()
            if not assign:
                logger.info("Creating default assignment: %s (%s)", item["id"], item["title"])
                assign = Assignment(
                    id=item["id"],
                    teacher_id=teacher.id,
                    title=item["title"],
                    class_name=item["class_name"],
                    description=item.get("description"),
                )
                db.add(assign)
                db.commit()
                logger.info("Default assignment %s created.", item["id"])
            elif assign.teacher_id != teacher.id:
                assign.teacher_id = teacher.id
                db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Error seeding default data: %s", e, exc_info=True)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database schema is created
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized.")
    seed_default_data()
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
