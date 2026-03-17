from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    annotations = payload.get("annotations", [])
    unique_genes = {str(item.get("gene", "")).strip() for item in annotations if str(item.get("gene", "")).strip() not in {"", "."}}
    clinvar_labeled = sum(1 for item in annotations if str(item.get("clinical_significance", "")).strip() not in {"", "."})
    symbolic = sum(
        1
        for item in annotations
        if any(str(alt).startswith("<") and str(alt).endswith(">") for alt in item.get("alts", []))
    )
    summary = [
        {"label": "Annotated rows", "count": len(annotations), "detail": f"{len(annotations)} rows currently available in the triage table"},
        {"label": "Distinct genes", "count": len(unique_genes), "detail": f"{len(unique_genes)} genes represented in the annotated subset"},
        {"label": "ClinVar-labeled rows", "count": clinvar_labeled, "detail": f"{clinvar_labeled} rows contain a ClinVar-style significance label"},
        {"label": "Symbolic ALT rows", "count": symbolic, "detail": f"{symbolic} rows are symbolic ALT records that may need separate handling"},
    ]
    Path(args.output).write_text(json.dumps({"filtering_summary": summary}, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
