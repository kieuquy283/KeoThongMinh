import { useEffect } from "react";

import type { KeoBotReminder } from "../types";

interface ReminderToastProps {
  reminder: KeoBotReminder;
  onDismiss: () => void;
}

export function ReminderToast({ reminder, onDismiss }: ReminderToastProps) {
  useEffect(() => {
    const timeout = window.setTimeout(() => {
      onDismiss();
    }, 8000);

    return () => {
      window.clearTimeout(timeout);
    };
  }, [onDismiss]);

  return (
    <aside className="reminder-toast" role="status" aria-live="assertive">
      <div className="reminder-toast-copy">
        <p className="section-kicker">Nhắc việc đến hạn</p>
        <strong>Kẹo Thông Minh nhắc bạn: {reminder.title}</strong>
      </div>
      <button className="action-button secondary" type="button" onClick={onDismiss}>
        Đóng
      </button>
    </aside>
  );
}
