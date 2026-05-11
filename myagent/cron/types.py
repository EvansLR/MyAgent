"""Cron data models."""

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class CronSchedule:
    """Schedule definition for a cron job."""

    kind: Literal["at", "every"]
    at: float | None = None  # Unix timestamp for "at"
    every: int | None = None  # seconds for "every"


@dataclass
class CronPayload:
    """What to do when the job runs."""

    message: str = ""


@dataclass
class CronRunRecord:
    """A single execution record for a cron job."""

    run_at: float
    status: Literal["ok", "error", "skipped"]
    duration_ms: int = 0
    error: str | None = None


@dataclass
class CronJobState:
    """Runtime state of a job."""

    next_run_at: float | None = None
    last_run_at: float | None = None
    last_status: Literal["ok", "error", "skipped"] | None = None
    last_error: str | None = None
    run_history: list[CronRunRecord] = field(default_factory=list)


@dataclass
class CronJob:
    """A scheduled job."""

    id: str
    name: str
    enabled: bool = True
    schedule: CronSchedule = field(
        default_factory=lambda: CronSchedule(kind="every")
    )
    payload: CronPayload = field(default_factory=CronPayload)
    state: CronJobState = field(default_factory=CronJobState)
    created_at: float = 0.0
    updated_at: float = 0.0
    delete_after_run: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CronJob":
        schedule = CronSchedule(**data.get("schedule", {"kind": "every"}))
        payload = CronPayload(**data.get("payload", {}))
        state_data = dict(data.get("state", {}))
        state_data["run_history"] = [
            CronRunRecord(**r) if isinstance(r, dict) else r
            for r in state_data.get("run_history", [])
        ]
        state = CronJobState(**state_data)
        return cls(
            id=data["id"],
            name=data["name"],
            enabled=data.get("enabled", True),
            schedule=schedule,
            payload=payload,
            state=state,
            created_at=data.get("created_at", 0.0),
            updated_at=data.get("updated_at", 0.0),
            delete_after_run=data.get("delete_after_run", False),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "schedule": {
                "kind": self.schedule.kind,
                "at": self.schedule.at,
                "every": self.schedule.every,
            },
            "payload": {
                "message": self.payload.message,
            },
            "state": {
                "next_run_at": self.state.next_run_at,
                "last_run_at": self.state.last_run_at,
                "last_status": self.state.last_status,
                "last_error": self.state.last_error,
                "run_history": [
                    {
                        "run_at": r.run_at,
                        "status": r.status,
                        "duration_ms": r.duration_ms,
                        "error": r.error,
                    }
                    for r in self.state.run_history
                ],
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "delete_after_run": self.delete_after_run,
        }
