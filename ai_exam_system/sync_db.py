"""
Database synchronization script:
Ensures all tables in Base.metadata exist in the production database (Neon Postgres)
and all missing columns are added safely.
"""

from app.database.connection import engine
from app.database.base import Base

# Import all models to register them with Base.metadata
from app.models.user import User
from app.models.student_profile import StudentProfile
from app.models.question import Question
from app.models.question_attempt import QuestionAttempt
from app.models.exam_session import ExamSession
from app.models.exam_session_question import ExamSessionQuestion
from app.models.proctoring import ProctoringEvent, ReviewDecision
from app.models.bandit_state import BanditState
from app.models.bandit_update import BanditUpdate

from sqlalchemy import text

def sync():
    print("Creating any missing tables from models...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")

    # Safely add columns to exam_sessions if they are missing
    with engine.begin() as conn:
        print("Checking exam_sessions columns...")
        alter_statements = [
            "ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS exam_type VARCHAR(20) DEFAULT 'practice' NOT NULL;",
            "ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS positive_mark FLOAT DEFAULT 4.0 NOT NULL;",
            "ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS negative_mark FLOAT DEFAULT 1.0 NOT NULL;",
            "ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS negative_marks_total FLOAT DEFAULT 0.0 NOT NULL;",
            "ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS raw_score FLOAT;",
            "ALTER TABLE exam_sessions ADD COLUMN IF NOT EXISTS exam_paper_title VARCHAR(255);",
            "ALTER TABLE exam_session_questions ADD COLUMN IF NOT EXISTS review_status VARCHAR(30) DEFAULT 'not_visited' NOT NULL;",
            "ALTER TABLE exam_session_questions ADD COLUMN IF NOT EXISTS selected_option VARCHAR(500);",
            "ALTER TABLE exam_session_questions ADD COLUMN IF NOT EXISTS is_correct BOOLEAN;"
        ]
        for stmt in alter_statements:
            conn.execute(text(stmt))
        print("Columns synced.")

if __name__ == "__main__":
    sync()
