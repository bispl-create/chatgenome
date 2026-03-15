from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable


JOB_STORE: dict[str, dict[str, Any]] = {}
JOB_LOCK = threading.Lock()


def create_job() -> str:
    job_id = str(uuid.uuid4())
    with JOB_LOCK:
        JOB_STORE[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "created_at": time.time(),
            "updated_at": time.time(),
            "result": None,
            "error": None,
        }
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    with JOB_LOCK:
        return JOB_STORE.get(job_id)


def run_job(job_id: str, fn: Callable[[], Any]) -> None:
    def target() -> None:
        with JOB_LOCK:
            JOB_STORE[job_id]["status"] = "running"
            JOB_STORE[job_id]["updated_at"] = time.time()
        try:
            result = fn()
            with JOB_LOCK:
                JOB_STORE[job_id]["status"] = "completed"
                JOB_STORE[job_id]["result"] = result
                JOB_STORE[job_id]["updated_at"] = time.time()
        except Exception as exc:
            with JOB_LOCK:
                JOB_STORE[job_id]["status"] = "failed"
                JOB_STORE[job_id]["error"] = str(exc)
                JOB_STORE[job_id]["updated_at"] = time.time()

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
