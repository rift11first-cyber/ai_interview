# InterviewIQ

Desktop-first AI interview preparation platform for college students.

## Stack

- **Frontend:** React + TypeScript + Vite + Tailwind (desktop UI; Tauri packaging next)
- **Backend:** FastAPI on `127.0.0.1:8765`
- **Storage:** SQLite (structured) + LanceDB (interview experience vectors)
- **LLM:** OpenRouter (user-provided API key) with offline heuristic fallbacks
- **Resume:** PyMuPDF + LLM structuring

## Quick start

### Backend

```bash
cd backend
uv sync --python 3.12
uv run interviewiq
# or: uv run uvicorn interviewiq_backend.main:app --host 127.0.0.1 --port 8765 --reload
```

### Frontend

```bash
cd apps/desktop
npm install
npm run dev
```

Open http://127.0.0.1:5173 — add your OpenRouter key under **Settings**.

## MVP features

1. Resume PDF upload & parsing
2. Company / role selection (Amazon, Goldman Sachs, Cognizant ACE, Google, Microsoft)
3. Text mock interview (one question at a time + follow-ups)
4. RAG over seeded interview experiences in LanceDB
5. Post-interview evaluation with recommendations
6. Local persistence under `~/.local/share/interviewiq/`

## Project layout

```
apps/desktop/     React UI
backend/          FastAPI + services
knowledge/seed/   Curated interview experience chunks
```

## Next phases

Voice (Faster-Whisper + Piper/Kokoro), analytics, replay, company trends, learning roadmaps, Tauri installers for Win/macOS/Linux.
