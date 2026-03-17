from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def _label(text: str, fallback: str) -> str:
    value = (text or "").strip()
    return value if value and value != "." else fallback


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    annotations = payload.get("annotations", [])
    counts = Counter(_label(item.get("clinical_significance", ""), "Unreviewed") for item in annotations)
    summary = [{"label": label, "count": count} for label, count in counts.most_common()]
    Path(args.output).write_text(json.dumps({"clinvar_summary": summary}, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
