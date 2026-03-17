from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.vcf_summary import summarize_vcf  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    vcf_path = payload["vcf_path"]
    max_examples = int(payload.get("max_examples", 8))

    facts = summarize_vcf(vcf_path, max_examples=max_examples)
    result = {
      "tool": "vcf_qc_tool",
      "facts": facts.model_dump(),
      "summary": (
          f"Summarized {facts.file_name}: {facts.record_count} record(s), "
          f"{len(facts.samples)} sample(s), build guess {facts.genome_build_guess or 'unknown'}."
      ),
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
