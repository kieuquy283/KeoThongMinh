# Kiến trúc & Codebase Map - Kẹo Thông Minh

> Tài liệu này giúp bạn hiểu codebase qua các sơ đồ phụ thuộc (dependency graph), luồng dữ liệu, và ánh xạ file-chức năng.

---

## 1. Tổng quan Kiến trúc 3 Tầng

```
┌─────────────────────────────────────────────────────────────┐
│  TẦNG 1: DESKTOP SHELL (Electron)                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │  main.js         │  │  preload.js      │  │  Tray/Hotkey│  │
│  │  (Main Process)  │  │  (IPC Bridge)    │  │  (Services) │  │
│  └────────┬────────┘  └────────┬────────┘  └──────┬──────┘  │
│           │                    │                    │        │
│           └────────────────────┴────────────────────┘        │
│                          │ IPC                                │
└──────────────────────────┼────────────────────────────────────┘
                           │
┌──────────────────────────┼────────────────────────────────────┐
│  TẦNG 2: FRONTEND (React + Vite)                            │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    App.tsx (Orchestrator)               │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │ │
│  │  │VoiceRecorder│  │  ChatPanel  │  │AnimatedMascot   │ │ │
│  │  │  (Controls) │  │  (Display)  │  │  (Visual)       │ │ │
│  │  └──────┬──────┘  └─────────────┘  └─────────────────┘ │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │ │
│  │  │SettingsPanel│  │KnowledgePanel│  │ReminderPanel   │ │ │
│  │  │  (Config)   │  │  (Docs)      │  │  (Alarms)      │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘ │ │
│  │                                                         │ │
│  │  HOOKS: useAutoVoiceConversation │ useWakeWord          │ │
│  │          useSilenceDetection     │ audioPlaybackController│ │
│  └─────────────────────────────────────────────────────────┘ │
│                          │ HTTP/Fetch                       │
└──────────────────────────┼────────────────────────────────────┘
                           │
┌──────────────────────────┼────────────────────────────────────┐
│  TẦNG 3: BACKEND (FastAPI + Python)                         │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    main.py (HTTP Router)                │ │
│  │  /voice-chat  │  /text-chat  │  /health  │  /memory    │ │
│  │  /reminders   │  /knowledge  │  /tools   │  /streaming │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│  ┌───────────────────────┴──────────────────────────────────┐ │
│  │              SERVICES (Business Logic)                    │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │ │
│  │  │chat_flow.py │ │tool_router.py│ │entity_extractor.py │ │ │
│  │  │(Orchestrate)│ │(Route Intents)│ │(Parse Entities)     │ │ │
│  │  └──────┬──────┘ └──────┬──────┘ └──────────┬──────────┘ │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │ │
│  │  │stream_manager│ │replanner.py │ │conversation_context│ │ │
│  │  │(Sessions)    │ │(Replan)      │ │(History)            │ │ │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘ │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │ │
│  │  │memory_store │ │reminder_store│ │knowledge_store      │ │ │
│  │  │(SQLite)     │ │(SQLite)      │ │(FTS5)               │ │ │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│  ┌───────────────────────┴──────────────────────────────────┐ │
│  │              PROVIDERS (AI Adapters)                      │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │ │
│  │  │llm.py       │ │llm_stream.py │ │stt.py               │ │ │
│  │  │(OpenAI/     │ │(Streaming)    │ │(Speech-to-Text)     │ │ │
│  │  │ Gemini/Qwen)│ │              │ │                     │ │ │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘ │ │
│  │  ┌─────────────┐ ┌──────────────────────────────────┐ │ │
│  │  │tts.py       │ │(Edge TTS - vi-VN-HoaiMyNeural)     │ │ │
│  │  └─────────────┘ └──────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│  ┌───────────────────────┴──────────────────────────────────┐ │
│  │              TOOLS (Real-world Data)                      │ │
│  │  time_tool.py │ weather_tool.py │ currency_tool.py       │ │
│  │  search_tool.py│ source_utils.py │                        │ │
│  └─────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

---

## 2. Dependency Graph - Backend Services

```
main.py
│
├── chat_flow.py ◄─────────────────────────────────────────┐
│   │                                                      │
│   ├── llm.py / llm_stream.py ◄────────────────────┐      │
│   │   │                                             │      │
│   │   ├── config.py ◄────────────────────┐          │      │
│   │   │   │                              │          │      │
│   │   │   └── data_paths.py              │          │      │
│   │   │                                  │          │      │
│   │   ├── schemas.py                     │          │      │
│   │   │                                  │          │      │
│   │   └── openai / google.generativeai   │          │      │
│   │                                      │          │      │
│   ├── tool_router.py ◄───────────────────┤          │      │
│   │   │                                  │          │      │
│   │   ├── entity_extractor.py ◄─────────┐│          │      │
│   │   │   │                             ││          │      │
│   │   │   └── config.py                 ││          │      │
│   │   │                                 ││          │      │
│   │   └── schemas.py                    ││          │      │
│   │                                     ││          │      │
│   ├── replanner.py ◄────────────────────┤          │      │
│   │   │                                 ││          │      │
│   │   ├── llm.py (for LLM-based)        ││          │      │
│   │   ├── event_bus.py                  ││          │      │
│   │   ├── memory_store.py               ││          │      │
│   │   └── stream_manager.py             ││          │      │
│   │                                     ││          │      │
│   ├── stream_manager.py ◄───────────────┤          │      │
│   │   │                                 ││          │      │
│   │   └── event_bus.py                  ││          │      │
│   │                                     ││          │      │
│   ├── conversation_context.py ◄─────────┤          │      │
│   │   │                                 ││          │      │
│   │   └── schemas.py                    ││          │      │
│   │                                     ││          │      │
│   ├── memory_store.py ◄─────────────────┐│          │      │
│   │   │                                 ││          │      │
│   │   ├── data_paths.py                 ││          │      │
│   │   └── schemas.py                    ││          │      │
│   │                                     ││          │      │
│   ├── reminder_store.py ◄───────────────┤│          │      │
│   │   │                                 ││          │      │
│   │   ├── data_paths.py                 ││          │      │
│   │   └── schemas.py                    ││          │      │
│   │                                     ││          │      │
│   ├── knowledge_store.py ◄────────────┤│          │      │
│   │   │                                 ││          │      │
│   │   ├── data_paths.py                 ││          │      │
│   │   ├── text_chunker.py               ││          │      │
│   │   └── document_importer.py          ││          │      │
│   │                                     ││          │      │
│   └── voice_chat.py ◄───────────────────┤          │      │
│       │                                 ││          │      │
│       ├── chat_flow.py ─────────────────┘│          │      │
│       ├── tts.py ◄───────────────────────┘          │      │
│       │   │                                          │      │
│       │   ├── config.py                              │      │
│       │   └── edge_tts (library)                     │      │
│       │                                              │      │
│       ├── stt.py ◄───────────────────────────────────┘      │
│       │   │                                                  │
│       │   ├── config.py                                      │
│       │   └── openai                                         │
│       │                                                      │
│       └── schemas.py                                         │
│                                                              │
├── event_bus.py ◄─────────────────────────────────────────────┘
│   │
│   └── Used by: chat_flow, stream_manager, replanner, voice_session_manager
│
├── voice_session_manager.py
│   │
│   └── Used by: main.py (WebSocket /voice-chat)
│
├── reminder_checker.py
│   │
│   └── Used by: main.py (background polling)
│
├── tools/
│   ├── time_tool.py ──► zoneinfo (stdlib)
│   ├── weather_tool.py ──► requests (external API)
│   ├── currency_tool.py ──► requests (external API)
│   ├── search_tool.py ──► requests (external API)
│   └── source_utils.py ──► (formatting utilities)
│
└── config.py
    │
    └── dotenv, os, pathlib ──► .env file
