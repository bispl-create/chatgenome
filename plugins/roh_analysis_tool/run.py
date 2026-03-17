from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.roh_analysis import run_roh_analysis  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    vcf_path = payload["vcf_path"]
    segments = run_roh_analysis(vcf_path)
    result = {
      "tool": "roh_analysis_tool",
      "roh_segments": [segment.model_dump() for segment in segments],
      "summary": f"Detected {len(segments)} ROH segment(s).",
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
