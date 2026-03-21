from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.models import VariantAnnotation
from app.services.revel_lookup import enrich_annotations_with_revel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    annotations = [VariantAnnotation(**item) for item in payload.get("annotations", [])]
    genome_build_guess = payload.get("genome_build_guess")
    enriched, lookup_performed, matched_count = enrich_annotations_with_revel(annotations, genome_build_guess)
    result = {
        "annotations": [item.model_dump() for item in enriched],
        "lookup_performed": lookup_performed,
        "matched_count": matched_count,
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
