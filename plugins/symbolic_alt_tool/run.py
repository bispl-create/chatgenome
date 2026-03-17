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
    symbolic = [
        item
        for item in annotations
        if any(str(alt).startswith("<") and str(alt).endswith(">") for alt in item.get("alts", []))
    ]
    summary = {
        "count": len(symbolic),
        "examples": [
            {
                "locus": f"{item.get('contig')}:{item.get('pos_1based')}",
                "gene": item.get("gene") or "",
                "alts": item.get("alts", []),
                "consequence": item.get("consequence") or "",
                "genotype": item.get("genotype") or "",
            }
            for item in symbolic[:5]
        ],
    }
    Path(args.output).write_text(json.dumps({"symbolic_alt_summary": summary}, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
