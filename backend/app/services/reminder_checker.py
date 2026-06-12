from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from app.services.event_bus import Event, EventType, get_event_bus
from app.services.reminder_store import get_reminder_store

if TYPE_CHECKING:
    from app.services.reminder_store import ReminderStore

logger = logging.getLogger("keobot.reminder_checker")

_CHECK_INTERVAL = 15


async def run_reminder_checker_loop(store: ReminderStore | None = None) -> None:
    s = store or get_reminder_store()
    while True:
        await asyncio.sleep(_CHECK_INTERVAL)
        try:
            now = datetime.now()
            due = s.get_due(now=now)

            for reminder in due:
                title = reminder.title
                rid = reminder.id
                repeat = reminder.repeat_interval

                store.mark_triggered(rid, triggered_at=now)

                bus = get_event_bus()
                await bus.publish_async(Event(
                    type=EventType.reminder_due,
                    payload={
                        "id": rid,
                        "title": title,
                        "remind_at": reminder.remind_at.isoformat(),
                        "repeat_interval": repeat,
                    },
                ))
                logger.info("reminder_fired id=%d title=%s", rid, title)

                if repeat is not None:
                    store.reschedule_recurring(rid, now=now)
                    logger.info("reminder_rescheduled id=%d interval=%ds", rid, repeat)
        except Exception:
            logger.exception("Reminder checker error")
