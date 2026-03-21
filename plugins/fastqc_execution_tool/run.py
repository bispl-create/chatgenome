from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.fastqc import run_fastqc_local  # noqa: E402
from app.services.tool_runner import discover_tools  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    raw_path = payload["raw_path"]
    original_name = payload.get("original_name") or Path(raw_path).name
    result = run_fastqc_local(raw_path, original_name, discover_tools())
    Path(args.output).write_text(
        json.dumps(result.model_dump(), ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