```

---

## 3. Dependency Graph - Frontend

```
main.tsx
│
└── App.tsx ◄─────────────────────────────────────────────────────────┐
    │                                                               │
    ├── api.ts ──► HTTP calls to backend (127.0.0.1:8000)           │
    │                                                               │
    ├── components/                                                 │
    │   ├── VoiceRecorder.tsx ◄─────────────────────────────────────┤
    │   │   │                                                       │
    │   │   ├── api.ts                                              │
    │   │   ├── hooks/useAutoVoiceConversation.ts ◄───────────────┤
    │   │   │   │                                                   │
    │   │   │   ├── api.ts                                          │
    │   │   │   ├── hooks/useSilenceDetection.ts                  │
    │   │   │   ├── utils/audioPlaybackController.ts ◄────────────┤
    │   │   │   │   │                                               │
    │   │   │   │   └── utils/diagnostics.ts                      │
    │   │   │   └── types.ts                                      │
    │   │   │                                                       │
    │   │   ├── utils/voiceSessionState.ts                        │
    │   │   └── types.ts                                          │
    │   │                                                           │
    │   ├── ChatPanel.tsx                                           │
    │   │   └── types.ts                                            │
    │   │                                                           │
    │   ├── KeoBotAnimatedMascot.tsx ◄────────────────────────────┤
    │   │   │                                                       │
    │   │   └── utils/keobotMascotState.ts                          │
    │   │                                                           │
    │   ├── SettingsPanel.tsx                                       │
    │   │   └── settings.ts                                         │
    │   │                                                           │
    │   ├── KnowledgePanel.tsx                                      │
    │   │   └── api.ts                                              │
    │   │                                                           │
    │   ├── MemoryPanel.tsx                                         │
    │   │   └── api.ts                                              │
    │   │                                                           │
    │   ├── ReminderPanel.tsx                                       │
    │   │   └── api.ts                                              │
    │   │                                                           │
    │   └── ReminderToast.tsx                                       │
    │                                                               │
    ├── hooks/                                                      │
    │   ├── useWakeWord.ts ◄────────────────────────────────────────┤
    │   │   │                                                       │
    │   │   └── utils/audioPlaybackController.ts                    │
    │   │                                                           │
    │   ├── useAutoVoiceConversation.ts (see above)                 │
    │   │                                                           │
    │   └── useSilenceDetection.ts                                  │
    │                                                               │
    ├── utils/                                                      │
    │   ├── audioPlaybackController.ts ──► (Central audio state)    │
    │   ├── diagnostics.ts ──► (Logging to desktop)               │
    │   ├── keobotMascotState.ts ──► (State → mascot mapping)    │
    │   └── voiceSessionState.ts ──► (Session state logic)        │
    │                                                               │
    ├── types.ts ──► (All TypeScript interfaces)                    │
    │                                                               │
    ├── settings.ts ──► (Default settings)                          │
    │                                                               │
    └── desktop.d.ts ──► (Electron IPC type definitions)          │
                                                                    │
    IPC (Electron) ──► window.keobotDesktop ──► desktop/preload.js  │
                                                                    │
    desktop/preload.js ──► desktop/main.js ──► System Commands      │
