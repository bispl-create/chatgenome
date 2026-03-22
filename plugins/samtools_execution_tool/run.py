from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.models import SamtoolsRequest  # noqa: E402
from app.services.samtools import run_samtools  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    request = SamtoolsRequest(**payload)
    result = run_samtools(request)
    Path(args.output).write_text(
        json.dumps(result.model_dump(), ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
