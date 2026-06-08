# KeoBot Voice Pipeline

KeoBot is a Vietnamese voice assistant MVP. This phase focuses on stabilizing the voice pipeline, keeping the repo clean, and making the project easy to validate locally.

## Overview

Flow:

1. Browser records Vietnamese audio with `MediaRecorder`.
2. Frontend uploads the audio to the FastAPI backend.
3. Backend transcribes audio into text.
4. LLM generates a KeoBot persona response.
5. TTS synthesizes Vietnamese speech as `.mp3`.
6. Browser plays the returned audio URL.

## Current Structure

- `backend/` FastAPI app, providers, service orchestration, tests, validation script
- `frontend/` React + Vite UI, recorder, chat panel, audio playback
- `references/` KeoBot character reference images
- `character_bible.md` persona and visual guidance
- `KEOBOT_VOICE_PIPELINE_TASK.md` original implementation task

## Backend Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend defaults to `http://localhost:8000`. Override with `VITE_API_BASE_URL` if needed.

## Mock / Local Mode

Use this mode for offline development and validation:

```env
STT_PROVIDER=mock
LLM_PROVIDER=local
TTS_PROVIDER=edge_tts
MOCK_STT_TEXT=KeoBot oi, ban la ai?
```

This keeps the pipeline runnable without external API keys.

## API Mode

If you want live providers, configure the keys and provider selection in `backend/.env`:

```env
STT_PROVIDER=openai
LLM_PROVIDER=openai
TTS_PROVIDER=edge_tts
OPENAI_API_KEY=...
```

Gemini is available as a fallback LLM option if configured.

## Environment Variables

Important backend variables:

```env
APP_NAME=KeoBot Voice Pipeline
APP_ENV=development
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
FRONTEND_ORIGIN=http://localhost:5173
STT_PROVIDER=openai
LLM_PROVIDER=openai
TTS_PROVIDER=edge_tts
OPENAI_API_KEY=...
OPENAI_STT_MODEL=gpt-4o-mini-transcribe
OPENAI_CHAT_MODEL=gpt-4o-mini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-1.5-flash
EDGE_TTS_VOICE=vi-VN-HoaiMyNeural
EDGE_TTS_RATE=+0%
EDGE_TTS_VOLUME=+0%
MAX_UPLOAD_SIZE_MB=15
MOCK_STT_TEXT=KeoBot oi, ban la ai?
```

## Tests

Backend tests:

```bash
cd backend
python -m pytest
```

Backend validation:

```bash
cd backend
python scripts/validate_backend.py
```

Frontend checks:

```bash
cd frontend
npm run typecheck
npm run build
```

## Known Limitations

- No avatar, VRM, three-vrm, or lip-sync yet.
- No RAG or memory layer yet.
- Voice flow is request/response, not realtime streaming.
- Generated audio files are stored under `backend/app/static/audio/` and should be treated as runtime artifacts.

## Next Phase

- Avatar placeholder upgrade
- 3D VRM integration
- Lip-sync

## Running as Windows Desktop App

### Dev mode

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

cd ../frontend
npm install

cd ../desktop
npm install
npm run dev
```

If you prefer the root wrapper:

```bash
npm run app:dev
```

### Build frontend

```bash
cd frontend
npm run build
```

### Build backend exe

```bash
cd backend
python scripts/build_backend_exe.py
```

### Build desktop app

```bash
cd desktop
npm run build
```

### Output

```text
release/
```

### Notes

- Backend runs locally on `127.0.0.1:8000`.
- No web deployment is required.
- Configure API keys via `.env`.
- Do not bundle private API keys into the Electron release.
- Mock/local mode can be used for demos.
