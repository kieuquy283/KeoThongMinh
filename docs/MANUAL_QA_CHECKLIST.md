# KeoBot Manual QA Checklist

## Prerequisites
- [ ] Backend is running (packaged exe or `python -m uvicorn ...`)
- [ ] Frontend is built or dev server is running
- [ ] Desktop app is packaged or running via `electron .`

## 1. Normal Text Chat
1. Open app
2. Type a message and send
3. Verify: bot responds with text
4. Verify: emotion changes appropriately
5. Verify: tool usage shown if applicable
6. Verify: sources shown if applicable

## 2. Normal Voice Chat
1. Click the microphone button (or use hotkey)
2. Speak a phrase
3. Wait for recording to stop (auto silence)
4. Verify: voice is sent, bot responds
5. Verify: TTS audio plays back
6. Verify: conversation panel shows user text and bot text

## 3. Stop Speaking (Manual Interrupt)
1. Ask a question that produces a long response
2. While KeoBot is speaking, click "Dừng nói" stop button
3. Verify: audio stops immediately
4. Verify: session state changes to "Đã dừng câu trả lời"
5. Verify: you can start a new recording/chat immediately after
6. Verify: mascot shows interrupted/idle state

## 4. Hotkey Interrupt
1. Set hotkey to Ctrl+Shift+K (default)
2. Start a voice chat and let KeoBot speak
3. While speaking, press Ctrl+Shift+K
4. Verify: audio stops immediately
5. Verify: new recording starts (hotkey transition to listening)

## 5. Wake Word Interrupt
1. Enable wake word in settings
2. Ensure wake word engine is running (listening)
3. Say "Kẹo Thông Minh ơi" while KeoBot is speaking
4. Verify: audio stops immediately
5. Verify: app transitions to listening state
6. Verify: you can speak a command after the wake word

## 6. Wake Resumes After Response
1. With wake word enabled, say "Kẹo Thông Minh ơi"
2. Speak a command
3. Wait for response to finish
4. Verify: wake word engine resumes listening
5. Verify: another wake word detection works

## 7. Reminder While Minimized
1. Create a reminder with `Nhắc tôi sau 1 phút`
2. Minimize the app to tray
3. Wait for reminder time
4. Verify: notification appears (Windows notification)
5. Verify: clicking notification shows the app
6. Verify: reminder shown in the reminder panel

## 8. Tray Show / Hide / Quit
1. Minimize app to tray (close button)
2. Verify: app hides, tray icon remains
3. Double-click tray icon: verify app shows
4. Open tray context menu: verify items present
5. Click "Quit" in tray menu: verify app exits completely
6. Verify: backend process also exits

## 9. Start with Windows Toggle
1. Open Settings > Background Assistant
2. Toggle "Start with Windows" on
3. Verify: setting is saved (reopen settings)
4. Toggle "Start with Windows" off
5. Verify: setting is saved

## 10. Mascot State Changes
1. Verify mascot shows idle state on startup
2. Start recording: verify listening state
3. While waiting for response: verify thinking state
4. While KeoBot speaks: verify speaking state
5. Interrupt speaking: verify idle state
6. On error: verify error state

## 11. Tools / Provider Diagnostics
1. Open Settings > Provider Health
2. Click "Check all tools"
3. Verify: status badges show for each provider
4. Click "Test" on a tool with sample query
5. Verify: test result is displayed
6. Verify: configured/unconfigured status reflects actual API key presence

## 12. App Restart
1. Close app (Quit from tray)
2. Restart app
3. Verify: settings are preserved
4. Verify: wake word state resumes (if enabled)
5. Verify: backend starts and health check passes

## 13. Packaged App Smoke
1. Run the portable `.exe` from release directory
2. Verify: backend starts (check `curl http://127.0.0.1:8000/health`)
3. Verify: main window appears
4. Verify: text chat works
5. Verify: voice chat works (if microphone available)
6. Verify: tray icon appears
7. Close app: verify backend also exits
