from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.models import AnalysisFacts, RecommendationItem, ReferenceItem, VariantAnnotation
from app.services.annotation import build_draft_answer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    facts = AnalysisFacts(**payload["facts"])
    annotations = [VariantAnnotation(**item) for item in payload.get("annotations", [])]
    references = [ReferenceItem(**item) for item in payload.get("references", [])]
    recommendations = [RecommendationItem(**item) for item in payload.get("recommendations", [])]

    draft_answer = build_draft_answer(
        facts,
        annotations,
        [item.id for item in references],
        [item.id for item in recommendations],
    )
    result = {"draft_answer": draft_answer}
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
