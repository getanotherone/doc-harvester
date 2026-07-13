import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional


class TaskStatus:
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskRecord:
    task_id: str
    status: str = TaskStatus.ACCEPTED
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    progress: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    thread: Optional[threading.Thread] = None


class TaskRegistry:
    def __init__(self):
        self._tasks: Dict[str, TaskRecord] = {}
        self._lock = threading.Lock()

    def create(self) -> TaskRecord:
        task_id = str(uuid.uuid4())
        record = TaskRecord(task_id=task_id)
        with self._lock:
            self._tasks[task_id] = record
        return record

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            return self._tasks.get(task_id)

    def active_count(self) -> int:
        with self._lock:
            return sum(
                1
                for r in self._tasks.values()
                if r.status in (TaskStatus.ACCEPTED, TaskStatus.RUNNING)
            )

    def submit(self, task_id: str, fn: Callable, *args, **kwargs) -> None:
        record = self.get(task_id)
        if not record:
            return

        def _runner():
            record.status = TaskStatus.RUNNING
            record.started_at = datetime.now(timezone.utc)
            try:
                result = fn(*args, **kwargs)
                record.result = result
                record.status = TaskStatus.COMPLETED
            except Exception as exc:
                record.error = str(exc)
                record.status = TaskStatus.FAILED
            finally:
                record.finished_at = datetime.now(timezone.utc)

        t = threading.Thread(target=_runner, daemon=True)
        record.thread = t
        t.start()


registry = TaskRegistry()
