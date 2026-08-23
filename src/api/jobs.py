"""Background job manager for long-running pipeline operations."""
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional


class Job:
    def __init__(self, kind: str):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.status = "queued"
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self._log: deque = deque(maxlen=1000)
        self._lock = threading.Lock()

    def log_line(self, message: str) -> None:
        with self._lock:
            entry = f"[{time.strftime('%H:%M:%S')}] {message}"
            self._log.append(entry)
        print(f"[job {self.id}] {entry}", flush=True)

    def tail(self, limit: int = 200) -> list:
        with self._lock:
            items = list(self._log)
        return items[-limit:]

    def to_dict(self, include_log: bool = True, log_limit: int = 200) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": (
                round((self.finished_at or time.time()) - self.started_at, 1)
                if self.started_at
                else None
            ),
            "result": self.result,
            "error": self.error,
            "log": self.tail(log_limit) if include_log else None,
        }


class JobManager:
    """Serializes heavy pipeline jobs on a single worker thread."""

    def __init__(self, max_workers: int = 1):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(
        self,
        kind: str,
        fn: Callable[..., Any],
        *args: Any,
        progress_kw: Optional[str] = "progress",
        **kwargs: Any,
    ) -> Job:
        job = Job(kind)
        with self._lock:
            self._jobs[job.id] = job

        def _run():
            job.status = "running"
            job.started_at = time.time()
            try:
                if progress_kw:
                    kwargs[progress_kw] = job.log_line
                job.result = fn(*args, **kwargs)
                job.status = "completed"
            except Exception as e:
                job.error = f"{type(e).__name__}: {e}"
                job.status = "failed"
                job.log_line(job.error)
            finally:
                job.finished_at = time.time()

        self._executor.submit(_run)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def current(self) -> Optional[Job]:
        """The job currently holding the single worker slot, if any."""
        for job in self._jobs.values():
            if job.status == "running":
                return job
        return None

    def all_jobs(self) -> list:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)


manager = JobManager()
