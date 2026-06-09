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

## Packaging Notes

- Production packaging expects `frontend/dist/` to exist.
- Production packaging expects `backend/dist/keobot_backend/keobot_backend.exe` to exist.
- Output is written to `release/`.
- Portable output: `KeoBot-Portable-v0.1.1.exe`
- Installer output: `KeoBot-Setup-v0.1.1.exe`
- Smoke test: `npm run smoke:packaged`

## Desktop Settings

Desktop settings are stored at `%APPDATA%/KeoBot/config.json`.

- API keys are never committed.
- API keys are never bundled into the app.
- After changing settings, restart KeoBot to apply them if backend restart is not exposed.
- Mock/local mode can be used for demos without keys.
- Live providers require OpenAI or Gemini/Google keys.
- If you see a provider key missing error, reopen Settings, verify the key, and save again.
