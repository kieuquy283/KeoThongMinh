# Tổng Quan Dự Án Kẹo Thông Minh

## 1. Giới thiệu

**Kẹo Thông Minh** là một trợ lý AI tiếng Việt thông minh, thân thiện và hài hước, được thiết kế để hoạt động trên desktop Windows với khả năng tương tác bằng giọng nói và văn bản. Dự án hướng đến việc tạo ra một trợ lý cá nhân nhẹ, nhanh, hoạt động offline được, và có khả năng mở rộng.

**Phiên bản hiện tại:** v1.6  
**Ngôn ngữ chính:** Tiếng Việt (hỗ trợ Unicode đầy đủ, dấu tiếng Việt)  
**Nền tảng:** Windows (Electron desktop app)  
**Backend:** Python FastAPI  
**Frontend:** React + TypeScript + Vite

---

## 2. Kiến trúc Hệ thống

### 2.1. Tổng quan Kiến trúc

Kẹo Thông Minh sử dụng kiến trúc **3 tầng**:

```
┌─────────────────────────────────────────┐
│         Desktop App (Electron)          │
│  - React Frontend UI                     │
│  - System Tray & Global Hotkey           │
│  - Native Notifications                  │
│  - IPC Communication                     │
└─────────────────────────────────────────┘
                    │
                    │ HTTP/WebSocket
                    ▼
┌─────────────────────────────────────────┐
│         FastAPI Backend (Python)         │
│  - Voice Chat Pipeline                 │
│  - LLM Providers (OpenAI/Gemini/Qwen)    │
│  - Tool Router (Time/Weather/Search...)   │
│  - Memory & Reminder Stores (SQLite)    │
│  - Knowledge Base (FTS5)                  │
└─────────────────────────────────────────┘
                    │
                    │ API Calls
                    ▼
┌─────────────────────────────────────────┐
│         External AI Providers             │
│  - OpenAI (GPT-4o, Whisper)            │
│  - Google Gemini                        │
│  - Alibaba DashScope (Qwen)             │
│  - Edge TTS (Microsoft)                 │
└─────────────────────────────────────────┘
```

### 2.2. Các thành phần chính

| Thành phần | Công nghệ | Mô tả |
|-----------|-----------|-------|
| **Desktop App** | Electron + Node.js | Shell desktop, system tray, global hotkey, notifications |
| **Frontend UI** | React + TypeScript + Vite | Giao diện người dùng, recorder, mascot, chat panel |
| **Backend API** | FastAPI + Python 3.12 | Xử lý voice chat, tools, memory, reminders |
| **Database** | SQLite | Memory, reminders, knowledge base, conversation history |
| **STT** | OpenAI / DashScope / Mock | Speech-to-Text (nhận diện giọng nói) |
| **LLM** | OpenAI / Gemini / Qwen / Mock | Large Language Model (tạo câu trả lời) |
| **TTS** | Edge TTS / Mock | Text-to-Speech (tổng hợp giọng nói tiếng Việt) |

---

## 3. Chi tiết các Chức năng

### 3.1. Voice Chat Pipeline

Đây là chức năng cốt lõi của Kẹo Thông Minh. Luồng xử lý voice chat:

1. **Thu âm**: Browser `MediaRecorder` thu âm giọng nói tiếng Việt
2. **Upload**: Frontend gửi file audio lên backend `/voice-chat`
3. **STT**: Backend transcribe audio → text (OpenAI Whisper / Qwen ASR / Mock)
4. **Intent Detection**: Phân tích ý định người dùng (tool routing)
5. **Tool Execution**: Chạy tool nếu cần (time, weather, currency, search)
6. **LLM Response**: Tạo câu trả lời persona Kẹo Thông Minh (OpenAI / Gemini / Qwen)
7. **TTS**: Tổng hợp giọng nói `.mp3` (Edge TTS - giọng vi-VN-HoaiMyNeural)
8. **Playback**: Phát audio và hiển thị text trong chat panel

**Hai chế độ voice:**
- **Manual Mode**: Nhấn nút để thu âm, nhấn lại để gửi
- **Auto Conversation Mode**: Tự động phát hiện giọng nói, tự động gửi khi im lặng đủ lâu

### 3.2. AI Providers (Multi-Provider)

Kẹo Thông Minh hỗ trợ nhiều nhà cung cấp AI, có thể chuyển đổi qua `.env`:

