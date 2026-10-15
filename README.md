# Mind AI - Phase 1: Foundation
## Setup Instructions
1. Run `docker-compose up -d` to start PostgreSQL and Redis.
2. Install backend dependencies: `pip install fastapi uvicorn sqlalchemy pydantic openai celery redis`
3. Install frontend dependencies: `npm install` (Ensure Next.js, Tailwind, and ShadCN are initialized).
4. Start backend: `uvicorn backend.app.main:app --reload`
5. Start frontend: `npm run dev`
