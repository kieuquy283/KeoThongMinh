# KeoBot Backend

FastAPI backend for the KeoBot voice pipeline MVP.

## Release Packaging

The release build uses an `onedir` layout for faster and more deterministic packaging than `onefile`.

## Desktop Settings

Desktop settings are saved locally at `%APPDATA%/KeoBot/config.json`.

- API keys are never committed.
- API keys are never bundled into the app.
- Mock/local mode can be used for demos without keys.
- Live providers require OpenAI or Gemini/Google keys from desktop settings or `.env`.
- If a provider key is missing, update Settings or `.env` and restart the app.

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

## Packaged Smoke Test

```bash
python scripts/smoke_backend_exe.py
```

## Release Output

```text
backend/dist/keobot_backend/keobot_backend.exe
```

## Notes

- `.env` is not committed.
- `backend/tmp/` and `backend/app/static/audio/` are runtime directories.
- TTS writes generated `.mp3` files into `app/static/audio`.
- Live providers still require API keys via `.env`; keys are never bundled into the app.
