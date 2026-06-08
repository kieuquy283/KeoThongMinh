# KeoBot Backend

FastAPI backend for the KeoBot voice pipeline MVP.

## Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Local Mock Mode

Use this configuration for offline development:

```env
STT_PROVIDER=mock
LLM_PROVIDER=local
TTS_PROVIDER=edge_tts
MOCK_STT_TEXT=KeoBot oi, ban la ai?
```

## Tests

```bash
python -m pytest
```

## Validation

```bash
python scripts/validate_backend.py
```

## Notes

- `.env` is not committed.
- `backend/tmp/` and `backend/app/static/audio/` are runtime directories.
- TTS writes generated `.mp3` files into `app/static/audio`.