| Provider | STT | LLM | Ưu điểm |
|----------|-----|-----|---------|
| **OpenAI** | Whisper (gpt-4o-mini-transcribe) | GPT-4o-mini | Chất lượng cao, ổn định |
| **Gemini (Google)** | - | Gemini 2.0 Flash | Miễn phí tier, tốc độ nhanh |
| **Qwen/DashScope** | Qwen3-ASR-Flash | Qwen3.6-plus | API giá rẻ, tiếng Việt tốt |
| **Mock/Local** | Text cố định | Rule-based | Offline, không cần API key |

**TTS duy nhất:** Edge TTS (Microsoft) với giọng `vi-VN-HoaiMyNeural`

### 3.3. Real-world Information Tools

Hệ thống tool giúp Kẹo Thông Minh trả lời câu hỏi thực tế:

| Tool | Mô tả | Provider | Fallback |
|------|-------|----------|----------|
| **Time** | Thời gian hiện tại theo múi giờ | Local (zoneinfo) | Không cần |
| **Weather** | Thời tiết theo thành phố | OpenWeatherMap | "Chưa cấu hình" |
| **Currency** | Tỷ giá ngoại tệ | Exchange Rate API | Demo rate (có cảnh báo) |
| **News Search** | Tin tức mới nhất | Tavily / SerpAPI | "Chưa cấu hình" |
| **General Search** | Tìm kiếm web | Tavily / SerpAPI | "Chưa cấu hình" |
| **System Commands** | Điều khiển máy tính | Local (Electron IPC) | Không cần |

**Routing:** Câu hỏi người dùng → `tool_router.py` → `entity_extractor.py` → chạy tool hoặc fallback LLM

### 3.4. Memory (Trí nhớ người dùng)

Hệ thống lưu trữ ưu tiên của người dùng trong SQLite:

- `user_name` - Tên người dùng
- `preferred_form_of_address` - Cách xưng hô
- `default_city` - Thành phố mặc định (cho thời tiết)
- `default_timezone` - Múi giờ mặc định
- `default_currency` - Tiền tệ mặc định
- `preferred_tts_voice` - Giọng đọc ưa thích
- `answer_style` - Phong cách trả lời (ngắn/dài)

**Ví dụ:**
- "Từ giờ gọi mình là Quý" → Kẹo Thông Minh nhớ và xưng hô đúng
- "Nhớ rằng thành phố mặc định của mình là Hà Nội" → Hỏi thời tiết không cần nói thành phố

### 3.5. Reminders (Nhắc nhở)

- Lưu nhắc nhở trong SQLite
- Desktop app polling mỗi 20 giây
- Hiển thị native notification khi đến hạn
- Hỗ trợ lặp lại (repeat interval)
- Ví dụ: "1 phút nữa nhắc mình uống nước"

### 3.6. Knowledge Base (Cơ sở tri thức)

- Import tài liệu: TXT, MD, PDF, DOCX
- Trích xuất text, chunking (700 từ), index FTS5
- Không upload cloud - hoàn toàn local
- Tra cứu bằng từ khóa tiếng Việt: "tài liệu", "trong file", "hỏi tài liệu"
- Có citation (trích dẫn nguồn) trong câu trả lời

### 3.7. System Commands (Lệnh hệ thống)

**Mới trong v1.6** - Kẹo Thông Minh có thể điều khiển máy tính qua giọng nói:

| Lệnh | Hành động | Ví dụ |
|------|-----------|-------|
| Shutdown | Tắt máy | "Tắt máy sau 30 phút" |
| Restart | Khởi động lại | "Restart máy" |
| Sleep | Ngủ đông | "Sleep 2 tiếng" |
| Open App | Mở ứng dụng | "Mở Chrome" |
| Close App | Đóng ứng dụng | "Đóng Chrome" |

- **Delay**: Hỗ trợ "phút", "tiếng", "giờ" → tính toán `delay_seconds`
- **Confirmation**: Các lệnh nguy hiểm (shutdown/restart) hiển thị dialog xác nhận
- **Cancel**: "Hủy tắt máy" để hủy lệnh đang chờ
- **Security**: Chỉ hoạt động trong desktop app qua Electron IPC

### 3.8. Hands-free Assistant (Trợ lý rảnh tay)

- **System Tray**: App chạy ngầm khi đóng cửa sổ
- **Global Hotkey**: `Ctrl+Shift+K` để bắt đầu nghe (hoạt động cả khi ẩn)
- **Wake Word**: "Kẹo Thông Minh ơi", "này Kẹo Thông Minh", "hey Kẹo Thông Minh"
  - Chạy qua Web Speech API trong renderer
  - Tự động pause 400ms sau khi phát audio để tránh self-trigger