```

---

## 4. Dependency Graph - Desktop (Electron)

```
desktop/main.js (Main Process)
│
├── electron (app, BrowserWindow, ipcMain, globalShortcut, Tray, Notification)
├── http (create backend HTTP server proxy)
├── child_process (spawn backend.exe)
├── fs / path (file system)
├── ./preload.js (IPC bridge)
├── ./services/logger.js ──► (Structured logging)
├── ./services/tray.js ──► (System tray icon)
├── ./services/hotkey.js ──► (Global hotkey Ctrl+Shift+K)
├── ./localWakeWord.js ──► (Local wake word engine)
└── ./package.json

desktop/preload.js (Renderer Bridge)
│
├── electron (contextBridge, ipcRenderer)
│
└── Exposes: window.keobotDesktop
    ├── getSettings / saveSettings
    ├── getStartWithWindows / setStartWithWindows
    ├── requestStartListening / requestStopListening
    ├── openSettings
    ├── notifyWakeWordDetected / notifyWakeWordStatus
    ├── startLocalWakeWord / stopLocalWakeWord
    ├── getLocalWakeWordStatus
    ├── exportMemory / importMemory / resetPersonalData
    ├── getAppInfo / getBackendHealth
    ├── logDiagnostic / openLogsFolder
    ├── checkForUpdates / downloadUpdate / quitAndInstall
    ├── chooseKnowledgeFiles
    ├── executeSystemCommand ──► (PowerShell/node-powershell)
    └── cancelSystemCommand
```

---

## 5. Luồng Dữ liệu Chi tiết

### 5.1. Voice Chat (Auto Conversation)

```
[User] Nói: "Kẹo Thông Minh ơi, bây giờ là mấy giờ?"
  │
  ▼
[Browser] MediaRecorder ──► Blob (webm/opus)
  │
  ▼
[Frontend] VoiceRecorder ──► useAutoVoiceConversation
  │                            │
  │                            ├── useSilenceDetection (RMS)
  │                            │      └── Auto submit khi im lặng
  │                            │
  │                            └── api.ts: sendVoiceChat(audio)
  │
  ▼
