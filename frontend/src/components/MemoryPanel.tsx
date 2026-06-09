import { useEffect, useState } from "react";
import { clearMemory, deleteMemoryItem, fetchMemory, saveMemoryItem } from "../api";
import type { MemoryItem } from "../types";

interface MemoryPanelProps {
  onClose: () => void;
}

type MemoryKey = MemoryItem["key"];

const KEY_LABELS: Record<MemoryKey, string> = {
  user_name: "User name",
  preferred_form_of_address: "Preferred address",
  default_city: "Default city",
  default_timezone: "Default timezone",
  default_currency: "Default currency",
  preferred_tts_voice: "Preferred TTS voice",
  answer_style: "Answer style",
};

export function MemoryPanel({ onClose }: MemoryPanelProps) {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("Memory is stored locally on this device. Do not store sensitive information.");
  const [selectedKey, setSelectedKey] = useState<MemoryKey>("user_name");
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);

  const loadMemory = async () => {
    setLoading(true);
    try {
      const nextItems = await fetchMemory();
      setItems(nextItems);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Khong the tai bo nho.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadMemory();
  }, []);

  const handleEdit = (item: MemoryItem) => {
    setSelectedKey(item.key);
    setValue(item.value);
  };

  const handleSave = async () => {
    if (!value.trim()) {
      setStatus("Gia tri bo nho khong duoc de trong.");
      return;
    }

    setSaving(true);
    setStatus("Dang luu bo nho...");
    try {
      await saveMemoryItem({
        key: selectedKey,
        value: value.trim(),
        category: "preference",
      });
      setStatus("Da luu bo nho.");
      setValue("");
      await loadMemory();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Khong the luu bo nho.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (key: MemoryKey) => {
    setStatus("Dang xoa bo nho...");
    try {
      await deleteMemoryItem(key);
      setStatus("Da xoa bo nho.");
      await loadMemory();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Khong the xoa bo nho.");
    }
  };

  const handleClear = async () => {
    setStatus("Dang xoa tat ca bo nho...");
    try {
      await clearMemory();
      setStatus("Da xoa tat ca bo nho.");
      setValue("");
      await loadMemory();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Khong the xoa tat ca bo nho.");
    }
  };

  return (
    <section className="panel settings-panel settings-modal">
      <div className="panel-inner memory-layout">
        <div className="panel-title">
          <div>
            <p className="section-kicker">Bo nho cuc bo</p>
            <h2>Memory</h2>
          </div>
          <button className="action-button secondary" type="button" onClick={onClose}>
            Dong
          </button>
        </div>

        <div className="tool-warning">
          <strong>Local only</strong>
          <span>Memory is stored locally on this device. Do not store sensitive information.</span>
        </div>

        <section className="settings-group">
          <h3>Add / edit memory</h3>
          <div className="settings-fields">
            <label className="settings-field">
              <span>Key</span>
              <select value={selectedKey} onChange={(event) => setSelectedKey(event.target.value as MemoryKey)}>
                {Object.entries(KEY_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="settings-field">
              <span>Value</span>
              <input
                value={value}
                onChange={(event) => setValue(event.target.value)}
                placeholder="Enter a simple preference"
                autoComplete="off"
              />
            </label>
          </div>
          <div className="settings-actions memory-actions">
            <button className="action-button" type="button" onClick={handleSave} disabled={saving}>
              {saving ? "Dang luu..." : "Save memory"}
            </button>
            <button className="action-button secondary" type="button" onClick={handleClear} disabled={loading || items.length === 0}>
              Clear all
            </button>
          </div>
        </section>

        <section className="settings-group">
          <div className="panel-title">
            <h3>Current memory</h3>
            <button className="action-button secondary" type="button" onClick={() => void loadMemory()} disabled={loading}>
              {loading ? "Dang tai..." : "Refresh"}
            </button>
          </div>
          <div className="memory-list">
            {items.length === 0 ? (
              <p className="muted-copy">Chua co memory nao.</p>
            ) : (
              items.map((item) => (
                <article className="memory-card" key={item.key}>
                  <div className="memory-card-copy">
                    <div className="meta-row">
                      <span>{KEY_LABELS[item.key]}</span>
                      <strong>{item.value}</strong>
                    </div>
                    <div className="meta-row">
                      <span>Category</span>
                      <strong>{item.category}</strong>
                    </div>
                    <div className="meta-row">
                      <span>Updated</span>
                      <strong>{new Date(item.updated_at).toLocaleString()}</strong>
                    </div>
                  </div>
                  <div className="memory-actions">
                    <button className="action-button secondary" type="button" onClick={() => handleEdit(item)}>
                      Edit
                    </button>
                    <button className="action-button secondary" type="button" onClick={() => handleDelete(item.key)}>
                      Delete
                    </button>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>

        <p className="settings-status">{status}</p>
      </div>
    </section>
  );
}
