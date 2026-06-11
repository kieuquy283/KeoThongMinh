# Kẹo Thông Minh Voice Pipeline

Kẹo Thông Minh is a Vietnamese voice assistant MVP. The current phase adds a near-realtime conversation loop on top of the existing request/response voice pipeline.

## Overview

Core flow:

1. Browser records Vietnamese audio with `MediaRecorder`.
2. Frontend uploads the audio to the FastAPI backend.
3. Backend transcribes audio into text.
4. LLM generates a Kẹo Thông Minh persona response.
5. TTS synthesizes Vietnamese speech as `.mp3`.
6. Browser plays the returned audio URL.

Near-realtime conversation flow:

1. User enables auto conversation mode.
2. Frontend opens the microphone and starts listening.
3. Silence detection watches microphone RMS volume in the browser.
4. When speech is detected and then silence lasts long enough, the current turn is sent to `/voice-chat`.
5. Kẹo Thông Minh plays the returned audio reply.
6. After playback ends, the frontend returns to listening automatically if auto mode is still enabled.

## Current Structure

- `backend/` FastAPI app, providers, service orchestration, tests, validation scripts
- `frontend/` React + Vite UI, recorder, chat panel, audio playback, silence detection
- `desktop/` Electron shell and packaged app validation
- `frontend/public/keobot/` canonical 2D mascot PNG assets used by the renderer
- `references/` Kẹo Thông Minh character reference images
- `character_bible.md` persona and visual guidance
- `KEOBOT_VOICE_PIPELINE_TASK.md` original implementation task

## 2D Mascot System

This phase integrates a 2D image-based KeoBot mascot system for the desktop UI.

- Asset location: `frontend/public/keobot/`
- Rendering mode: React + CSS only
- Not included in this phase: Live2D, VRM, GLB/3D avatar rendering, lip-sync engine

Canonical asset names:

- `keobot_idle.png`
- `keobot_listening.png`
- `keobot_thinking.png`
- `keobot_speaking_1.png`
- `keobot_speaking_2.png`
- `keobot_speaking_3.png`
- `keobot_happy.png`
- `keobot_error.png`
- `keobot_reminder.png`
- `keobot_blink_1.png`
- `keobot_blink_2.png`
- `keobot_wave.png`
- `keobot_celebrate.png`
- `keobot_thinking_alt.png`
- `keobot_loading.png`
- `keobot_goodbye.png`
- `keobot_confused.png`
- `keobot_sad.png`
- `keobot_sleepy.png`
- `keobot_surprised_alt.png`
- `keobot_processing.png`
- `keobot_calm.png`

State mapping summary:

- `idle` -> idle/calm art with breathing and blink
- `listening` -> listening art with attention pulse
- `thinking` -> thinking or thinking-alt art with dot indicator
- `speaking` -> `keobot_speaking_1..3.png` frame loop
- `loading` -> loading or processing art with status dots
- `reminder` -> reminder art with friendly pulse
- `error` -> error or sad art with soft shake
- special emotions -> happy, celebrate, confused, sleepy, calm, surprised

Fallback behavior:

- missing speaking frames fall back to `keobot_speaking_1.png` then idle
- missing `thinking_alt` falls back to thinking
- missing loading art falls back to processing, then thinking
- missing celebrate art falls back to happy
- missing sad art falls back to error
- missing calm art falls back to idle

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

Frontend defaults to `http://127.0.0.1:8000`. Override with `VITE_API_BASE_URL` if needed.

## Voice Modes

### Manual voice mode

- Click to start recording.
- Click again to stop and send audio.
- Kẹo Thông Minh replies after the backend finishes the full request/response turn.

### Auto conversation mode

- Turn on auto conversation in the recorder UI.
- The frontend keeps the microphone open.
- A turn is auto-submitted after speech ends and silence lasts long enough.
- After Kẹo Thông Minh finishes speaking, the app returns to listening automatically.

## Real-world Information Tools

Kẹo Thông Minh now supports tool-assisted answers for real-world questions:

- `time`: current time in supported timezones
- `currency`: exchange-rate lookup with clear demo fallback when live provider is not configured
- `weather`: live weather only when configured
- `news_search`: latest-news lookup only when configured
- `general_search`: general web information lookup only when configured

Tool routing is rule-based in the backend and runs before normal LLM fallback.
The backend order is:

1. reminder intent
2. real-world tool intent
3. normal LLM response

Memory sits before reminders in the chat flow and is limited to explicit preference commands.