[Backend] POST /voice-chat
  │
  ├── voice_chat.py: run_voice_chat()
  │   │
  │   ├── stt.py: transcribe_audio()
  │   │   └── "Kẹo Thông Minh ơi bây giờ là mấy giờ"
  │   │
  │   ├── chat_flow.py: generate_chat_response()
  │   │   │
  │   │   ├── 1. entity_extractor.py: extract_entities()
  │   │   │      └── intent="time", location="", timezone=""
  │   │   │
  │   │   ├── 2. memory_store.py: get_memory_context()
  │   │   │      └── { user_name: "Quý", default_timezone: "Asia/Ho_Chi_Minh" }
  │   │   │
  │   │   ├── 3. tool_router.py: detect_tool_intent()
  │   │   │      └── intent="time", confidence=0.95
  │   │   │
  │   │   ├── 4. _run_tool() ──► time_tool.py: get_time_info()
  │   │   │      └── { location: "Hồ Chí Minh", formatted_time: "14:30" }
  │   │   │
  │   │   ├── 5. llm.py: generate_keobot_tool_response()
  │   │   │      └── "Bây giờ ở Hồ Chí Minh là 14:30"
  │   │   │
  │   │   └── 6. _build_sources() ──► [time_tool]
  │   │
  │   ├── tts.py: synthesize_speech()
  │   │   └── edge_tts ──► /static/audio/abc123.mp3
  │   │
  │   └── Return: { audio_url, bot_text, emotion, sources }
  │
  ▼
[Frontend] App.tsx ──► audioPlaybackController.play()
  │
  ├── KeoBotAnimatedMascot: state="speaking"
  ├── ChatPanel: add message "Bây giờ ở Hồ Chí Minh là 14:30"
  └── onended: If auto mode ──► resume listening
  │
  ▼
[Loop] Return to listening state
```

### 5.2. System Command Flow

```
[User] "Tắt máy sau 30 phút"
  │
  ▼
[Backend] chat_flow.py
  │
  ├── entity_extractor.py: _extract_system_command()
  │   └── { command: "shutdown", delay_minutes: 30 }
  │
  ├── chat_flow.py: _run_tool()
  │   └── Return: { action: "system_command", system_command: "shutdown", delay_seconds: 1800 }
  │
  ▼
[Frontend] App.tsx: detect action === "system_command"
  │
  ├── window.keobotDesktop.executeSystemCommand()
  │
  ▼
[Desktop] main.js: ipcMain.handle("keobot:executeSystemCommand")
  │
  ├── dialog.showMessageBox() ──► Confirmation dialog
  │
  ├── If confirmed: node-powershell
  │   └── shutdown /s /t 1800
  │
  └── Return: { success: true, message: "Đã lên lịch tắt máy sau 30 phút" }
  │
  ▼
[Frontend] ChatPanel: display confirmation message
```

### 5.3. Knowledge Base Query

```
[User] "Trong tài liệu có gì về AI?"
  │
  ▼
[Backend] chat_flow.py: _detect_knowledge_query()
  │   └── True (detected keywords: "tài liệu", "trong file")
  │
  ├── knowledge_store.py: query_knowledge()
  │   │
  │   ├── SQLite FTS5: MATCH "AI"
  │   │   └── [chunk1, chunk2, chunk3]
  │   │
  │   └── knowledge_query.py: rank_results()
  │       └── [chunk1 (score: 0.95), chunk2 (score: 0.87)]
  │
  ├── llm.py: generate_keobot_response()
  │   │   └── context: "Dữ liệu tài liệu: [chunk1, chunk2]"
  │   └── "Theo tài liệu của bạn, AI là... [1]"
  │
  └── _build_sources()
      └── [knowledge_source_1, knowledge_source_2]
  │
  ▼
[Frontend] ChatPanel: display response with citation numbers
```

### 5.4. Reminder Flow

```
[User] "1 phút nữa nhắc mình uống nước"
  │
  ▼
[Backend] reminder_parser.py: parse_reminder_text()
  │   └── { title: "nhắc mình uống nước", due_at: +1 minute }
  │
  ├── reminder_store.py: add_reminder()
  │   └── SQLite INSERT
  │
  └── Return: "Đã đặt nhắc nhở: nhắc mình uống nước"
  │
  ▼
[Desktop] Every 20 seconds: poll GET /reminders/due
  │
  ├── reminder_checker.py: check_due_reminders()
  │   └── Query SQLite WHERE due_at <= NOW()
  │
  └── If due: ipcMain.emit("keobot:reminderDue", reminder)
  │
  ▼
[Frontend] ReminderToast: display notification
  │
  └── App.tsx: play reminder sound + mascot "reminder" state
```

### 5.5. Memory Storage Flow

```
[User] "Từ giờ gọi mình là Quý"
  │
  ▼
