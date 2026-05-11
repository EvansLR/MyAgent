"""JSON file persistence for cron jobs."""

import json
import os
import time
from pathlib import Path
from typing import Any

from myagent.cron.types import CronJob


class CronStore:
    """Persistent store for cron jobs backed by a JSON file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[CronJob]:
        """Load jobs from disk.

        Returns an empty list when the store file does not exist.
        Raises RuntimeError when the file exists but cannot be parsed;
        the corrupt file is preserved with a ``.corrupt-{timestamp}`` suffix.
        """
        if not self.path.exists():
            return []
        try:
            data: dict[str, Any] = json.loads(
                self.path.read_text(encoding="utf-8")
            )
            return [CronJob.from_dict(j) for j in data.get("jobs", [])]
        except Exception:
            backup = self.path.with_suffix(
                self.path.suffix + f".corrupt-{int(time.time())}"
            )
            try:
                self.path.rename(backup)
            except OSError:
                pass
            raise RuntimeError(
                f"cron store at {self.path} is corrupt and was preserved; "
                "refusing to overwrite to avoid data loss."
            ) from None

    def save(self, jobs: list[CronJob]) -> None:
        """Save jobs to disk atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "jobs": [j.to_dict() for j in jobs]}
        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._atomic_write(self.path, content)

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        """Write *content* to *path* atomically with fsync.

        Uses a temp-file + ``os.replace`` + ``fsync`` pattern so a crash
        or SIGKILL mid-write cannot leave the destination truncated.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