- **Auto Return**: Tự động quay lại chế độ nghe sau khi phát xong
- **Start with Windows**: Tùy chọn khởi động cùng Windows

### 3.9. Mascot System (Nhân vật Kẹo Thông Minh)

Hệ thống mascot 2D với 22 trạng thái:

**Trạng thái cơ bản:** idle, listening, thinking, speaking, loading, error, reminder
**Trạng thái cảm xúc:** happy, sad, surprised, angry, wink, confused, sleepy, calm
**Animation:** celebrate, wave, goodbye, processing, blink

**Cải tiến v1.6:**
- Background removal: 22 assets đã xử lý bằng `rembg` (u2netp model)
- Crossfade animation: Chuyển đổi hình ảnh mượt mà (300ms opacity transition)
- Preload: Tải trước hình ảnh trước khi hiển thị

### 3.10. Replanning (Lập kế hoạch lại)

Hệ thống quyết định tiếp theo trong cuộc hội thoại:

- **Continue**: Tiếp tục câu trả lời hiện tại
- **Restart**: Người dùng chuyển chủ đề → bắt đầu lại
- **Switch Intent**: Người dùng muốn dùng tool khác
- **Ask Missing Info**: Thiếu thông tin để chạy tool

Hỗ trợ cả heuristic (rule-based) và LLM-based replanning.

### 3.11. Streaming Response

Backend hỗ trợ streaming cho LLM response:
- Token-by-token streaming qua SSE
- Hỗ trợ cancel giữa chừng
- Retry 3 lần khi API lỗi
- Timeout và error handling

---

## 4. Công nghệ sử dụng

### 4.1. Backend

| Công nghệ | Phiên bản | Mục đích |
|-----------|-----------|----------|
| Python | 3.12 | Ngôn ngữ chính |
| FastAPI | Latest | Web framework |
| SQLite | Built-in | Database |
| FTS5 | Built-in | Full-text search (Knowledge Base) |
| OpenAI SDK | Latest | GPT-4o, Whisper API |
| Google Generative AI | Latest | Gemini API |
| Edge TTS | Latest | Text-to-Speech tiếng Việt |
| Pydantic | Latest | Data validation |
| Pytest | Latest | Testing |
| Uvicorn | Latest | ASGI server |

### 4.2. Frontend

| Công nghệ | Phiên bản | Mục đích |
|-----------|-----------|----------|
| React | 18 | UI framework |
| TypeScript | 5.x | Type safety |
| Vite | 5.x | Build tool |
| Electron | Latest | Desktop shell |
| Web Speech API | Native | Wake word detection |
| Web Audio API | Native | Silence detection, RMS analysis |
| MediaRecorder | Native | Audio recording |

### 4.3. Desktop

| Công nghệ | Mục đích |
|-----------|----------|
| Electron | Desktop app shell |
| electron-updater | Auto update |
| node-powershell | System commands |
| electron-builder | Packaging |

---

## 5. Cấu trúc Thư mục

