interface PrivacyNoticeProps {
  onEnableMemory: () => void;
  onKeepMemoryOff: () => void;
  onOpenPrivacySettings: () => void;
}

export function PrivacyNotice({ onEnableMemory, onKeepMemoryOff, onOpenPrivacySettings }: PrivacyNoticeProps) {
  return (
    <section className="panel privacy-notice-overlay">
      <div className="panel-inner privacy-notice-card">
        <h2>Quyền riêng tư & Dữ liệu cá nhân</h2>
        <p className="privacy-notice-message">
          KẹoBot lưu bộ nhớ cá nhân trên máy này. Nếu dùng máy chung, hãy tắt bộ nhớ hoặc xóa dữ liệu cá nhân sau khi dùng.
        </p>
        <div className="privacy-notice-actions">
          <button className="action-button" type="button" onClick={onEnableMemory}>
            Bật bộ nhớ
          </button>
          <button className="action-button secondary" type="button" onClick={onKeepMemoryOff}>
            Tắt bộ nhớ
          </button>
          <button className="action-button secondary" type="button" onClick={onOpenPrivacySettings}>
            Cài đặt quyền riêng tư
          </button>
        </div>
      </div>
    </section>
  );
}
