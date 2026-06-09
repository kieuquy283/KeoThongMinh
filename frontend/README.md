# KeoBot Frontend

React + Vite frontend for the KeoBot voice pipeline MVP.

## Real-world Tool Metadata

The conversation panel can now show:

- `tool_used`
- `updated_at`
- source links for search/news results
- a warning banner when a requested tool is unavailable

The Settings panel now also has a `Check tools` button that calls the backend `/tools/status` endpoint and shows whether weather/search providers are configured.
The app also has a separate Memory panel for local-only preferences.

## Hands-free Assistant v0.9.0

The frontend now participates in the desktop hands-free foundation:

- it can receive `handsfree:start-listening` and `handsfree:stop-listening` IPC events
- it can open Settings from an Electron tray action
- it shows a background/listening banner while hands-free mode is active
- it still uses browser/Electron microphone permission and `MediaRecorder`

Wake Word MVP:

- It can listen locally for `KeoBot ơi`, `này KeoBot`, and `hey KeoBot` when the Web Speech API is available.
- Wake-word detection stays local in the renderer until a phrase is recognized.
- The app only sends audio to `/voice-chat` after wake-word activation or a normal hotkey/listening turn.
- If wake word is unsupported in the current Electron runtime, the hotkey fallback remains available.

Known limitations:

- wake word is an MVP, not a dedicated low-power wake-word engine
- the app must already be running
- the global hotkey is registered by Electron, not by the web UI
- hotkey conflicts may happen if another app already owns `Ctrl+Shift+K`

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

## Known Limitations

- This is not full streaming realtime conversation.
- It depends on microphone permission, `MediaRecorder`, and browser Web Audio support.
- Silence threshold may need tuning for noisy environments.
- There is no wake word.
- Cancelling a turn can stop local audio playback and abort the current HTTP request, but it does not interrupt backend streaming because the backend is still request/response.
- Weather and search answers depend on backend provider configuration.
- The frontend only displays tool metadata returned by the backend; it does not fetch real-world data directly.
- The UI does not show API keys, only provider status.
- Memory is local-only and should not be used for sensitive data.
