from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


def _cache_root() -> Path:
    root = os.getenv(
        "VCF_EVIDENCE_CACHE_DIR",
        "/Users/jongcye/Documents/Codex/workspace/bioinformatics_vcf_evidence_mvp/.cache",
    )
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _namespace_dir(namespace: str) -> Path:
    path = _cache_root() / namespace
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_path(namespace: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return _namespace_dir(namespace) / f"{digest}.json"


def load_cache(namespace: str, key: str, ttl_seconds: int) -> Any | None:
    path = _cache_path(namespace, key)
    if not path.exists():
        return None
    if ttl_seconds > 0 and time.time() - path.stat().st_mtime > ttl_seconds:
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def save_cache(namespace: str, key: str, payload: Any) -> None:
    path = _cache_path(namespace, key)
    path.write_text(json.dumps(payload))