[Backend] chat_flow.py
  │
  ├── memory_parser.py: parse_memory_text()
  │   └── { user_name: "Quý" }
  │
  ├── memory_store.py: set_memory()
  │   └── SQLite INSERT/UPDATE memory.sqlite3
  │
  └── Return: "Đã nhớ! Chào Quý, mình là Kẹo Thông Minh"
  │
  ▼
[Next Query] chat_flow.py: generate_chat_response()
  │
  └── memory_store.py: get_memory_context()
      └── { user_name: "Quý" }
      └── llm.py: include in system prompt
          └── "Thông tin bổ sung: user_name: Quý"
```

---

## 6. File-Chức năng Mapping

### 6.1. Backend (Python)

| File | Chức năng | Dependencies | Export |
|------|-----------|--------------|--------|
| `main.py` | HTTP Router, WebSocket, Static files | All services | FastAPI app |
| `config.py` | Settings, env vars | dotenv, data_paths | `get_settings()` |
| `schemas.py` | Pydantic models | None | 20+ models |
| `data_paths.py` | Data directory paths | pathlib | `get_data_root()` |
| **PROVIDERS** ||||
| `llm.py` | LLM chat/tool/summary | openai, google.generativeai | `generate_keobot_response()` |
| `llm_stream.py` | Streaming LLM | llm.py | `stream_keobot_response()` |
| `stt.py` | Speech-to-Text | openai | `transcribe_audio()` |
| `tts.py` | Text-to-Speech | edge_tts | `synthesize_speech()` |
| **SERVICES** ||||
| `chat_flow.py` | Main orchestration | providers, tools, stores | `generate_chat_response()` |
| `tool_router.py` | Intent routing | entity_extractor | `detect_tool_intent()` |
| `entity_extractor.py` | Entity parsing | config, schemas | `extract_entities()` |
| `replanner.py` | Conversation replan | llm.py, event_bus | `decide_replan()` |
| `stream_manager.py` | Session management | event_bus | `get_stream_manager()` |
| `conversation_context.py` | Chat history | schemas | `get_conversation_manager()` |
| `memory_store.py` | User preferences | data_paths, schemas | `get_memory_store()` |
| `memory_parser.py` | Parse memory commands | None | `parse_memory_text()` |
| `reminder_store.py` | Reminder storage | data_paths, schemas | `get_reminder_store()` |
| `reminder_parser.py` | Parse reminder text | None | `parse_reminder_text()` |
| `reminder_checker.py` | Check due reminders | reminder_store | `run_reminder_checker_loop()` |
| `knowledge_store.py` | Document index | data_paths, text_chunker | `get_knowledge_store()` |
| `knowledge_query.py` | Search & rank | knowledge_store | `query_knowledge()` |
| `document_importer.py` | Import documents | knowledge_store, text_chunker | `import_document()` |
| `text_chunker.py` | Text splitting | None | `chunk_text()` |
| `embedding_provider.py` | Text embeddings | None | (Future) |
| `vector_store.py` | Vector DB | None | (Future) |
| `event_bus.py` | Pub/sub events | None | `get_event_bus()` |
| `voice_chat.py` | Voice chat pipeline | chat_flow, stt, tts | `run_voice_chat()` |
| `voice_session_manager.py` | Session lifecycle | None | `create_session()` |
| `async_tool_executor.py` | Async tool runner | None | `AsyncToolExecutor` |
| `stability.py` | Stability checks | None | (Health checks) |
| **TOOLS** ||||
| `time_tool.py` | Time queries | zoneinfo | `get_time_info()` |
| `weather_tool.py` | Weather queries | requests | `get_weather_info()` |
| `currency_tool.py` | Exchange rates | requests | `get_currency_info()` |
| `search_tool.py` | Web search | requests | `get_search_info()` |
| `source_utils.py` | Source formatting | None | `format_sources()` |

### 6.2. Frontend (TypeScript/React)

| File | Chức năng | Dependencies | Export |
|------|-----------|--------------|--------|
| `App.tsx` | Main orchestrator | All components, hooks | `App` component |
| `main.tsx` | Entry point | App.tsx | React root |
| `types.ts` | All interfaces | None | 30+ types |
| `desktop.d.ts` | IPC types | None | Type declarations |
| `settings.ts` | Default settings | types.ts | `DEFAULT_SETTINGS` |
| `api.ts` | HTTP API client | None | `sendVoiceChat()`, `fetchReminders()` |
| **COMPONENTS** ||||
| `VoiceRecorder.tsx` | Recording controls | useAutoVoiceConversation | `VoiceRecorder` |
| `ChatPanel.tsx` | Message display | types.ts | `ChatPanel` |
| `KeoBotAnimatedMascot.tsx` | Visual mascot | keobotMascotState | `KeoBotAnimatedMascot` |
| `KeoBotMascot.tsx` | Legacy mascot | types.ts | `KeoBotMascot` |
| `SettingsPanel.tsx` | Settings UI | settings.ts | `SettingsPanel` |
| `KnowledgePanel.tsx` | Document manager | api.ts | `KnowledgePanel` |
| `MemoryPanel.tsx` | Memory viewer | api.ts | `MemoryPanel` |
| `ReminderPanel.tsx` | Reminder list | api.ts | `ReminderPanel` |
| `ReminderToast.tsx` | Toast notification | types.ts | `ReminderToast` |
| `PrivacyNotice.tsx` | Privacy info | None | `PrivacyNotice` |
| `KeoBot3D.tsx` | 3D avatar (future) | three.js | `KeoBot3D` |
| `useLipSync.ts` | Lip sync hook | Web Audio API | `useLipSync` |
| **HOOKS** ||||
| `useAutoVoiceConversation.ts` | Auto conversation | useSilenceDetection, api.ts | `useAutoVoiceConversation` |
| `useWakeWord.ts` | Wake word detection | audioPlaybackController | `useWakeWord` |
| `useSilenceDetection.ts` | Audio analysis | Web Audio API | `useSilenceDetection` |
| **UTILS** ||||
| `audioPlaybackController.ts` | Audio state | diagnostics | `play()`, `stop()`, `subscribe()` |
| `diagnostics.ts` | Logging | desktop.d.ts | `logDiagnostic()` |
| `keobotMascotState.ts` | State mapping | types.ts | `mapAppStateToMascot()` |
| `voiceSessionState.ts` | Session logic | types.ts | `voiceStatusToSessionState()` |

### 6.3. Desktop (JavaScript/Node.js)

| File | Chức năng | Dependencies | Export |
|------|-----------|--------------|--------|
| `main.js` | Main process | electron, all services | `main()` |
| `preload.js` | IPC bridge | electron | `window.keobotDesktop` |
| `localWakeWord.js` | Local wake word | None | `createLocalWakeWordService()` |
| **SERVICES** ||||
| `logger.js` | Structured logging | fs, path | `Logger` class |
| `tray.js` | System tray | electron | `createTray()` |
| `hotkey.js` | Global hotkey | electron | `registerHotkey()` |
| **SCRIPTS** ||||
| `check_signing_config.js` | Signing env check | None | CLI script |
| `verify_windows_signature.js` | Signature verify | child_process | CLI script |
| `validate_release_artifacts.js` | Artifact validation | fs | CLI script |
| `prepare_release.js` | Pre-build check | None | CLI script |
| `check_update_metadata.js` | Update metadata | fs | CLI script |
| `smoke_packaged_app.js` | Smoke test | None | CLI script |

---

## 7. Sơ đồ Trạng thái (State Machine)

### 7.1. Voice Session State

```
                        ┌─────────────┐
                        │    IDLE     │
                        │  (mascot:   │
                        │   idle)     │
                        └──────┬──────┘
                               │
              ┌────────────────┼────────────────┐
              │ Hotkey/Wake    │ Manual click   │ Auto mode
              │ Word triggered │                │
              ▼                ▼                ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │ LISTENING   │ │ LISTENING   │ │ LISTENING   │
        │ (mascot:    │ │ (mascot:    │ │ (mascot:    │
        │  listening) │ │  listening) │ │  listening) │
        └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
               │               │               │
               │ User speaks   │ User speaks   │ Speech detected
               ▼               ▼               ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │ RECORDING   │ │ RECORDING   │ │ RECORDING   │
        │ (mascot:    │ │ (mascot:    │ │ (mascot:    │
        │  recording) │ │  recording) │ │  recording) │
        └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
               │               │               │
               │ Stop/Submit   │ Manual stop   │ Silence detected
               ▼               ▼               ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │  UPLOADING  │ │  UPLOADING  │ │  UPLOADING  │
        │ (mascot:    │ │ (mascot:    │ │ (mascot:    │
        │  thinking)  │ │  thinking)  │ │  thinking)  │
        └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
               │               │               │
               │ HTTP POST     │ HTTP POST     │ HTTP POST
               ▼               ▼               ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │  PROCESSING │ │  PROCESSING │ │  PROCESSING │
        │ (mascot:    │ │ (mascot:    │ │ (mascot:    │
        │  thinking)  │ │  thinking)  │ │  thinking)  │
        └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
               │               │               │
               │ Response      │ Response      │ Response
               ▼               ▼               ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │  SPEAKING   │ │  SPEAKING   │ │  SPEAKING   │
        │ (mascot:    │ │ (mascot:    │ │ (mascot:    │
        │  speaking)  │ │  speaking)  │ │  speaking)  │
        └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
               │               │               │
               │ Audio ended   │ Audio ended   │ Audio ended
               │               │               │
               ▼               ▼               ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │    IDLE     │ │    IDLE     │ │ LISTENING   │
        │ (mascot:    │ │ (mascot:    │ │ (mascot:    │
        │   idle)     │ │   idle)     │ │  listening) │
        └─────────────┘ └─────────────┘ └─────────────┘
                          (Auto mode loops back)
