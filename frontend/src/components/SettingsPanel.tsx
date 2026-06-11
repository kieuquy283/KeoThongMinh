import { useEffect, useState } from "react";
import { fetchToolsStatus, testTool } from "../api";
import { DEFAULT_SETTINGS, normalizeSettings } from "../settings";
import type { KeoBotSettings, ToolTestResponse, ToolsStatusResponse } from "../types";

interface SettingsPanelProps {
  onClose: () => void;
  onSaved?: (settings: KeoBotSettings) => void;
}

type SecretField =
  | "OPENAI_API_KEY"
  | "GEMINI_API_KEY"
  | "GOOGLE_API_KEY"
  | "OPENWEATHER_API_KEY"
  | "TAVILY_API_KEY"
  | "SERPAPI_API_KEY"
  | "PICOVOICE_ACCESS_KEY";

type TestableTool = "weather" | "search" | "currency" | "time";

const TOOL_SAMPLE_QUERIES: Record<TestableTool, string> = {
  weather: "Thời tiết Hà Nội hôm nay thế nào?",
  search: "Tin AI mới nhất",
  currency: "100 USD sang VND hôm nay?",
  time: "Bây giờ là mấy giờ ở Nhật?",
};

const STATUS_LABELS: Record<NonNullable<ToolsStatusResponse["weather"]["status"]>, string> = {
  ok: "OK",
  not_configured: "Not configured",
  invalid_key: "Invalid key",
  network_error: "Network error",
  rate_limited: "Rate limited",
  unknown_error: "Unknown error",
};

const STATUS_CLASS: Record<NonNullable<ToolsStatusResponse["weather"]["status"]>, string> = {
  ok: "ok",
  not_configured: "warning",
  invalid_key: "error",
  network_error: "error",
  rate_limited: "warning",
  unknown_error: "warning",
};

const SECRET_LABELS: Record<SecretField, string> = {
  OPENAI_API_KEY: "OpenAI API key",
  GEMINI_API_KEY: "Gemini API key",
  GOOGLE_API_KEY: "Google API key",
  OPENWEATHER_API_KEY: "OpenWeather API key",
  TAVILY_API_KEY: "Tavily API key",
  SERPAPI_API_KEY: "SerpAPI API key",
  PICOVOICE_ACCESS_KEY: "Picovoice access key",
};

function formatWakeWordPhrases(phrases: string[]): string {
  return phrases.join("\n");
}

function parseWakeWordPhrases(value: string): string[] {
  return value
    .split(/[\n,;]/g)
    .map((phrase) => phrase.trim())
    .filter(Boolean);
}

