from __future__ import annotations

import argparse
import json
from pathlib import Path


def _has_meaningful_text(value: str | None) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text and text not in {".", "n/a", "NA"})


def _detail(label: str, count: int, total: int) -> dict[str, object]:
    percent = round((count / total) * 100) if total else 0
    return {"label": label, "count": count, "detail": f"{count}/{total} annotated ({percent}%)"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    annotations = payload.get("annotations", [])
    total = len(annotations)
    summary = [
        _detail(
            "ClinVar coverage",
            sum(
                1
                for item in annotations
                if _has_meaningful_text(item.get("clinical_significance")) or _has_meaningful_text(item.get("clinvar_conditions"))
            ),
            total,
        ),
        _detail("gnomAD coverage", sum(1 for item in annotations if _has_meaningful_text(item.get("gnomad_af"))), total),
        _detail("Gene mapping", sum(1 for item in annotations if _has_meaningful_text(item.get("gene"))), total),
        _detail(
            "HGVS coverage",
            sum(1 for item in annotations if _has_meaningful_text(item.get("hgvsc")) or _has_meaningful_text(item.get("hgvsp"))),
            total,
        ),
        _detail("Protein change", sum(1 for item in annotations if _has_meaningful_text(item.get("hgvsp"))), total),
    ]
    Path(args.output).write_text(json.dumps({"clinical_coverage_summary": summary}, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