```

### 7.2. Chat Flow Decision Tree

```
User Input (text)
  │
  ▼
┌─────────────────────┐
│ 1. Is it a memory   │ ──Yes──► memory_parser ──► store ──► return
│    command?         │
│    ("Gọi mình là")  │
└─────────────────────┘
  No
  ▼
┌─────────────────────┐
│ 2. Is it a system   │ ──Yes──► entity_extractor ──► execute command ──► return
│    command?         │
│    ("Tắt máy")      │
└─────────────────────┘
  No
  ▼
┌─────────────────────┐
│ 3. Is it a knowledge│ ──Yes──► knowledge_store ──► LLM with context ──► return
│    query?           │
│    ("Trong tài liệu")│
└─────────────────────┘
  No
  ▼
┌─────────────────────┐
│ 4. Is it a reminder │ ──Yes──► reminder_parser ──► store ──► return
│    request?         │
│    ("Nhắc mình sau")│
└─────────────────────┘
  No
  ▼
┌─────────────────────┐
│ 5. Is it a tool     │ ──Yes──► tool_router ──► run tool ──► LLM with result ──► return
│    intent?          │
│    ("Thời tiết",     │
│     "Tỷ giá")       │
└─────────────────────┘
  No
  ▼
┌─────────────────────┐
│ 6. Normal LLM       │ ──Yes──► LLM with memory + context ──► return
│    response         │
│    ("Bạn là ai?")   │
└─────────────────────┘
```

---

## 8. API Endpoints Map

```
main.py
│
├── GET /health ──► HealthResponse (version, mode, providers)
│
├── POST /voice-chat ──► VoiceChatResponse
│   ├── File: audio/webm
│   └── Process: STT → chat_flow → TTS
│
├── POST /text-chat ──► TextChatResponse
│   ├── Body: { text, session_id }
│   └── Process: chat_flow (no STT/TTS)
│
├── POST /stream-chat ──► StreamingResponse (SSE)
│   ├── Body: { text, session_id }
│   └── Process: stream_chat_response (streaming)
│
├── WebSocket /voice-chat-ws ──► Real-time streaming
│   └── Process: voice_session_manager
│
├── GET /memory ──► List[MemoryItem]
├── POST /memory ──► Set memory
├── DELETE /memory/{key} ──► Delete key
├── DELETE /memory ──► Clear all
│
├── GET /reminders ──► List[ReminderResponse]
├── POST /reminders ──► Create reminder
├── GET /reminders/due ──► List[ReminderResponse]
├── DELETE /reminders/{id} ──► Delete reminder
│
├── GET /knowledge ──► List[DocumentResponse]
├── POST /knowledge/import ──► Import documents
├── GET /knowledge/query ──► Search results
├── DELETE /knowledge/{id} ──► Delete document
│
├── GET /tools/status ──► ToolStatusResponse
├── POST /tools/test ──► Test tool execution
│
├── POST /voice-session/{id}/cancel ──► Cancel session
├── POST /voice-session/{id}/cleanup ──► Cleanup session
│
├── GET /diagnostics ──► DiagnosticsResponse
│
└── GET /static/audio/{filename} ──► Serve audio files
```

---

## 9. Database Schema

### 9.1. memory.sqlite3

```sql
CREATE TABLE memory (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Keys: user_name, preferred_form_of_address, default_city, 
--       default_timezone, default_currency, preferred_tts_voice, answer_style
```

### 9.2. reminders.sqlite3

```sql
CREATE TABLE reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    due_at TIMESTAMP NOT NULL,
    repeat_interval TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed BOOLEAN DEFAULT 0
);
```

### 9.3. knowledge.sqlite3

```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT REFERENCES documents(id),
    content TEXT NOT NULL,
    chunk_index INTEGER,
    token_count INTEGER
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
    content,
    content='chunks',
    content_rowid='id'
);
```

---

## 10. Module Interaction Matrix

| | main | config | schemas | llm | stt | tts | chat_flow | tool_router | entity | memory | reminder | knowledge | event_bus |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| main | - | ✅ | ✅ | | | | ✅ | | | ✅ | ✅ | ✅ | ✅ |
| llm | | ✅ | ✅ | - | | | | | | | | | |
| stt | | ✅ | | | - | | | | | | | | |
| tts | | ✅ | | | | - | | | | | | | |
| chat_flow | | | ✅ | ✅ | | | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| tool_router | | | ✅ | | | | | - | ✅ | | | | |
| entity | | ✅ | | | | | | | - | | | | |
| memory | | | ✅ | | | | | | | - | | | |
| reminder | | | ✅ | | | | | | | | - | | |
| knowledge | | | ✅ | | | | | | | | | - | |
| event_bus | | | | | | | | | | | | | - |

Legend: ✅ = imports/uses

---

## 11. Build & Deployment Flow

```
Development
  │
  ├── Backend: uvicorn app.main:app --reload
  │   └── http://127.0.0.1:8000
  │
  ├── Frontend: npm run dev
  │   └── http://localhost:5173
  │
  └── Desktop: npm run dev
      └── Electron → loads localhost:5173

