import { useEffect, useState } from "react";
import { DEFAULT_SETTINGS, normalizeSettings } from "../settings";
import type { KeoBotSettings } from "../types";

interface SettingsPanelProps {
  onClose: () => void;
  onSaved?: (settings: KeoBotSettings) => void;
}

type SecretField = "OPENAI_API_KEY" | "GEMINI_API_KEY" | "GOOGLE_API_KEY";

const SECRET_LABELS: Record<SecretField, string> = {
  OPENAI_API_KEY: "OpenAI API key",
  GEMINI_API_KEY: "Gemini API key",
  GOOGLE_API_KEY: "Google API key",
};

export function SettingsPanel({ onClose, onSaved }: SettingsPanelProps) {
  const [settings, setSettings] = useState<KeoBotSettings>(DEFAULT_SETTINGS);
  const [status, setStatus] = useState<string>("Đang tải cài đặt...");
  const [saving, setSaving] = useState(false);
  const [visibleSecrets, setVisibleSecrets] = useState<Record<SecretField, boolean>>({
    OPENAI_API_KEY: false,
    GEMINI_API_KEY: false,
    GOOGLE_API_KEY: false,
  });
  const isDesktop = typeof window !== "undefined" && Boolean(window.keobotDesktop?.isDesktop);

  useEffect(() => {
    if (!isDesktop || !window.keobotDesktop) {
      setStatus("Settings chỉ khả dụng trong bản desktop.");
      return;
    }

    let active = true;
    void window.keobotDesktop.getSettings().then((loaded) => {
      if (!active) {
        return;
      }

      setSettings(normalizeSettings(loaded));
      setStatus("Cài đặt đã tải xong.");
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
      setStatus("Settings chỉ khả dụng trong bản desktop.");
      return;
    }

    setSaving(true);
    setStatus("Đang lưu cài đặt...");

    try {
      await window.keobotDesktop.saveSettings(settings);
      setStatus("Đã lưu cài đặt. Hãy khởi động lại KeoBot để áp dụng thay đổi.");
      onSaved?.(settings);
    } catch {
      setStatus("Không thể lưu cài đặt.");
    } finally {
      setSaving(false);
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
            <h2>Cài đặt</h2>
            <button className="action-button secondary" type="button" onClick={onClose}>
              Đóng
            </button>
          </div>
          <p className="muted-copy">Settings chỉ khả dụng trong bản desktop.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel settings-panel settings-modal">
      <div className="panel-inner settings-layout">
        <div className="panel-title">
          <div>
            <p className="section-kicker">Điều khiển desktop</p>
            <h2>Cài đặt</h2>
          </div>
          <button className="action-button secondary" type="button" onClick={onClose}>
            Đóng
          </button>
        </div>

        <div className="settings-summary">
          <div className="meta-row">
            <span>Trạng thái provider</span>
            <strong>Đã lưu cục bộ</strong>
          </div>
          <div className="meta-row">
            <span>Khởi động lại</span>
            <strong>Yêu cầu sau khi lưu</strong>
          </div>
        </div>

        <div className="settings-grid">
          <section className="settings-group">
            <h3>Provider</h3>
            <div className="settings-fields">
              <label className="settings-field">
                <span>STT provider</span>
                <select
                  value={settings.STT_PROVIDER}
                  onChange={(event) =>
                    updateField("STT_PROVIDER", event.target.value as KeoBotSettings["STT_PROVIDER"])
                  }
                >
                  <option value="mock">mock</option>
                  <option value="openai">openai</option>
                </select>
              </label>

              <label className="settings-field">
                <span>LLM provider</span>
                <select
                  value={settings.LLM_PROVIDER}
                  onChange={(event) =>
                    updateField("LLM_PROVIDER", event.target.value as KeoBotSettings["LLM_PROVIDER"])
                  }
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
                      placeholder={field === "OPENAI_API_KEY" ? "sk-..." : "AIza..."}
                    />
                    <button
                      className="action-button secondary secret-toggle"
                      type="button"
                      onClick={() => toggleSecret(field)}
                    >
                      {visibleSecrets[field] ? "Ẩn" : "Hiện"}
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
            {saving ? "Đang lưu..." : "Lưu cài đặt"}
          </button>
          <p className="settings-status">{status}</p>
        </div>
      </div>
    </section>
  );
}
