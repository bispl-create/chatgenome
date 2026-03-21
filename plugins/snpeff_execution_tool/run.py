from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.models import SnpEffRequest
from app.services.snpeff import run_snpeff


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    request = SnpEffRequest(**payload)
    response = run_snpeff(request)
    Path(args.output).write_text(response.model_dump_json(), encoding="utf-8")


if __name__ == "__main__":
    main()
