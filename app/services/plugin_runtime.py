from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable


def run_plugin_cli(execute: Callable[[dict[str, Any]], Any]) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = execute(payload)
    if hasattr(result, "model_dump"):
        serialized = result.model_dump()
    else:
        serialized = result
    Path(args.output).write_text(
        json.dumps(serialized, ensure_ascii=False),
        encoding="utf-8",
    )