Testing
  │
  ├── Backend: python -m pytest (417 tests)
  ├── Frontend: npm run typecheck
  └── Desktop: npm run build

Production Build
  │
  ├── 1. Build backend exe
  │   └── python scripts/build_backend_exe.py
  │   └── backend/dist/keobot_backend/keobot_backend.exe
  │
  ├── 2. Build frontend
  │   └── npm run build
  │   └── frontend/dist/
  │
  ├── 3. Build desktop
  │   └── npm run build
  │   └── desktop/dist/
  │
  ├── 4. Validate
  │   └── npm run validate:artifacts
  │
  └── 5. Release (GitHub Actions)
      └── .github/workflows/release.yml
      └── Creates: KeoThongMinh-Setup-vX.X.X.exe
                    KeoThongMinh-Portable-vX.X.X.exe
```

---

## 12. Các Pattern Kiến trúc

### 12.1. Singleton Pattern
- `config.py`: `get_settings()` (lru_cache)
- `memory_store.py`: `get_memory_store()`
- `reminder_store.py`: `get_reminder_store()`
- `knowledge_store.py`: `get_knowledge_store()`
- `event_bus.py`: `get_event_bus()`
- `stream_manager.py`: `get_stream_manager()`
- `conversation_context.py`: `get_conversation_manager()`
- `replanner.py`: `get_replanner()`

### 12.2. Strategy Pattern
- `llm.py`: Provider selection (openai, gemini, qwen, local)
- `stt.py`: Provider selection (openai, dashscope, local)
- `tool_router.py`: Tool selection (time, weather, currency, search)

### 12.3. Observer Pattern
- `event_bus.py`: Pub/sub for events (interrupt, replanning, reminder due)
- `audioPlaybackController.ts`: Subscribe/unsubscribe for playback state

### 12.4. Factory Pattern
- `document_importer.py`: File type → parser (txt, md, pdf, docx)
- `schemas.py`: Pydantic model validation

### 12.5. Adapter Pattern
- `llm.py`: `_is_qwen_provider()` → OpenAI SDK with custom base_url
- `tts.py`: Edge TTS → standardized response format

---

## 13. Từ điển Thuật ngữ

| Thuật ngữ | Ý nghĩa |
|-----------|---------|
| **STT** | Speech-to-Text (nhận diện giọng nói) |
| **LLM** | Large Language Model (mô hình ngôn ngữ lớn) |
| **TTS** | Text-to-Speech (tổng hợp giọng nói) |
| **RAG** | Retrieval-Augmented Generation (tìm kiếm + tạo văn bản) |
| **FTS5** | Full-Text Search version 5 (SQLite) |
| **IPC** | Inter-Process Communication (Electron main ↔ renderer) |
| **SSE** | Server-Sent Events (streaming từ server) |
| **MVP** | Minimum Viable Product (phiên bản tối thiểu) |
| **RMS** | Root Mean Square (đo mức âm thanh) |
| **ASR** | Automatic Speech Recognition (nhận dạng giọng nói tự động) |

---

*Document version: 1.0*  
*Last updated: 2026-06-13*  
*Kẹo Thông Minh v1.6*