## Tool Intelligence v0.7.0

This phase hardens the tool layer:

- rule-based entity extraction for location, timezone, currency, and search topics
- confidence-based routing to reduce false positives
- deduped search/news sources
- provider status endpoint for diagnostics
- demo-vs-live exchange rate handling

Do not fabricate current weather, news, or live rates when a provider is not configured.

## Lightweight Local Memory v0.9.0

Kẹo Thông Minh also supports a small local-only memory layer for simple preferences:

- `user_name`
- `preferred_form_of_address`
- `default_city`
- `default_timezone`
- `default_currency`
- `preferred_tts_voice`
- `answer_style`

Memory is stored in SQLite at `KEOBOT_DATA_DIR/memory.sqlite3` and is separate from Settings.
Settings hold provider/API-key configuration. Memory holds only user preferences.

Memory endpoints:

- `GET /memory`
- `POST /memory`
- `DELETE /memory/{key}`
- `DELETE /memory`

Memory commands must be explicit. Kẹo Thông Minh does not silently capture sensitive data.

## Silence Detection

Default frontend silence detection settings:

```ts
{
  volumeThreshold: 0.02,
  silenceMs: 1000,
  minSpeechMs: 500,
}
```

These values are frontend-side only and can be tuned for different microphones or room noise.

## Hands-free Assistant v1.0

Kẹo Thông Minh now supports a complete hands-free desktop experience:

- **System tray** keeps the app running after the window is closed.
- **Global hotkey** (default `Ctrl+Shift+K`) starts listening; works even while the window is hidden.
- **Wake word** (`Kẹo Thông Minh ơi`, `này Kẹo Thông Minh`, `hey Kẹo Thông Minh`) runs locally via the Web Speech API.
- **Auto return to wake mode** after a response finishes (configurable).
- **Hotkey can be disabled** in Settings if not needed.
- **Tray menu**: Show Kẹo Thông Minh, Start Listening, Toggle Wake Word, Open Settings, Quit.
- **Background mode**: closing/minimizing hides to tray instead of quitting.
- **Start with Windows**: optional login-item registration in Settings.
- **Reminders** still poll while minimized and show native notifications.
- **Privacy**: Wake word listens locally. Audio is sent to the backend only after activation.

### Wake Word MVP

- Phrases: `Kẹo Thông Minh ơi`, `này Kẹo Thông Minh`, `hey Kẹo Thông Minh` (configurable).
- Runs in the frontend renderer using the Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`).
- Only starts a voice-command turn after a phrase is matched.
- If the Web Speech API is unavailable, the mascot shows a clear fallback message:
  > "Wake word is not supported in this environment. Use Ctrl+Shift+K instead."
- The global hotkey always works as a fallback, even when wake word is unsupported.

### Settings (new in v1.0)

| Setting | Default | Description |
|---------|---------|-------------|
| `WAKE_WORD_ENABLED` | `false` | Enable/disable wake word listening |
| `WAKE_WORD_PHRASES` | `Kẹo Thông Minh ơi, này Kẹo Thông Minh, hey Kẹo Thông Minh` | Wake phrases (one per line) |
| `HOTKEY_ENABLED` | `true` | Enable/disable the global hotkey |
| `HOTKEY_VALUE` | `Ctrl+Shift+K` | The hotkey accelerator (read-only) |
| `HANDSFREE_AUTO_RETURN_TO_WAKE_MODE` | `true` | Auto-restart wake word after response |
| `START_WITH_WINDOWS` | `false` | Register at Windows login (packaged only) |
| `BACKGROUND_ASSISTANT_ENABLED` | `true` | Keep app in tray when window is closed |

### Known Limitations

- Wake word is an MVP, not a dedicated low-power wake-word engine.
- The app must still be running in the background.
- Microphone permission is still required.
- The hotkey may conflict with other apps if they use the same shortcut.
- Wake word depends on the Web Speech API being available in the Electron renderer.
- If no microphone is available, wake word falls back to the hotkey.
- The backend remains request/response; there is no full realtime streaming interrupt.

## Mock / Local Mode

Use this mode for offline development and validation:

```env
STT_PROVIDER=mock
LLM_PROVIDER=local
TTS_PROVIDER=edge_tts
MOCK_STT_TEXT=Kẹo Thông Minh oi, ban la ai?
```

This keeps the pipeline runnable without external API keys.

## API Mode

If you want live providers, configure the keys and provider selection in `backend/.env`:

```env
STT_PROVIDER=openai
LLM_PROVIDER=openai
TTS_PROVIDER=edge_tts
OPENAI_API_KEY=...
GOOGLE_API_KEY=...
```

Gemini is available as a fallback LLM option if configured. `GOOGLE_API_KEY` works as an alias for Gemini in the backend.

## Information Tool Providers

Optional provider configuration:

```env
CURRENCY_PROVIDER=none
EXCHANGE_RATE_API_URL=
EXCHANGE_RATE_API_KEY=
WEATHER_PROVIDER=openweathermap
OPENWEATHER_API_KEY=
SEARCH_PROVIDER=tavily
TAVILY_API_KEY=
SERPAPI_API_KEY=
```

Desktop users can also store weather and search provider settings in the existing `%APPDATA%/KeoBot/config.json` compatibility path through the Settings panel.

Provider diagnostics:

- `GET /tools/status` returns weather/search/currency configuration state.
- The Settings panel has a `Check tools` button that calls the same endpoint.

## Fallback Behavior

- Time tool works locally with `zoneinfo` and does not need an external API.
- Currency tool uses demo fallback with a visible `Demo rate, not live.` marker when no live provider is configured.
- Weather tool returns `Weather provider not configured.` when unavailable.
- Search/news tool returns `Search provider not configured.` when unavailable.
- Kẹo Thông Minh should not invent current weather, exchange rates, or news when the required tool is not configured.

## How To Test Providers

1. Open desktop Settings.
2. Set the optional weather/search provider fields.
3. Click `Check tools`.
4. Confirm the weather/search rows change from `Not configured` to the configured provider name.
5. Use `/tools/status` directly if you want an API-level check.

## Environment Variables

Important backend variables:

```env
APP_NAME=Kẹo Thông Minh Voice Pipeline
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
MOCK_STT_TEXT=Kẹo Thông Minh oi, ban la ai?
CURRENCY_PROVIDER=none
EXCHANGE_RATE_API_URL=
EXCHANGE_RATE_API_KEY=
WEATHER_PROVIDER=none
OPENWEATHER_API_KEY=
SEARCH_PROVIDER=none
TAVILY_API_KEY=
SERPAPI_API_KEY=
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

