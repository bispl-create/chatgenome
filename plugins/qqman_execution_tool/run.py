from __future__ import annotations

import json
import sys

from app.models import QqmanAssociationRequest
from app.services.r_vcf_plots import run_qqman_association


def main() -> int:
    payload = json.load(sys.stdin)
    result = run_qqman_association(QqmanAssociationRequest(**payload))
    json.dump(result.model_dump(), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
