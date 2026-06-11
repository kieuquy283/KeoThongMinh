# Kẹo Thông Minh Desktop

Electron shell for packaging the Kẹo Thông Minh voice MVP as a Windows desktop app.

## Status

The desktop main process already handles backend lifecycle startup, backend health checking, and loading the frontend in dev and packaged modes.

The release build expects the backend to be packaged in `onedir` form at:

```text
resources/backend/keobot_backend/keobot_backend.exe
```

## Hands-free Assistant v1.0

The Electron shell now provides a complete hands-free foundation:

- **System tray** icon with: Show Kẹo Thông Minh, Start Listening, Toggle Wake Word, Open Settings, Quit.
- **Global hotkey** (default `Ctrl+Shift+K`) starts listening; works even while the window is hidden.
- **Hotkey can be disabled** in Settings; unregisters/registers dynamically.
- **Closing/minimizing** the window hides it to tray (when `BACKGROUND_ASSISTANT_ENABLED` is on).
- **Wake word** is handled locally in the frontend renderer via the Web Speech API.
- **No continuous audio** is sent to the backend before wake-word activation.
- **If wake word is unsupported**, the global hotkey remains the fallback; the UI shows a clear message.
- **Reminders** still poll while the window is hidden and show native OS notifications.
- **Start with Windows** via `app.setLoginItemSettings()`; works only in packaged mode (dev shows a warning).

### main.js hotkey logic

- Hotkey registration/unregistration respects the `HOTKEY_ENABLED` setting.
- Settings changes trigger re-registration through `saveSettingsToDisk()`.
- `unregisterGlobalHotkeys()` is called on quit to clean up.

## Local Wake Word Engine v1.1

The desktop app now supports three wake word engines:

| Engine | Mode | Description |
|--------|------|-------------|
| `web_speech` | Renderer | Uses Web Speech API (previous v1.0 behavior) |
| `local` | Main process | Uses Porcupine by Picovoice, runs in Electron main |
| `hotkey_only` | None | Disables wake word listening; hotkey fallback only |

The **local engine** runs Porcupine (`@picovoice/porcupine-node`) in the Electron main process with `@picovoice/pvrecorder-node` for audio capture. The renderer receives only safe IPC status events — no raw audio or model data is exposed.

- Requires a **Picovoice access key** from https://console.picovoice.ai/.
- Uses the built-in `porcupine` keyword by default, or a custom `.ppn` keyword file.
- Sensitivity is configurable (0.0–1.0, default 0.5).
- Hotkey fallback remains available regardless of engine choice.

### `localWakeWord.js`

`desktop/localWakeWord.js` exports `createLocalWakeWordService()` which returns `{ start, stop, getStatus, isAvailable }`:
- `start({ accessKey, keywordPath, sensitivity })` — initializes Porcupine, starts audio capture, polls for detection.
- `stop()` — stops capture and releases Porcupine.
- `getStatus()` — returns `{ status, phrase }` (one of `off`, `starting`, `listening_for_wake_word`, `wake_word_detected`, `error`, `unavailable`).
- `isAvailable()` — returns `false` if Porcupine modules could not be loaded.

### IPC channels (new in v1.1)

| Channel | Direction | Payload |
|---------|-----------|---------|
| `localWakeWord:start` | Renderer → Main | Invoke; returns `{ ok, error? }` |
| `localWakeWord:stop` | Renderer → Main | Invoke; returns `{ ok }` |
| `localWakeWord:getStatus` | Renderer → Main | Invoke; returns `{ status, phrase }` |
| `localWakeWord:statusChanged` | Main → Renderer | Event; `{ status, phrase }` |

### Default settings (new in v1.1)

| Key | Default | Description |
|-----|---------|-------------|
| `WAKE_WORD_ENGINE` | `web_speech` | Engine: `local`, `web_speech`, or `hotkey_only` |
| `LOCAL_WAKE_WORD_ENABLED` | `false` | Enable local wake word engine |
| `PICOVOICE_ACCESS_KEY` | `""` | Picovoice access key (required for local engine) |
| `PORCUPINE_KEYWORD_PATH` | `""` | Path to `.ppn` file (empty = built-in `porcupine`) |
| `LOCAL_WAKE_SENSITIVITY` | `0.5` | Detection sensitivity 0.0–1.0 |
| `HOTKEY_ENABLED` | `true` | Enable the global hotkey |
| `HOTKEY_VALUE` | `Ctrl+Shift+K` | Hotkey accelerator |
| `HANDSFREE_AUTO_RETURN_TO_WAKE_MODE` | `true` | Return to wake mode after response |
| `WAKE_WORD_ENABLED` | `false` | Enable wake word listening |
| `WAKE_WORD_PHRASES` | `["keobot oi", "nay keobot", "hey keobot"]` | Wake phrases |
| `START_WITH_WINDOWS` | `false` | Register at Windows login |
| `BACKGROUND_ASSISTANT_ENABLED` | `true` | Keep running in background |

### Mic lifecycle safety

- Wake word (Web Speech API or Porcupine) and recording (MediaRecorder) use separate APIs.
- When wake word is detected, it is stopped before recording starts.
- After recording + response playback, wake word restarts if enabled.
- Manual recording does not interfere with wake word listening.
- On app quit, all listeners are cleaned up.

### Known limitations

- Porcupine Node SDK uses native addons; require `@electron/rebuild` for packaging.
- Built-in keyword is English `porcupine`; custom Vietnamese keyword requires a `.ppn` file from Picovoice Console.
- Microphone permission is still required.
- The hotkey can conflict with other apps.
- The backend remains request/response; there is no full realtime streaming.

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
- Portable output: `KeoThongMinh-Portable-v0.3.0.exe`
- Installer output: `KeoThongMinh-Setup-v0.3.0.exe`
- Smoke test: `npm run smoke:packaged`

## Desktop Settings

Desktop settings are stored at the existing `%APPDATA%/KeoBot/config.json` compatibility path.

- API keys are never committed.
- API keys are never bundled into the app.
- After changing settings, restart Kẹo Thông Minh to apply them if backend restart is not exposed.
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
- After Kẹo Thông Minh finishes speaking, the app returns to listening automatically until stopped.

## Reminders

- Reminders are stored locally in the backend SQLite database.
- Notifications appear while the desktop app is running, even when the window is hidden to tray.
- Due reminders are polled from the local backend on a timer.

## Known Limitations

- Auto conversation is near-realtime, not full streaming realtime.
- It depends on Windows microphone permission and Chromium `MediaRecorder` behavior.
- Silence threshold can require tuning for different microphones.
- Interrupt support only stops local playback or aborts the current request before the backend returns.
- Weather and search require provider/API-key configuration before Kẹo Thông Minh can answer live questions.
- When a tool is not configured, Kẹo Thông Minh should report that clearly instead of inventing data.
- Currency can still answer with a demo rate when live exchange-rate configuration is missing.
- Memory is local-only and does not sync to cloud storage.