Desktop checks:

```bash
cd desktop
npm run build
npm run smoke:packaged
```

## Known Limitations

- No Live2D, VRM, GLB/3D avatar rendering, or lip-sync engine in this phase.
- The mascot is a 2D asset-driven state system, not a realtime facial rig.
- No RAG or vector DB in this phase.
- Memory is lightweight, local-only, and limited to explicit preferences.
- Voice flow is still request/response, not full realtime streaming.
- Auto conversation depends on browser `MediaRecorder`, microphone permission, and Web Audio API support.
- Silence threshold is heuristic and may need tuning for different microphones or noisy rooms.
- Wake word relies on the Web Speech API being available in the Electron renderer.
- Interrupt only stops local playback or aborts the current request before the backend replies; there is no backend streaming interrupt.
- Weather and search need provider configuration before they can answer real-world queries.
- Currency can fall back to demo values, so the response must be treated as non-live unless a provider is configured.
- Reminders are stored locally in SQLite under `KEOBOT_DATA_DIR` or `backend/data/`.
- Reminders only fire while the desktop app is open and polling the local backend.
- Reminders do not sync to cloud services.
- Generated audio files are stored under `backend/app/static/audio/` and should be treated as runtime artifacts.

## Release v0.3.0

The desktop release uses a backend `onedir` layout for faster, more deterministic packaging.

## Desktop Settings

Settings are stored locally at the existing `%APPDATA%/KeoBot/config.json` compatibility path.
Memory is stored separately in the backend data directory, usually `KEOBOT_DATA_DIR/memory.sqlite3`.

- API keys are never committed.
- API keys are never bundled into the app.
- Mock/local mode can be used for demos without keys.
- Live providers require OpenAI or Gemini/Google keys in the desktop settings.
- After changing settings, restart Kẹo Thông Minh to apply them if backend restart is not exposed.
- If you see a provider key missing error, verify the key in Settings and save again.
- Memory values are not part of Settings and should not contain secrets.

### Dev mode

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd ..\frontend
npm install

