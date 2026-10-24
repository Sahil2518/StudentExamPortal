# Intelligent Exam Portal

**Role:** AI Intern  
**Company:** Meetmux  

---

## Project overview
A production-grade, full-stack adaptive examination platform featuring machine learning-driven question selection, skill mastery tracking, retention modeling, secure proctoring integrity, and deep learning knowledge tracing architectures.

## Problem statement
Traditional assessment platforms often deliver static question banks that fail to adapt to individual student abilities, lacking dynamic estimation of true knowledge states over time. Moreover, existing systems frequently suffer from poor proctoring integrity and lack comprehensive insights into learning retention.

## Key objectives
1. Deliver a dynamically adaptive examination experience based on real-time student performance.
2. Ensure uncompromising proctoring integrity through event sequencing and replay protection.
3. Track multi-dimensional skill mastery using Knowledge Tracing and retention decay models.
4. Maintain a robust, production-ready, migration-safe database architecture.

## System architecture
- **Frontend:** React, TypeScript, Vite, Tailwind CSS. Communicates securely via REST.
- **Backend:** FastAPI (Python), strictly typed with Pydantic.
- **Database:** PostgreSQL (Neon) managed securely via Alembic.
- **ML Engine:** Custom implementations of Thompson Sampling, IRT, and deep learning KT frameworks (PyTorch/Scikit-learn).

## Technology stack
- **Frontend:** React 18, Vite, TypeScript, TailwindCSS, Vitest, React Router v6.
- **Backend:** Python 3.11, FastAPI, SQLAlchemy, Alembic, Pytest.
- **ML/AI:** Scikit-learn, PyTorch, LightGBM, XGBoost, CatBoost.
- **Database:** PostgreSQL.

## Major modules
- **Auth & Authorization:** Role-based access (student, reviewer, admin) via JWT.
- **Exam Engine:** Session lifecycles, answer validation, dynamic scoring.
- **Adaptive Engine:** Contextual Bandit and IRT.
- **Proctoring System:** Web-camera verification and browser-focus event tracking.
- **Admin & Reviewer Portals:** Quality assurance and session auditing.

## Adaptive assessment workflow
1. Student starts an exam session.
2. The Adaptive Engine requests the Contextual Bandit for an optimal question based on the student's mastery.
3. Student submits an answer.
4. The attempt is reliably persisted (with idempotency guarantees).
5. The outcome updates the student's skill mastery and the Bandit's internal Alpha/Beta state immediately.
6. The cycle repeats until the test completes.

## Machine-learning components
- **Performance Model:** Baseline logistic regression, XGBoost, LightGBM, and CatBoost models to predict correctness probability.
- **Item Response Theory (IRT):** 2PL model for difficulty and discrimination tracking.
- **Contextual Thompson Sampling Bandit:** Dynamically optimized exploration/exploitation of questions.

## Knowledge tracing status
Deep learning KT models (AKT, DKT+, SAKT, BKT) are implemented architecturally. 
**Current Status:** `BLOCKED_BY_DATA` / `NOT_TRAINED`.
The models honestly enforce a `NOT_TRAINED` state until sufficient sequential interaction data is aggregated to execute legitimate training runs. No metrics are fabricated.

## Proctoring architecture
- **Client Side:** React hook securely accesses `navigator.mediaDevices.getUserMedia()`, tracking permissions and blur events without streaming raw video.
- **Server Side:** REST endpoints enforce duplicate rejection via `client_event_id` and strict replay protection using monotonically increasing sequence verification.

## AI tutor
An LLM-driven explainer that provides contextualized feedback on incorrect answers. 
If the API key (`OPENAI_API_KEY`) is omitted, the system gracefully degrades to utilizing static stored question explanations, preventing application crashes.

## Database architecture
The system uses PostgreSQL.
- Database schemas are actively managed using **Alembic**.
- Production `create_all()` calls are explicitly removed to prevent accidental data destruction.
- Isolated temporary SQLite databases are exclusively spawned and destroyed dynamically for unit tests.

## Setup instructions

### Environment configuration
Copy the `.env.example` file to `.env` in the `ai_exam_system` directory.
Populate the `DATABASE_URL`, `JWT_SECRET_KEY`, and (optionally) `OPENAI_API_KEY`.
Do NOT commit `.env` to version control.

### Database migration instructions
Ensure the database is up-to-date with Alembic:
```bash
cd ai_exam_system
python -m alembic upgrade head
```

### Backend startup
```bash
cd ai_exam_system
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend startup
```bash
cd frontend
npm install
npm run dev
```

## Testing instructions
Backend tests (Pytest):
```bash
cd ai_exam_system
python -m pytest tests/ -v
```

Frontend tests (Vitest):
```powershell
cd frontend
npx vitest run
```

## Current limitations
- **Dataset Size:** Due to limited initial student interactions, deep knowledge tracing models are currently `BLOCKED_BY_DATA` and operate using fallback synthetic heuristics until sufficient real-world data is collected.
- **Question Bank:** Question count is static; dynamic generation requires future integration.

## Future scope
- Full execution of deep KT models once real student traffic achieves minimum thresholds.
- Advanced Computer Vision tracking (e.g. YOLO-based multiple face detection) once specific GPU infrastructure is provisioned.
- Question generation pipeline via LLMs to perpetually scale domain coverage.