```
KeoThongMinh/
├── backend/                    # FastAPI Backend
│   ├── app/
│   │   ├── main.py             # Entry point
│   │   ├── config.py           # Settings & env vars
│   │   ├── schemas.py          # Pydantic models
│   │   ├── providers/          # AI providers
│   │   │   ├── llm.py          # LLM (OpenAI/Gemini/Qwen)
│   │   │   ├── llm_stream.py   # Streaming LLM
│   │   │   ├── stt.py          # Speech-to-Text
│   │   │   └── tts.py          # Text-to-Speech
│   │   ├── services/           # Business logic
│   │   │   ├── chat_flow.py    # Chat orchestration
│   │   │   ├── tool_router.py  # Tool routing
│   │   │   ├── entity_extractor.py # Entity parsing
│   │   │   ├── replanner.py    # Replanning logic
│   │   │   ├── memory_store.py # Memory storage
│   │   │   ├── reminder_store.py # Reminder storage
│   │   │   ├── knowledge_service.py # Knowledge base
│   │   │   └── stream_manager.py # Session management
│   │   ├── tools/              # Real-world tools
│   │   │   ├── time_tool.py
│   │   │   ├── weather_tool.py
│   │   │   ├── currency_tool.py
│   │   │   └── search_tool.py
│   │   ├── data_paths.py       # Data directory paths
│   │   └── static/audio/       # Generated audio files
│   ├── tests/                  # 417 test cases
│   ├── scripts/                # Build & validation scripts
│   ├── data/                   # SQLite databases
│   ├── .env                    # Environment variables
│   └── requirements.txt        # Dependencies
│
├── frontend/                   # React Frontend
│   ├── src/
│   │   ├── App.tsx             # Main app component
│   │   ├── components/
│   │   │   ├── VoiceRecorder.tsx
│   │   │   ├── ChatPanel.tsx
│   │   │   ├── KeoBotAnimatedMascot.tsx
│   │   │   ├── SettingsPanel.tsx
│   │   │   └── KnowledgePanel.tsx
│   │   ├── hooks/
│   │   │   ├── useAutoVoiceConversation.ts
│   │   │   ├── useWakeWord.ts
│   │   │   └── useSilenceDetection.ts
│   │   ├── utils/
│   │   │   ├── audioPlaybackController.ts
│   │   │   ├── diagnostics.ts
│   │   │   └── api.ts
│   │   ├── types.ts            # TypeScript types
│   │   ├── desktop.d.ts        # Electron IPC types
│   │   └── styles.css          # Global styles
│   ├── public/keobot/          # Mascot assets (22 PNG)
│   └── package.json
│
├── desktop/                    # Electron Desktop App
│   ├── main.js                 # Main process
│   ├── preload.js              # IPC bridge
│   ├── services/
│   │   ├── logger.js           # Structured logging
│   │   ├── tray.js             # System tray
│   │   └── hotkey.js           # Global hotkey
│   ├── scripts/                # Build scripts
│   └── package.json
│
├── docs/                       # Documentation
│   ├── MANUAL_QA_CHECKLIST.md
│   └── RELEASE_CHECKLIST.md
│
├── assets/                     # Mascot assets & backup
│   └── backup/                 # Original mascot PNGs
│
├── README.md                   # Main documentation
├── .gitignore
└── package.json                # Root package
```

---

## 6. Luồng Dữ liệu

### 6.1. Voice Chat (Request/Response)

```
User speaks
  ↓
[Browser] MediaRecorder → Blob (webm/opus)
  ↓
[Frontend] Upload to /voice-chat
  ↓
[Backend] Save to backend/tmp/
  ↓
[Backend] STT: audio → text (OpenAI/Qwen/Mock)
  ↓
[Backend] Tool Router: detect intent
  ↓
[Backend] If tool needed: run tool + get result
  ↓
[Backend] LLM: generate response (persona + context)
  ↓
[Backend] TTS: text → mp3 (Edge TTS)
  ↓
[Backend] Return {audio_url, bot_text, emotion}
  ↓
[Frontend] Play audio + display text + update mascot
  ↓
[Frontend] If auto mode: return to listening
```

### 6.2. Auto Conversation Mode

```
User enables Auto Conversation
  ↓
[Frontend] Open microphone (continuous)
  ↓
[Frontend] Silence detection (RMS analysis)
  ↓
[Frontend] Speech detected → start recording
  ↓
[Frontend] Silence > threshold → auto-submit
  ↓
[Backend] Process voice chat (same as above)
  ↓
[Frontend] Play response
  ↓
[Frontend] Audio ended → resume listening
  ↓
[Loop] Repeat until user disables auto mode
```

### 6.3. System Command Flow

```
User: "Tắt máy sau 30 phút"
  ↓
[Backend] Entity Extractor: detect intent="system", delay=1800s
  ↓
[Backend] Chat Flow: route to system tool
  ↓
[Backend] Return {action: "system_command", system_command: "shutdown", delay_seconds: 1800}
  ↓
[Frontend] App.tsx: detect action === "system_command"
  ↓
[Frontend] Call window.electron.executeSystemCommand()
  ↓
[Desktop] IPC handler: show confirmation dialog
  ↓
[Desktop] If confirmed: run `shutdown /s /t 1800`
  ↓
[Desktop] Return result to frontend
  ↓
[Frontend] Display "Đã lên lịch tắt máy sau 30 phút"
```

---

## 7. Tính năng Bảo mật & Quyền riêng tư

- **API Keys**: Không bao giờ commit vào git, không bundle vào app
- **Data Local**: Memory, reminders, knowledge base đều lưu local SQLite
- **No Cloud Upload**: Tài liệu knowledge base không upload lên server
- **Wake Word**: Xử lý local qua Web Speech API, không gửi audio lên server
- **Sensitive Data Redaction**: Logs tự động ẩn API keys, tokens
- **System Commands**: Có confirmation dialog cho lệnh nguy hiểm
- **Mock Mode**: Có thể chạy hoàn toàn offline không cần API key

---

## 8. Định hướng Phát triển (Roadmap)

### 8.1. Ngắn hạn (v1.7 - v1.8)

