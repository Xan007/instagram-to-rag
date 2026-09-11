"""Background job manager for long-running pipeline operations."""
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Any, Callable, Dict, Optional

from storage.db import get_session
import storage.repositories as repo

logger = logging.getLogger(__name__)


def _run_job_process(job_id: str, kind: str, fn: Callable, args: tuple, kwargs: dict):
    # This runs in a separate process or thread.
    db = get_session()
    try:
        job = repo.get_job(db, job_id)
        if not job:
            return
        
        job.status = "running"
        job.started_at = time.time()
        repo.update_job(db, job)
        
        def progress(msg: str):
            repo.append_job_log(db, job_id, msg)
            logger.info("[job %s] %s", job_id, msg)

        if "progress_kw" in kwargs:
            pk = kwargs.pop("progress_kw")
            if pk:
                kwargs[pk] = progress

        result = fn(*args, **kwargs)
        
        job = repo.get_job(db, job_id)
        job.result = result
        job.status = "completed"
        
    except Exception as e:
        logger.exception("Job %s failed", job_id)
        job = repo.get_job(db, job_id)
        if job:
            job.error = f"{type(e).__name__}: {e}"
            job.status = "failed"
            repo.append_job_log(db, job_id, job.error)
    finally:
        job = repo.get_job(db, job_id)
        if job:
            job.finished_at = time.time()
            repo.update_job(db, job)
        db.close()

class JobManager:
    """Serializes heavy pipeline jobs on a single worker."""

    def __init__(self, max_workers: int = 1):
        # We use ThreadPoolExecutor because network IO (Pinecone, Gemini, Apify) 
        # and Subprocesses (ffmpeg) release the GIL. True multiprocessing isn't 
        # strictly necessary for Pinecone, but ThreadPool provides clean isolation.
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        
    def submit(
        self,
        kind: str,
        fn: Callable[..., Any],
        *args: Any,
        progress_kw: Optional[str] = "progress",
        **kwargs: Any,
    ):
        job_id = uuid.uuid4().hex[:12]
        db = get_session()
        try:
            job = repo.create_job(db, job_id, kind)
        finally:
            db.close()

        kwargs["progress_kw"] = progress_kw
        self._executor.submit(_run_job_process, job_id, kind, fn, args, kwargs)
        return type('DummyJob', (), {'id': job_id, 'kind': kind})()

    def get(self, job_id: str):
        db = get_session()
        try:
            job = repo.get_job(db, job_id)
            if not job:
                return None
            
            # Match old in-memory interface for api.py
            class JobAdapter:
                def __init__(self, j):
                    self.id = j.id
                    self.kind = j.kind
                    self.status = j.status
                    self.created_at = j.created_at
                    self.started_at = j.started_at
                    self.finished_at = j.finished_at
                    self.result = j.result
                    self.error = j.error
                    self.log = j.log or []

                def to_dict(self, include_log=True, log_limit=200):
                    return {
                        "id": self.id,
                        "kind": self.kind,
                        "status": self.status,
                        "created_at": self.created_at,
                        "started_at": self.started_at,
                        "finished_at": self.finished_at,
                        "duration_s": round((self.finished_at or time.time()) - self.started_at, 1) if self.started_at else None,
                        "result": self.result,
                        "error": self.error,
                        "log": self.log[-log_limit:] if include_log else None,
                    }
            return JobAdapter(job)
        finally:
            db.close()

    def current(self):
        db = get_session()
        try:
            from storage.models import JobRecord
            job = db.query(JobRecord).filter(JobRecord.status == "running").first()
            return self.get(job.id) if job else None
        finally:
            db.close()

    def all_jobs(self):
        db = get_session()
        try:
            from storage.models import JobRecord
            jobs = db.query(JobRecord).order_by(JobRecord.created_at.desc()).all()
            return [self.get(j.id) for j in jobs]
        finally:
            db.close()


manager = JobManager()
