# Kẹo Thông Minh Backend

FastAPI backend for the Kẹo Thông Minh voice pipeline MVP.

## Release v0.3.0

This backend currently ships as part of the desktop release `v0.3.0`.

## Release Packaging

The release build uses an `onedir` layout for faster and more deterministic packaging than `onefile`.

## Tool Intelligence v0.7.0

The backend now includes a rule-based real-world tool layer:

- `backend/app/services/entity_extractor.py`
- `backend/app/services/tool_router.py`
- `backend/app/tools/time_tool.py`
- `backend/app/tools/currency_tool.py`
- `backend/app/tools/weather_tool.py`
- `backend/app/tools/search_tool.py`

The backend also exposes `GET /tools/status` and `POST /tools/test` for provider diagnostics.

Do not fabricate weather, search/news, or live exchange rates when the provider is not configured.

## Lightweight Local Memory v0.9.0

The backend now stores a small local-only memory layer in SQLite:

- `KEOBOT_DATA_DIR/memory.sqlite3`
- fallback: `backend/data/memory.sqlite3`

Allowed memory keys:

- `user_name`
- `preferred_form_of_address`
- `default_city`
- `default_timezone`
- `default_currency`
- `preferred_tts_voice`
- `answer_style`

Memory endpoints:

- `GET /memory`
- `POST /memory`
- `DELETE /memory/{key}`
- `DELETE /memory`

Memory is separate from Settings. Settings hold provider/API-key configuration; memory holds explicit user preferences only.
Do not store API keys or hidden/system data in memory.

## Hands-free Assistant v0.9.0

The backend does not implement wake word or tray logic, but it still supports the background assistant foundation indirectly:

- reminders continue to work while the desktop app is minimized to tray
- the backend stays request/response for voice and text chat
- the frontend and Electron shell trigger listening through IPC and `/voice-chat`
- wake-word detection itself stays in the frontend renderer when supported

Known limitations:

- The app must be running for hands-free mode to work
- Microphone permission is still required on the desktop side
- Wake word is an MVP and is not a dedicated low-power wake-word engine
- Hotkey conflicts are handled in Electron, not in the backend

## Desktop Settings

Desktop settings are saved locally at the existing `%APPDATA%/KeoBot/config.json` compatibility path.

- API keys are never committed.
- API keys are never bundled into the app.
- Mock/local mode can be used for demos without keys.
- Live providers require OpenAI or Gemini/Google keys from desktop settings or `.env`.
- If a provider key is missing, update Settings or `.env` and restart the app.
- Weather/search providers are optional and can be checked with `GET /tools/status`.

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
MOCK_STT_TEXT=Kẹo Thông Minh oi, ban la ai?
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
- Reminder data is stored locally in SQLite under `KEOBOT_DATA_DIR` or `backend/data/`.
- Memory data is stored locally in SQLite under `KEOBOT_DATA_DIR` or `backend/data/`.
- `backend/tmp/` and `backend/app/static/audio/` are runtime directories.
- TTS writes generated `.mp3` files into `app/static/audio`.
- Live providers still require API keys via `.env`; keys are never bundled into the app.
- Currency has a demo fallback when live exchange-rate configuration is missing.