export function SettingsPanel({ onClose, onSaved }: SettingsPanelProps) {
  const [settings, setSettings] = useState<KeoBotSettings>(DEFAULT_SETTINGS);
  const [wakeWordPhrasesText, setWakeWordPhrasesText] = useState(formatWakeWordPhrases(DEFAULT_SETTINGS.WAKE_WORD_PHRASES));
  const [status, setStatus] = useState<string>("Dang tai cai dat...");
  const [saving, setSaving] = useState(false);
  const [checkingTools, setCheckingTools] = useState(false);
  const [toolsStatus, setToolsStatus] = useState<ToolsStatusResponse | null>(null);
  const [toolTests, setToolTests] = useState<Partial<Record<TestableTool, ToolTestResponse>>>({});
  const [visibleSecrets, setVisibleSecrets] = useState<Record<SecretField, boolean>>({
    OPENAI_API_KEY: false,
    GEMINI_API_KEY: false,
    GOOGLE_API_KEY: false,
    OPENWEATHER_API_KEY: false,
    TAVILY_API_KEY: false,
    SERPAPI_API_KEY: false,
    PICOVOICE_ACCESS_KEY: false,
  });
  const [appInfo, setAppInfo] = useState<{ appVersion: string; buildMode: string; releaseMode: string; signedBuild: boolean; commitHash: string; updateChannel: string; publishProvider: string | null } | null>(null);
  const [backendHealthy, setBackendHealthy] = useState(false);
  const [backendVersion, setBackendVersion] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [updateStatus, setUpdateStatus] = useState<"idle" | "checking" | "update_available" | "update_not_available" | "downloading" | "downloaded" | "error">("idle");
  const [updateErrorMessage, setUpdateErrorMessage] = useState<string | null>(null);
  const isDesktop = typeof window !== "undefined" && Boolean(window.keobotDesktop?.isDesktop);

  useEffect(() => {
    if (!isDesktop || !window.keobotDesktop) {
      setStatus("Settings chi kha dung trong ban desktop.");
      return;
    }

    let active = true;

    void window.keobotDesktop.getSettings().then((loaded) => {
      if (!active) {
        return;
      }

      const normalized = normalizeSettings(loaded);
      setSettings(normalized);
      setWakeWordPhrasesText(formatWakeWordPhrases(normalized.WAKE_WORD_PHRASES));
      setStatus("Cai dat da tai xong.");
    });

    if (window.keobotDesktop.getAppInfo) {
      void window.keobotDesktop.getAppInfo().then((info) => {
        if (active) setAppInfo(info);
      });
    }

    if (window.keobotDesktop.getBackendHealth) {
      void window.keobotDesktop.getBackendHealth().then((health) => {
        if (active) {
          setBackendHealthy(health.healthy);
          setBackendVersion(health.version);
        }
      });
    }

    if (window.keobotDesktop.onUpdateStatus) {
      const unsub = window.keobotDesktop.onUpdateStatus((status) => {
        if (!active) return;
        setUpdateStatus(status.status);
        if (status.message) setUpdateErrorMessage(status.message);
        if (status.status === "error" && !status.message) setUpdateErrorMessage("Update check failed");
      });
      return () => {
        active = false;
        unsub();
      };
    }

    return () => {
      active = false;
    };
  }, [isDesktop]);

  const updateField = <K extends keyof KeoBotSettings>(key: K, value: KeoBotSettings[K]) => {
    setSettings((current) => ({
      ...current,
      [key]: value,
    }));
  };

  const handleSave = async () => {
    if (!window.keobotDesktop) {
      setStatus("Settings chi kha dung trong ban desktop.");
      return;
    }

    setSaving(true);
    setStatus("Dang luu cai dat...");

    try {
      const nextSettings = {
        ...settings,
        WAKE_WORD_PHRASES: parseWakeWordPhrases(wakeWordPhrasesText),
      };
      await window.keobotDesktop.saveSettings(nextSettings);
      setStatus("Đã lưu cài đặt. Hãy khởi động lại Kẹo Thông Minh để áp dụng thay đổi.");
      onSaved?.(nextSettings);
    } catch {
      setStatus("Khong the luu cai dat.");
    } finally {
      setSaving(false);
    }
  };

  const handleOpenLogs = async () => {
    if (window.keobotDesktop?.openLogsFolder) {
      await window.keobotDesktop.openLogsFolder();
    }
  };

  const handleCopyDiagnostics = async () => {
    const lines: string[] = [];
    if (appInfo) {
      lines.push(`App version: ${appInfo.appVersion}`);
      lines.push(`Build mode: ${appInfo.buildMode}`);
      lines.push(`Release mode: ${appInfo.releaseMode}`);
      lines.push(`Signed build: ${appInfo.signedBuild ? "yes" : "no"}`);
      if (appInfo.commitHash) lines.push(`Commit: ${appInfo.commitHash.slice(0, 8)}`);
      lines.push(`Update channel: ${appInfo.updateChannel}`);
      lines.push(`Publish provider: ${appInfo.publishProvider || "none"}`);
    }
    lines.push(`Backend healthy: ${backendHealthy}`);
    if (backendVersion) lines.push(`Backend version: ${backendVersion}`);
    lines.push(`Update status: ${updateStatus}`);
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setStatus("Khong the copy.");
    }
  };

  const handleCheckTools = async () => {
    setCheckingTools(true);
    setStatus("Dang kiem tra cong cu...");
    try {
      const result = await fetchToolsStatus();
      setToolsStatus(result);
      setStatus("Da kiem tra cong cu.");
    } catch {
      setStatus("Khong the kiem tra cong cu.");
    } finally {
      setCheckingTools(false);
    }
  };

  const handleTestTool = async (tool: TestableTool) => {
    setStatus(`Dang kiem tra ${tool}...`);
    try {
      const result = await testTool({
        tool,
        sample_query: TOOL_SAMPLE_QUERIES[tool],
      });
      setToolTests((current) => ({
        ...current,
        [tool]: result,
      }));
      setStatus(`Da kiem tra ${tool}.`);
    } catch {
      setStatus(`Khong the kiem tra ${tool}.`);
    }
  };

  const toggleSecret = (field: SecretField) => {
    setVisibleSecrets((current) => ({
      ...current,
      [field]: !current[field],
    }));
  };

  if (!isDesktop) {
    return (
      <section className="panel settings-panel settings-modal">
        <div className="panel-inner">
          <div className="panel-title">
            <h2>Cai dat</h2>
            <button className="action-button secondary" type="button" onClick={onClose}>
              Dong
            </button>
          </div>
          <p className="muted-copy">Settings chi kha dung trong ban desktop.</p>
        </div>
      </section>
    );
  }

  const renderStatusBadge = (toolStatus?: ToolsStatusResponse["weather"]) => {
    const statusKey = toolStatus?.status ?? "unknown_error";
    return (
      <span className={`provider-status-badge ${STATUS_CLASS[statusKey]}`}>
        {STATUS_LABELS[statusKey]}
      </span>
    );
  };

  const formatCheckedAt = (checkedAt?: string | null) => {
    if (!checkedAt) {
      return "Chua kiem tra";
    }

    const date = new Date(checkedAt);
    if (Number.isNaN(date.getTime())) {
      return checkedAt;
    }

    return new Intl.DateTimeFormat("vi-VN", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(date);
  };

  const renderProviderCard = (
    title: string,
    toolKey: TestableTool,
    statusInfo: ToolsStatusResponse["weather"] | undefined,
    description: string,
  ) => {
    const testResult = toolTests[toolKey];
    const providerName = statusInfo?.configured ? statusInfo.provider : "Not configured";
    const providerNote = statusInfo?.message ?? "Chua kiem tra";
    const lastChecked = formatCheckedAt(statusInfo?.last_checked_at ?? testResult?.checked_at ?? null);
    const testSummary = testResult ? `${STATUS_LABELS[testResult.status]} · ${testResult.message}` : null;

    return (
      <article className="provider-health-card" key={toolKey}>
        <div className="provider-health-header">
          <div>
            <h4>{title}</h4>
            <p>{description}</p>
          </div>
          {renderStatusBadge(statusInfo)}
        </div>
        <div className="provider-health-meta">
          <div className="meta-row">
            <span>Provider</span>
            <strong>{providerName}</strong>
          </div>
          <div className="meta-row">
            <span>Last checked</span>
            <strong>{lastChecked}</strong>
          </div>
        </div>
        <p className="provider-health-note">{providerNote}</p>
        {testSummary ? <p className="provider-health-test">{testSummary}</p> : null}
        <div className="provider-health-actions">
          <button className="action-button secondary" type="button" onClick={() => handleTestTool(toolKey)}>
            Test
          </button>
        </div>
      </article>
    );
  };

  return (
    <section className="panel settings-panel settings-modal">
      <div className="panel-inner settings-layout">
        <div className="panel-title">
          <div>
            <p className="section-kicker">Dieu khien desktop</p>
            <h2>Cai dat</h2>
          </div>
          <button className="action-button secondary" type="button" onClick={onClose}>
            Dong
          </button>
        </div>

        <div className="settings-summary">
          <div className="meta-row">
            <span>Trang thai provider</span>
            <strong>Da luu cuc bo</strong>
          </div>
          <div className="meta-row">
            <span>Khoi dong lai</span>
            <strong>Yeu cau sau khi luu</strong>
          </div>
        </div>

        <section className="settings-group">
          <h3>Background Assistant</h3>
          <div className="settings-fields">
            <label className="settings-field">
              <span>Enable wake word</span>
              <input
                type="checkbox"
                checked={settings.WAKE_WORD_ENABLED}
                onChange={(event) => updateField("WAKE_WORD_ENABLED", event.target.checked)}
              />
            </label>

            <label className="settings-field">
              <span>Wake word engine</span>
              <select
                value={settings.WAKE_WORD_ENGINE}
                onChange={(event) => updateField("WAKE_WORD_ENGINE", event.target.value as KeoBotSettings["WAKE_WORD_ENGINE"])}
              >
                <option value="web_speech">Web Speech API</option>
                <option value="local">Local (Porcupine)</option>
                <option value="hotkey_only">Hotkey only</option>
              </select>
            </label>

            <label className="settings-field">
              <span>Wake word mode</span>
              <input value="local_stt" readOnly />
            </label>

            <label className="settings-field">
              <span>Wake phrases</span>
              <textarea
                value={wakeWordPhrasesText}
                onChange={(event) => setWakeWordPhrasesText(event.target.value)}
                rows={4}
                placeholder="keobot oi&#10;nay keobot&#10;hey keobot"
              />
            </label>

            {settings.WAKE_WORD_ENGINE === "local" ? (
              <>
                <label className="settings-field">
                  <span>Picovoice access key</span>
                  <div className="secret-input">
                    <input
                      type={visibleSecrets.PICOVOICE_ACCESS_KEY ? "text" : "password"}
                      value={settings.PICOVOICE_ACCESS_KEY}
                      onChange={(event) => updateField("PICOVOICE_ACCESS_KEY", event.target.value)}
                      autoComplete="off"
                    />
                    <button
                      className="action-button secondary secret-toggle"
                      type="button"
                      onClick={() => setVisibleSecrets((current) => ({ ...current, PICOVOICE_ACCESS_KEY: !current.PICOVOICE_ACCESS_KEY }))}
                    >
                      {visibleSecrets.PICOVOICE_ACCESS_KEY ? "An" : "Hien"}
                    </button>
                  </div>
                </label>

                <label className="settings-field">
                  <span>Keyword path (.ppn)</span>
                  <input
                    value={settings.PORCUPINE_KEYWORD_PATH}
                    onChange={(event) => updateField("PORCUPINE_KEYWORD_PATH", event.target.value)}
                    placeholder="Leave empty to use built-in porcupine keyword"
                  />
                </label>

                <label className="settings-field">
                  <span>Sensitivity ({settings.LOCAL_WAKE_SENSITIVITY.toFixed(2)})</span>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={settings.LOCAL_WAKE_SENSITIVITY}
                    onChange={(event) => updateField("LOCAL_WAKE_SENSITIVITY", Number.parseFloat(event.target.value))}
                  />
                </label>
              </>
            ) : null}

            <label className="settings-field">
              <span>Global hotkey</span>
              <input
                type="checkbox"
                checked={settings.HOTKEY_ENABLED}
                onChange={(event) => updateField("HOTKEY_ENABLED", event.target.checked)}
              />
            </label>

            <label className="settings-field">
              <span>Hotkey value</span>
              <input value={settings.HOTKEY_VALUE} readOnly />
            </label>

            <label className="settings-field">
              <span>Auto return to wake mode</span>
              <input
                type="checkbox"
                checked={settings.HANDSFREE_AUTO_RETURN_TO_WAKE_MODE}
                onChange={(event) => updateField("HANDSFREE_AUTO_RETURN_TO_WAKE_MODE", event.target.checked)}
              />
            </label>

            <label className="settings-field">
              <span>Start with Windows</span>
              <input
                type="checkbox"
                checked={settings.START_WITH_WINDOWS}
                onChange={(event) => updateField("START_WITH_WINDOWS", event.target.checked)}
              />
            </label>

            <label className="settings-field">
              <span>Giữ Kẹo Thông Minh chạy nền</span>
              <input
                type="checkbox"
                checked={settings.BACKGROUND_ASSISTANT_ENABLED}
                onChange={(event) => updateField("BACKGROUND_ASSISTANT_ENABLED", event.target.checked)}
              />
            </label>
          </div>
          <p className="muted-copy">
            Wake word can use Web Speech API (renderer) or local Porcupine engine (main process). Audio is sent to
            backend only after activation. Hotkey fallback works regardless of engine.
          </p>
        </section>

        <section className="settings-group">
          <div className="panel-title">
            <div>
              <h3>Provider health</h3>
              <p className="muted-copy">Kiem tra cau hinh va trang thai cong cu ma khong hien API key.</p>
            </div>
            <button className="action-button secondary" type="button" onClick={handleCheckTools} disabled={checkingTools}>
              {checkingTools ? "Dang kiem tra..." : "Check all tools"}
            </button>
          </div>
          <div className="provider-health-grid">
            {renderProviderCard("Weather", "weather", toolsStatus?.weather, "Weather provider diagnostics and test query")}
            {renderProviderCard("Search", "search", toolsStatus?.search, "Search/news provider diagnostics and test query")}
            {renderProviderCard("Currency", "currency", toolsStatus?.currency, "Currency provider diagnostics and test query")}
            {renderProviderCard(
              "Time",
              "time",
              {
                provider: "zoneinfo",
                configured: true,
                live: false,
                status: "ok",
                message: "Local timezone lookup is always available.",
                last_checked_at: toolTests.time?.checked_at ?? null,
              },
              "Local timezone lookup test query",
            )}
          </div>
        </section>

        <section className="settings-group">
          <h3>Diagnostics & About</h3>
          <div className="settings-fields">
            {appInfo && (
              <>
                <div className="settings-field">
                  <span>App version</span>
                  <code>{appInfo.appVersion}</code>
                </div>
                <div className="settings-field">
                  <span>Build mode</span>
                  <code>{appInfo.buildMode}</code>
                </div>
                <div className="settings-field">
                  <span>Backend health</span>
                  <code className={backendHealthy ? "status-ok" : "status-error"}>
                    {backendHealthy ? "Healthy" : "Unreachable"}
                  </code>
                </div>
                {appInfo.commitHash && (
                  <div className="settings-field">
                    <span>Commit</span>
                    <code>{appInfo.commitHash.slice(0, 8)}</code>
                  </div>
                )}
                <div className="settings-field">
                  <span>Release mode</span>
                  <code>{appInfo.releaseMode}</code>
                </div>
                <div className="settings-field">
                  <span>Signed build</span>
                  <code className={appInfo.signedBuild ? "status-ok" : "status-error"}>
                    {appInfo.signedBuild ? "Yes" : "No"}
                  </code>
                </div>
                <div className="settings-field">
                  <span>Update channel</span>
                  <code>{appInfo.updateChannel}</code>
                </div>
                <div className="settings-field">
                  <span>Publish provider</span>
                  <code>{appInfo.publishProvider || "none"}</code>
                </div>
                {backendVersion && (
                  <div className="settings-field">
                    <span>Backend version</span>
                    <code>{backendVersion}</code>
                  </div>
                )}
              </>
            )}
            <div className="settings-field">
              <span>Logs folder</span>
              <button className="action-button secondary" type="button" onClick={handleOpenLogs}>
                Open logs folder
              </button>
            </div>
            <div className="settings-field">
              <span>Copy diagnostics</span>
              <button className="action-button secondary" type="button" onClick={handleCopyDiagnostics}>
                {copied ? "Copied!" : "Copy diagnostics"}
              </button>
            </div>
            <div className="settings-field">
              <span>Auto update</span>
              <div>
                {updateStatus === "idle" && (
                  appInfo?.publishProvider
                    ? <span className="muted-copy">Ready to check updates</span>
                    : <span className="muted-copy">Auto update is not configured for this build.</span>
                )}
                {updateStatus === "checking" && <span>Checking for updates...</span>}
                {updateStatus === "update_available" && <span className="status-ok">Update available</span>}
                {updateStatus === "update_not_available" && <span className="muted-copy">You have the latest version</span>}
                {updateStatus === "downloading" && <span>Downloading...</span>}
                {updateStatus === "downloaded" && <span className="status-ok">Update downloaded</span>}
                {updateStatus === "error" && <span className="status-error">{updateErrorMessage || "Update error"}</span>}
              </div>
            </div>
          </div>
        </section>

        <div className="settings-grid">
          <section className="settings-group">
            <h3>Core Providers</h3>
            <div className="settings-fields">
              <label className="settings-field">
                <span>STT provider</span>
                <select
                  value={settings.STT_PROVIDER}
                  onChange={(event) => updateField("STT_PROVIDER", event.target.value as KeoBotSettings["STT_PROVIDER"])}
                >
                  <option value="mock">mock</option>
                  <option value="openai">openai</option>
                </select>
              </label>

              <label className="settings-field">
                <span>LLM provider</span>
                <select
                  value={settings.LLM_PROVIDER}
                  onChange={(event) => updateField("LLM_PROVIDER", event.target.value as KeoBotSettings["LLM_PROVIDER"])}
                >
                  <option value="local">local</option>
                  <option value="openai">openai</option>
                  <option value="gemini">gemini</option>
                </select>
              </label>

              <label className="settings-field">
                <span>TTS provider</span>
                <input value="edge_tts" readOnly />
              </label>
            </div>
          </section>

          <section className="settings-group">
            <h3>Information Providers</h3>
            <div className="settings-fields">
              <label className="settings-field">
                <span>Weather provider</span>
                <select
                  value={settings.WEATHER_PROVIDER}
                  onChange={(event) =>
                    updateField("WEATHER_PROVIDER", event.target.value as KeoBotSettings["WEATHER_PROVIDER"])
                  }
                >
                  <option value="none">none</option>
                  <option value="openweathermap">openweathermap</option>
                </select>
              </label>

              <label className="settings-field">
                <span>Search provider</span>
                <select
                  value={settings.SEARCH_PROVIDER}
                  onChange={(event) =>
                    updateField("SEARCH_PROVIDER", event.target.value as KeoBotSettings["SEARCH_PROVIDER"])
                  }
                >
                  <option value="none">none</option>
                  <option value="tavily">tavily</option>
                  <option value="serpapi">serpapi</option>
                </select>
              </label>
            </div>
          </section>

          <section className="settings-group">
            <h3>API Keys</h3>
            <div className="settings-fields">
              {(Object.keys(SECRET_LABELS) as SecretField[]).map((field) => (
                <label className="settings-field" key={field}>
                  <span>{SECRET_LABELS[field]}</span>
                  <div className="secret-input">
                    <input
                      type={visibleSecrets[field] ? "text" : "password"}
                      value={settings[field]}
                      onChange={(event) => updateField(field, event.target.value)}
                      autoComplete="off"
                    />
                    <button
                      className="action-button secondary secret-toggle"
                      type="button"
                      onClick={() => toggleSecret(field)}
                    >
                      {visibleSecrets[field] ? "An" : "Hien"}
                    </button>
                  </div>
                </label>
              ))}
            </div>
          </section>

          <section className="settings-group">
            <h3>Voice</h3>
            <div className="settings-fields">
              <label className="settings-field">
                <span>Edge TTS voice</span>
                <input
                  value={settings.EDGE_TTS_VOICE}
                  onChange={(event) => updateField("EDGE_TTS_VOICE", event.target.value)}
                  placeholder="vi-VN-HoaiMyNeural"
                />
              </label>
            </div>
          </section>
        </div>

        <div className="settings-actions">
          <button className="action-button" type="button" onClick={handleSave} disabled={saving}>
            {saving ? "Dang luu..." : "Luu cai dat"}
          </button>
          <p className="settings-status">{status}</p>
        </div>
      </div>
    </section>
  );
}
