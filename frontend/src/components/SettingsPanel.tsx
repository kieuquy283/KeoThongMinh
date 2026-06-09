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
  | "SERPAPI_API_KEY";

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
};

export function SettingsPanel({ onClose, onSaved }: SettingsPanelProps) {
  const [settings, setSettings] = useState<KeoBotSettings>(DEFAULT_SETTINGS);
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
  });
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

      setSettings(normalizeSettings(loaded));
      setStatus("Cai dat da tai xong.");
    });

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
      await window.keobotDesktop.saveSettings(settings);
      setStatus("Da luu cai dat. Hay khoi dong lai KeoBot de ap dung thay doi.");
      onSaved?.(settings);
    } catch {
      setStatus("Khong the luu cai dat.");
    } finally {
      setSaving(false);
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
          <h3>Background</h3>
          <p className="muted-copy">Start with Windows: planned.</p>
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