cd ..\desktop
npm install
npm run dev
```

If you prefer the root wrapper:

```powershell
npm run app:dev
```

### Build frontend

```powershell
cd frontend
npm run build
```

### Build backend exe

```powershell
cd backend
python scripts/build_backend_exe.py
```

Backend output:

```text
backend/dist/keobot_backend/keobot_backend.exe
```

### Smoke test backend exe

```powershell
cd backend
python scripts/smoke_backend_exe.py
```

### Build desktop app

```powershell
cd desktop
npm run build
```

### Smoke packaged app

```powershell
cd desktop
npm run smoke:packaged
```

### Release artifacts to share

- `release/KeoThongMinh-Portable-v0.3.0.exe`
- `release/KeoThongMinh-Setup-v0.3.0.exe`

### Notes

- Backend runs locally on `127.0.0.1:8000`.
- The packaged backend lives at `resources/backend/keobot_backend/keobot_backend.exe`.
- No web deployment is required.
- Configure API keys via `.env`.
- `GOOGLE_API_KEY` is accepted as an alias for Gemini if you prefer that variable name.
- Do not bundle private API keys into the Electron release.
- Mock/local mode can be used for demos.

## Reminder Support

- Reminder data is stored locally in SQLite.
- The desktop app polls due reminders every 20 seconds by default.
- Desktop notifications only appear while Kẹo Thông Minh is open.
- Reminder data is local-only and does not sync to cloud services.

### Reminder quick test

1. Start the backend, frontend, and desktop app.
2. Say or type `1 phut nua nhac minh uong nuoc`.
3. Keep the desktop app open.
4. Wait for the toast in-app and the Electron notification.

## Auto Conversation Quick Test

1. Start the backend, frontend, and desktop app.
2. Switch the recorder to `Auto conversation`.
3. Click `Bat dau tro chuyen`.
4. Speak one short sentence.
5. Stay silent for about 1 second.
6. Confirm the app sends audio automatically, plays Kẹo Thông Minh's reply, and returns to listening.

## Real-world Tools Quick Test

1. Ask `Bay gio la may gio o Nhat?`
2. Ask `Ty gia USD sang VND hom nay?`
3. Ask `Thoi tiet Ha Noi hom nay the nao?` without weather API key and confirm Kẹo Thông Minh says the tool is not configured.
4. Ask `Tin AI moi nhat co gi?` without search API key and confirm Kẹo Thông Minh says the tool is not configured.

## Memory Quick Test

1. Say `Tu gio goi minh la Quy`.
2. Ask a normal question and confirm Kẹo Thông Minh uses the remembered name.
3. Say `Nho rang thanh pho mac dinh cua minh la Ha Noi`.
4. Ask `Thoi tiet hom nay the nao?` and confirm the backend applies the remembered city as its default.
5. Say `Xoa thanh pho mac dinh cua minh`.

## v1.3 — Release Hardening, Auto Update & Crash Diagnostics

### Diagnostics & Logging

All structured logs are written to the app's user data directory:
- `%APPDATA%/KeoBot/logs/main/` — main process events (start/quit, backend spawn/exit, tray actions, hotkeys)
- `%APPDATA%/KeoBot/logs/backend/` — backend stdout/stderr piped from Electron
- `%APPDATA%/KeoBot/logs/wake-word/` — wake word engine state changes
- `%APPDATA%/KeoBot/logs/update/` — auto-updater events

Logs are timestamped, have levels (debug/info/warn/error), and use daily rotation with a 5 MB max per day. Sensitive values (API keys, tokens) are redacted automatically.

### Crash Handling

- Uncaught exceptions and unhandled promise rejections in the main process are logged.
- Backend process exit code and signal are logged.
- Renderer can forward diagnostic events to the main process logger via `keobot:logDiagnostic` IPC.
- Electron's crash reporter is available but not enabled by default (no remote upload).

### Diagnostics UI

A "Diagnostics & About" section is available in the Settings panel:
- App version, build mode, commit hash
- Backend health status
- Open logs folder button
- Copy diagnostics summary button
- Auto-update status indicator

### Auto Update Structure

- `electron-updater` is installed and configured.
- The updater is disabled when no publish provider is configured (publish: null in package.json).
- When enabled, the updater emits events: checking, update_available, update_not_available, downloading, downloaded, error.
- UI in Settings shows update status.
- Update check/download/install is manual (autoDownload: false).
- See `docs/RELEASE_CHECKLIST.md` for release process.

### Release Validation

- `scripts/validate_release_artifacts.js` checks: portable exe, setup exe, backend exe in resources, mascot assets, no .env files, native modules, no hardcoded API keys.
- Run with: `cd desktop && npm run validate:artifacts`

### Test Coverage Added

- `test_diagnostics.py` — health response version/mode, API key redaction patterns

### Files Changed (v1.3)

| File | Change |
|---|---|
| `desktop/services/logger.js` | New — structured logger with rotation and redaction |
| `desktop/main.js` | Logger integration, crash handlers, backend logging, auto-updater, diagnostics IPC |
| `desktop/preload.js` | New bridges for getAppInfo, logDiagnostic, openLogsFolder, update events |
| `desktop/package.json` | Added electron-updater, services files, publish: null, validate scripts |
| `desktop/scripts/validate_release_artifacts.js` | New — 9-point asset/security check |
| `frontend/src/utils/diagnostics.ts` | New — diagnostic events logger |
| `frontend/src/utils/audioPlaybackController.ts` | Import diagnostics helper |
| `frontend/src/App.tsx` | Diagnostic logging for voice session, wake word, audio playback |
| `frontend/src/components/SettingsPanel.tsx` | Diagnostics & About section |
| `frontend/src/desktop.d.ts` | Type definitions for new IPC bridges |
| `backend/app/schemas.py` | Health response includes version and mode |
| `backend/app/main.py` | /health returns dynamic version/mode |
| `backend/tests/test_diagnostics.py` | New — health and redaction tests |
| `docs/MANUAL_QA_CHECKLIST.md` | New — 13-item manual QA checklist |
| `docs/RELEASE_CHECKLIST.md` | New — full release process checklist |

## v1.4 — GitHub Releases Pipeline & Auto Update Publishing

### Release Pipeline

- **GitHub Actions workflow**: `.github/workflows/release.yml` (manual `workflow_dispatch`)
  - Builds backend exe, frontend, desktop package
  - Runs all validations (backend tests + frontend typecheck/build + desktop build + artifact validation + smoke)
  - Uploads artifacts to GitHub Releases as a **draft** release
  - No tokens in config — uses `${{ secrets.GITHUB_TOKEN }}`
- **Local validation**: `cd desktop && npm run prepare:release` (run before committing version bump)
  - Checks version consistency across packages
  - Verifies publish config, artifact patterns, no hardcoded tokens
  - Verifies electron-updater is installed
  - Verifies backend/frontend dist exist
  - Verifies git tag matches version
- **Update metadata**: `cd desktop && npm run check:updates`
  - Validates `latest.yml` has correct version, path, sha512
  - Verifies matching installer exe exists
  - Checks for token leaks in metadata

### Auto Update Behavior

- `publishProvider` is detected at runtime via `hasPublishConfig()` (checks `package.json build.publish` for GitHub provider)
- When `publishProvider` is set: Settings panel shows "Ready to check updates" at idle
- When `publishProvider` is null (dev builds): Settings panel shows "Auto update is not configured for this build."
- `updateChannel` ("stable") is exposed in diagnostics
- `backendVersion` is fetched from `/health` at startup and shown in diagnostics
- `releaseType: "draft"` ensures no automatic notifications to subscribers

### Files Changed (v1.4)

| File | Change |
|---|---|
| `.github/workflows/release.yml` | New — GitHub Actions release workflow |
| `desktop/package.json` | Updated publish from null to GitHub Releases config; added scripts |
| `desktop/main.js` | Added `hasPublishConfig()`, `publishProvider`/`updateChannel` to getAppInfo; improved update:check handler |
| `desktop/preload.js` | No changes needed (already proxies getAppInfo) |
| `desktop/scripts/prepare_release.js` | New — pre-build validation (version, config, tokens, deps, dist) |
| `desktop/scripts/check_update_metadata.js` | New — validates latest.yml, sha512, artifacts |
| `frontend/src/desktop.d.ts` | Added `publishProvider`, `updateChannel` to getAppInfo type; `version` to getBackendHealth type |
| `frontend/src/components/SettingsPanel.tsx` | Added publish provider, update channel, backend version to diagnostics; dynamic update status message |
| `backend/tests/test_distribution.py` | New — 5 test classes for publish config, metadata, updater state, artifacts, workflow |
| `docs/RELEASE_CHECKLIST.md` | Updated with workflow steps, required secrets, SmartScreen warning, update metadata |

## v1.5 — Code Signing & Windows Trust Preparation

### Signing Overview

KeoBot can be built in three signing modes:

| Mode | Description | Env vars required |
|------|-------------|-------------------|
| `dev` | Local development — unsigned, no signing config needed | None |
| `unsigned-release` | CI release without signing — works, SmartScreen warns | None (default) |
| `signed-release` | CI release with Authenticode signing | `CSC_LINK` + `CSC_KEY_PASSWORD` or Azure vars |

### Signing Environment Variables

**PFX certificate (traditional):**
- `CSC_LINK` — path or base64-encoded PFX file (cross-platform)
- `CSC_KEY_PASSWORD` — PFX password
- `WIN_CSC_LINK` — Windows-specific PFX override
- `WIN_CSC_KEY_PASSWORD` — Windows-specific PFX password

**Azure Trusted Signing:**
- `AZURE_TENANT_ID` — Azure AD tenant ID
- `AZURE_CLIENT_ID` — Azure AD app registration client ID
- `AZURE_CLIENT_SECRET` — client secret
- `AZURE_TRUSTED_SIGNING_ACCOUNT_NAME` — Trusted Signing account name
- `AZURE_TRUSTED_SIGNING_CERT_PROFILE_NAME` — certificate profile name
- `AZURE_TRUSTED_SIGNING_ENDPOINT` — regional endpoint (optional)

**Mode control:**
- `RELEASE_MODE` — `dev`, `unsigned-release`, or `signed-release`
- `FORCE_CODE_SIGNING` — `true`/`false`; fails build if signing not available
- `REQUIRE_SIGNED_ARTIFACTS` — `true`/`false`; fails verification if artifacts unsigned

### Scripts

| Script | Purpose |
|--------|---------|
| `npm run check:signing` | Detects signing env vars safely (no secrets printed) |
| `npm run verify:signature` | Checks Authenticode signature on Windows using `Get-AuthenticodeSignature` |
| `npm run validate:signing` | Runs both check + verify |
| `npm run release:signed` | Build with `FORCE_CODE_SIGNING=true` |
| `npm run validate:artifacts` | Now also checks: cert files, signing secrets, .env in packaged resources, signing config |

### Signature Verification

- On Windows, uses PowerShell `Get-AuthenticodeSignature` to verify installer/portable exes
- Reports: `SIGNED`, `NOT SIGNED`, or `VERIFIER NOT AVAILABLE`
- Does **not** fail unsigned dev builds by default
- Fails only when `REQUIRE_SIGNED_ARTIFACTS=true`
- Safe to run cross-platform (gracefully reports verifier unavailable)

### Diagnostics

- Settings → Diagnostics & About now shows:
  - **Release mode**: `dev`, `unsigned-release`, or `signed-release`
  - **Signed build**: `Yes`/`No` (detected from signing env vars)
- Certificate details are never exposed

### GitHub Actions Changes

- New workflow input: `signed` (boolean, default false)
- When `signed=true`: sets `FORCE_CODE_SIGNING=true`, passes signing secrets, runs signature verification
- When `signed=false`: builds unsigned, skips verification
- Signing secrets read from GitHub Secrets — never logged or committed
- New step: `Check signing config` (runs before build)
- New step: `Verify Windows signatures` (runs after signed build)

### SmartScreen

- Signing with a valid OV/EV code signing certificate improves trust
- SmartScreen reputation still requires time and download volume — signing alone is not instant trust
- Certificate files must **never** be committed to the repository
- See `docs/RELEASE_CHECKLIST.md` for the full signing/release process

### Files Changed (v1.5)

| File | Change |
|---|---|
| `desktop/package.json` | Added `check:signing`, `verify:signature`, `release:signed`, `validate:signing` scripts |
| `desktop/main.js` | Added `hasSigningConfig()`, `signedBuild`, `releaseMode` to `getAppInfo` IPC |
| `desktop/scripts/check_signing_config.js` | New — safe signing env detection (no secrets printed) |
| `desktop/scripts/verify_windows_signature.js` | New — Authenticode verification using PowerShell |
| `desktop/scripts/validate_release_artifacts.js` | Extended: cert file scan, signing secret leak scan, .env in packaged resources, signing config check |
| `.github/workflows/release.yml` | Added `signed` input, signing config check, signed/unsigned build branches, signature verification |
| `frontend/src/desktop.d.ts` | Added `releaseMode`, `signedBuild` to `getAppInfo` type |
| `frontend/src/components/SettingsPanel.tsx` | Added release mode and signed build status to diagnostics |
| `README.md` | Added v1.5 code signing section |
| `desktop/README.md` | Added signing overview, env vars, scripts |
| `docs/RELEASE_CHECKLIST.md` | Added signing section, code signing options, verification steps |
| `backend/tests/test_distribution.py` | Updated: signing config tests |
