from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.models import AnalysisFacts
from app.services.variant_annotation import annotate_variants


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    facts = AnalysisFacts(**payload["facts"])
    annotations = annotate_variants(
        payload["vcf_path"],
        facts,
        scope=payload.get("scope", "representative"),
        limit=payload.get("limit"),
    )

    result = {"annotations": [item.model_dump() for item in annotations]}
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