- [ ] **RAG (Retrieval-Augmented Generation)**: Tích hợp vector DB (Chroma/Qdrant) cho knowledge base
- [ ] **Streaming STT**: Real-time streaming speech-to-text (WebSocket)
- [ ] **Wake Word Engine**: Thay thế Web Speech API bằng engine chuyên dụng (Porcupine/Picovoice)
- [ ] **Multi-language**: Hỗ trợ tiếng Anh, tiếng Trung (song ngữ)
- [ ] **Custom Voice**: Tinh chỉnh giọng TTS riêng cho Kẹo Thông Minh

### 8.2. Trung hạn (v2.0 - v2.5)

- [ ] **Live2D / VRM**: Hỗ trợ avatar 3D với lip-sync
- [ ] **Realtime Streaming**: Full streaming pipeline (STT + LLM + TTS liên tục)
- [ ] **Plugin System**: Cho phép mở rộng tools và providers qua plugin
- [ ] **Cross-platform**: Hỗ trợ macOS và Linux
- [ ] **Mobile App**: React Native / Flutter companion app
- [ ] **Cloud Sync**: Tùy chọn sync memory/reminders qua cloud (encrypted)

### 8.3. Dài hạn (v3.0+)

- [ ] **Local LLM**: Hỗ trợ chạy LLM local (Llama, Mistral, Qwen) qua Ollama
- [ ] **Agent Framework**: Cho phép Kẹo Thông Minh tự động thực hiện nhiệm vụ phức tạp
- [ ] **Vision**: Hỗ trợ xử lý hình ảnh (screenshot, camera)
- [ ] **Multi-agent**: Nhiều persona khác nhau (Kẹo Thông Minh, Kẹo Học Tập, Kẹo Lập Trình)
- [ ] **Enterprise**: Hỗ trợ SSO, audit logs, admin dashboard

---

## 9. Thông số Kỹ thuật

### 9.1. Yêu cầu Hệ thống

**Phát triển:**
- OS: Windows 10/11 (macOS/Linux cho backend-only)
- Python: 3.12+
- Node.js: 18+
- RAM: 8GB+ (16GB recommended)
- Disk: 2GB+ (bao gồm node_modules và Python packages)

**Production:**
- OS: Windows 10/11
- RAM: 4GB+ (8GB recommended)
- Disk: 500MB+ (app + data)
- Microphone: Required
- Internet: Required cho live providers

### 9.2. Performance

- **Backend startup**: < 3 giây
- **STT**: 1-3 giây (phụ thuộc provider)
- **LLM response**: 1-5 giây (phụ thuộc provider và độ dài)
- **TTS**: 2-4 giây (phụ thuộc độ dài text)
- **Total voice chat turn**: 5-15 giây
- **Backend tests**: 417 passed, 3 skipped (23.72s)

### 9.3. Cache Migration

Để tiết kiệm SSD C:\, các cache đã chuyển sang D:\Cache\:

| Cache | Kích thước | Junction Link |
|-------|-----------|---------------|
| rembg (u2netp) | 4.5 MB | `~\.u2net` |
| Python packages | 1.1 GB | `~\.cache` |
| npm cache | 3.5 GB | `%LocalAppData%\npm-cache` |
| npm global | 1.3 GB | `%AppData%\npm` |

---

## 10. Hướng dẫn Đóng góp

### 10.1. Development Setup

```powershell
# 1. Clone repo
git clone https://github.com/kieuquy283/KeoThongMinh.git
cd KeoThongMinh

# 2. Backend
python -m venv backend/.venv
.\backend\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt

# 3. Frontend
cd frontend
npm install

# 4. Desktop
cd ../desktop
npm install

# 5. Run development
npm run app:dev
```

### 10.2. Testing

```bash
# Backend tests
cd backend
python -m pytest

# Frontend typecheck
cd frontend
npm run typecheck

# Desktop build
cd desktop
npm run build
```

### 10.3. Commit Convention

- `feat:` - Tính năng mới
- `fix:` - Sửa lỗi
- `docs:` - Tài liệu
- `refactor:` - Tái cấu trúc
- `test:` - Test
- `chore:` - Công việc nhỏ

---

## 11. Liên hệ & Thông tin

- **Repository**: https://github.com/kieuquy283/KeoThongMinh
- **License**: (Chưa xác định - cần bổ sung)
- **Author**: kieuquy283
- **Status**: Active development

---

*Document version: 1.0*  
*Last updated: 2026-06-13*  
*Kẹo Thông Minh v1.6*
