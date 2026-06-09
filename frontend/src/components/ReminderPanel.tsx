import type { KeoBotReminder } from "../types";

interface ReminderPanelProps {
  reminders: KeoBotReminder[];
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onRefresh: () => void;
  onDelete: (reminderId: number) => void;
}

function formatReminderTime(remindAt: string): string {
  const date = new Date(remindAt);
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
  }).format(date);
}

export function ReminderPanel({
  reminders,
  loading,
  error,
  onClose,
  onRefresh,
  onDelete,
}: ReminderPanelProps) {
  return (
    <section className="panel settings-modal">
      <div className="panel-inner reminder-panel">
        <div className="panel-title">
          <div>
            <p className="section-kicker">Reminder local</p>
            <h2>Danh sách nhắc việc</h2>
          </div>
          <div className="hero-actions">
            <button className="action-button secondary" type="button" onClick={onRefresh}>
              Làm mới
            </button>
            <button className="action-button secondary" type="button" onClick={onClose}>
              Đóng
            </button>
          </div>
        </div>

        {error ? <div className="error-banner">{error}</div> : null}
        {loading ? <p className="muted-copy">Đang tải reminders...</p> : null}
        {!loading && reminders.length === 0 ? (
          <p className="muted-copy">Chưa có reminder nào. Hãy nói kiểu: "1 phút nữa nhắc mình uống nước".</p>
        ) : null}

        <div className="reminder-list">
          {reminders.map((reminder) => (
            <article className="reminder-card" key={reminder.id}>
              <div className="reminder-copy">
                <strong>{reminder.title}</strong>
                <span>{formatReminderTime(reminder.remind_at)}</span>
              </div>
              <div className="reminder-actions">
                <span className="status-pill">{reminder.status}</span>
                <button className="action-button danger" type="button" onClick={() => onDelete(reminder.id)}>
                  Xóa
                </button>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
