"""Notification helpers for desktop session UX events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class NotificationEvent:
    level: str
    title: str
    message: str
    created_at: str = field(default_factory=_utc_now_iso)


class NotificationSink(Protocol):
    def notify(self, event: NotificationEvent) -> None:
        ...


class MemoryNotificationSink:
    def __init__(self) -> None:
        self.events: list[NotificationEvent] = []

    def notify(self, event: NotificationEvent) -> None:
        self.events.append(event)


class DesktopNotificationCenter:
    def __init__(self, sinks: list[NotificationSink] | None = None) -> None:
        self._memory_sink = MemoryNotificationSink()
        self._sinks: list[NotificationSink] = [self._memory_sink]
        if sinks:
            self._sinks.extend(sinks)

    def publish(self, title: str, message: str, level: str = "info") -> NotificationEvent:
        event = NotificationEvent(level=level, title=title, message=message)
        for sink in self._sinks:
            sink.notify(event)
        return event

    def info(self, title: str, message: str) -> NotificationEvent:
        return self.publish(title=title, message=message, level="info")

    def warning(self, title: str, message: str) -> NotificationEvent:
        return self.publish(title=title, message=message, level="warning")

    def error(self, title: str, message: str) -> NotificationEvent:
        return self.publish(title=title, message=message, level="error")

    def recent(self, limit: int | None = None) -> list[NotificationEvent]:
        events = list(self._memory_sink.events)
        if limit is None:
            return events
        return events[-limit:]