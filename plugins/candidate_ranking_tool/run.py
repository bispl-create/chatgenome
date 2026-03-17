from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.models import RohSegment, VariantAnnotation
from app.services.candidate_ranking import build_ranked_candidates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    annotations = [VariantAnnotation(**item) for item in payload.get("annotations", [])]
    roh_segments = [RohSegment(**item) for item in payload.get("roh_segments", [])]
    limit = int(payload.get("limit", 8))
    ranked = build_ranked_candidates(annotations, roh_segments, limit=limit)

    result = {"candidate_variants": [item.model_dump() for item in ranked]}
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
