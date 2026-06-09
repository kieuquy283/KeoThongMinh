# KeoBot Desktop

Electron shell for packaging the KeoBot voice MVP as a Windows desktop app.

## Status

The desktop main process already handles backend lifecycle startup, backend health checking, and loading the frontend in dev and packaged modes.

The release build expects the backend to be packaged in `onedir` form at:

```text
resources/backend/keobot_backend/keobot_backend.exe
```

## Scripts

```bash
npm run dev
npm run start
npm run pack
npm run build
```

## Environment

Use `desktop/.env.example` as the starting point for desktop-specific env vars.

## Troubleshooting

- `Port 8000 already in use`: stop the existing backend or let Electron attach to the healthy backend if it is already responding on `http://127.0.0.1:8000/health`.
- `Python not found`: install Python and make sure `python` is on `PATH`, or point the desktop launcher at the correct interpreter.
- `backend exe not found`: run `cd backend && python scripts/build_backend_exe.py` before building the desktop package.
- `microphone permission blocked`: allow microphone access for the app in Windows privacy settings and in the browser permission prompt.
- `API key missing`: set the required provider key in `backend/.env` before using live STT, LLM, or TTS providers.
- `auto conversation sends too early or too late`: adjust the frontend silence detection threshold and duration in code for the target microphone and room noise.

## Packaging Notes

- Production packaging expects `frontend/dist/` to exist.
- Production packaging expects `backend/dist/keobot_backend/keobot_backend.exe` to exist.
- Output is written to `release/`.
- Portable output: `KeoBot-Portable-v0.3.0.exe`
- Installer output: `KeoBot-Setup-v0.3.0.exe`
- Smoke test: `npm run smoke:packaged`

## Desktop Settings

Desktop settings are stored at `%APPDATA%/KeoBot/config.json`.

- API keys are never committed.
- API keys are never bundled into the app.
- After changing settings, restart KeoBot to apply them if backend restart is not exposed.
- Mock/local mode can be used for demos without keys.
- Live providers require OpenAI or Gemini/Google keys.
- Weather provider settings are optional.
- Search provider settings are optional.
- If you see a provider key missing error, reopen Settings, verify the key, and save again.

Supported optional information-tool settings:

- `WEATHER_PROVIDER`
- `OPENWEATHER_API_KEY`
- `SEARCH_PROVIDER`
- `TAVILY_API_KEY`
- `SERPAPI_API_KEY`

Use the `Check tools` button in Settings to query `/tools/status` and verify whether weather/search is configured.

## Lightweight Local Memory v0.9.0

The desktop app also exposes a separate Memory panel.

- Settings stores provider configuration and API keys.
- Memory stores explicit user preferences only.
- Memory is local-only and is stored in the backend SQLite database under `KEOBOT_DATA_DIR/memory.sqlite3`.
- The Memory panel should not be used for secrets or API keys.

Allowed memory keys:

- `user_name`
- `preferred_form_of_address`
- `default_city`
- `default_timezone`
- `default_currency`
- `preferred_tts_voice`
- `answer_style`

## Voice Conversation Modes

### Manual mode

- Press record to start.
- Press stop to send the turn.
- Wait for the backend response and audio playback.

### Auto conversation mode

- Press `Bat dau tro chuyen` once.
- The frontend listens continuously.
- Silence detection submits a turn automatically after the speaker stops.
- After KeoBot finishes speaking, the app returns to listening automatically until stopped.

## Reminders

- Reminders are stored locally in the backend SQLite database.
- Notifications appear only while the desktop app is open.
- Due reminders are polled from the local backend on a timer.

## Known Limitations

- Auto conversation is near-realtime, not full streaming realtime.
- It depends on Windows microphone permission and Chromium `MediaRecorder` behavior.
- Silence threshold can require tuning for different microphones.
- There is no wake word.
- Interrupt support only stops local playback or aborts the current request before the backend returns.
- Weather and search require provider/API-key configuration before KeoBot can answer live questions.
- When a tool is not configured, KeoBot should report that clearly instead of inventing data.
- Currency can still answer with a demo rate when live exchange-rate configuration is missing.
- Memory is local-only and does not sync to cloud storage.
