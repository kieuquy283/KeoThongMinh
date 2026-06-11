# Kẹo Thông Minh Frontend

React + Vite frontend for the Kẹo Thông Minh voice pipeline MVP.

## 2D Mascot Integration

The frontend now uses a 2D mascot asset system under `public/keobot/`.

- Primary component: `src/components/KeoBotAnimatedMascot.tsx`
- State helper: `src/utils/keobotMascotState.ts`
- Render path: `App.tsx` -> `KeoBotMascot`
- Rendering mode: React + CSS image animation only

Canonical mascot assets:

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

- `idle` -> idle or calm, with blink/breathing
- `listening` -> listening
- `thinking` -> thinking or thinking-alt
- `speaking` -> frame loop across speaking 1/2/3
- `loading` -> loading or processing
- `reminder` -> reminder
- `error` -> error or sad

Fallback behavior:

- speaking frames fall back to `speaking_1`, then idle
- thinking-alt falls back to thinking
- loading falls back to processing, then thinking
- celebrate falls back to happy
- sad falls back to error
- calm falls back to idle

This is a 2D mascot system only. It does not use Live2D, 3D avatars, or GLB runtime rendering.

## Real-world Tool Metadata

The conversation panel can now show:

- `tool_used`
- `updated_at`
- source links for search/news results
- a warning banner when a requested tool is unavailable

The Settings panel now also has a `Check tools` button that calls the backend `/tools/status` endpoint and shows whether weather/search providers are configured.
The app also has a separate Memory panel for local-only preferences.

## Hands-free Assistant v1.0

The frontend participates in the desktop hands-free system:

- Receives `handsfree:start-listening` and `handsfree:stop-listening` IPC events from Electron.
- Opens Settings from the Electron tray action.
- Shows a background/listening banner while hands-free mode is active.
- Uses browser/Electron microphone permission and `MediaRecorder`.

### Wake Word (useWakeWord)

The `useWakeWord` hook (`src/hooks/useWakeWord.ts`) supports three engines:

| Engine | Behavior |
|--------|----------|
| `web_speech` | Uses Web Speech API in renderer (v1.0 default) |
| `local` | Uses Porcupine via IPC to Electron main process |
| `hotkey_only` | Sets `supported = false`, no listening |

- **web_speech**: Uses `SpeechRecognition` / `webkitSpeechRecognition` with `lang: vi-VN`.
- **local**: Calls `window.keobotDesktop.startLocalWakeWord()` → listens to `onLocalWakeWordStatusChanged` IPC.
- All engines: Detects phrases via normalized string matching (NFD-decomposed, accent-stripped).
- Exposes: `supported`, `enabled`, `status`, `error`, `lastDetectedPhrase`, `startWakeWord()`, `stopWakeWord()`.
- Statuses: `off`, `starting`, `listening_for_wake_word`, `wake_word_detected`, `handoff_to_listening`, `unsupported`, `unavailable`, `error`.

### Wake Word Lifecycle

1. App starts → wake word begins listening in the background (if enabled).
2. Phrase matched → status becomes `wake_word_detected`.
3. Electron shows the window, renderer stops wake word, starts recording.
4. Recording finishes → backend processes → audio plays.
5. Playback ends → wake word restarts (if `HANDSFREE_AUTO_RETURN_TO_WAKE_MODE` is on).

### Fallback

- If the engine is `hotkey_only`: `supported = false`, status `off`.
- If the local engine is unavailable (Porcupine modules not loaded): status `unavailable`.
- If Web Speech API is unavailable: `supported = false`, status `unsupported`.
- UI shows: `"Wake word is not supported in this environment. Use Ctrl+Shift+K instead."`
- Hotkey fallback remains functional through Electron's global shortcut.

### Settings (New in v1.1)

| Setting | Control | Default |
|---------|---------|---------|
| `WAKE_WORD_ENABLED` | Checkbox | Off |
| `WAKE_WORD_ENGINE` | Select | `web_speech` |
| `WAKE_WORD_PHRASES` | Textarea | `Kẹo Thông Minh ơi`, `này Kẹo Thông Minh`, `hey Kẹo Thông Minh` |
| `PICOVOICE_ACCESS_KEY` | Password input (shown when engine=local) | `""` |
| `PORCUPINE_KEYWORD_PATH` | Text input (shown when engine=local) | `""` |
| `LOCAL_WAKE_SENSITIVITY` | Range slider 0–1 (shown when engine=local) | `0.5` |
| `HOTKEY_ENABLED` | Checkbox | On |
| `HOTKEY_VALUE` | Read-only input | `Ctrl+Shift+K` |
| `HANDSFREE_AUTO_RETURN_TO_WAKE_MODE` | Checkbox | On |
| `START_WITH_WINDOWS` | Checkbox | Off |
| `BACKGROUND_ASSISTANT_ENABLED` | Checkbox | On |

### Provider Strip Indicators

The provider strip at the top of the app now shows:
- Wake: On/Off
- Engine: web_speech / local / hotkey_only
- Wake status (idle / listening / detected / unsupported / unavailable)
- Hotkey value or "Off" if disabled
- Auto wake mode status
- Background mode status

### Known Limitations

- Porcupine native modules require `@electron/rebuild` for packaged builds.
- Built-in keyword is English `porcupine`; custom keyword requires `.ppn` file from Picovoice Console.
- No continuous audio is sent to the backend before wake activation.

## Lightweight Local Memory v0.9.0

Memory is separate from Settings.

- Settings stores provider choices and API keys.
- Memory stores explicit user preferences only.
- Memory data is stored locally in SQLite through the backend API.
- The frontend never shows API keys in the Memory panel.

Supported memory keys:

- `user_name`
- `preferred_form_of_address`
- `default_city`
- `default_timezone`
- `default_currency`
- `preferred_tts_voice`
- `answer_style`

## Setup

```bash
cd frontend
npm install
```

## Run

```bash
npm run dev
```

## Voice Modes

### Manual voice mode

- User starts recording manually.
- User stops recording manually.
- The recorded turn is uploaded to `/voice-chat`.

### Auto conversation mode

- User enables `Auto conversation`.
- The frontend keeps listening with the microphone open.
- Browser-side silence detection ends the turn automatically after speech followed by silence.
- After audio playback finishes, the frontend re-enters listening mode automatically.

## Silence Detection

The auto conversation hook uses Web Audio API RMS volume analysis with these defaults:

```ts
{
  volumeThreshold: 0.02,
  silenceMs: 1000,
  minSpeechMs: 500,
}
```

## Checks

```bash
npm run typecheck
npm run build
```

## API Base URL

The frontend defaults to `http://localhost:8000`. Override with:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## v1.3 — Diagnostics

- `src/utils/diagnostics.ts` — in-memory diagnostic event log with forwarding to main process
- `logDiagnostic()` called at voice session transitions, audio playback events, wake word detections
- Diagnostics & About section in SettingsPanel shows app version, build mode, backend health, logs folder
- Update status UI (idle/checking/update_available/update_not_available/downloading/downloaded/error)

## Known Limitations

- This is not full streaming realtime conversation.
- It depends on microphone permission, `MediaRecorder`, and browser Web Audio support.
- Silence threshold may need tuning for noisy environments.
- Cancelling a turn can stop local audio playback and abort the current HTTP request, but it does not interrupt backend streaming because the backend is still request/response.
- Weather and search answers depend on backend provider configuration.
- The frontend only displays tool metadata returned by the backend; it does not fetch real-world data directly.
- The UI does not show API keys, only provider status.
- Memory is local-only and should not be used for sensitive data.
