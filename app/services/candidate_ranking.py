from __future__ import annotations

from app.models import RankedCandidate, RohSegment, VariantAnnotation


def is_variant_in_roh(item: VariantAnnotation, roh_segments: list[RohSegment] | None) -> bool:
    if not roh_segments:
        return False
    return any(
        segment.contig == item.contig
        and item.pos_1based >= segment.start_1based
        and item.pos_1based <= segment.end_1based
        for segment in roh_segments
    )


def rank_candidate_score(item: VariantAnnotation) -> int:
    score = 0
    significance = (item.clinical_significance or "").lower()
    consequence = (item.consequence or "").lower()
    af = _parse_af(item.gnomad_af)

    if "pathogenic" in significance:
        score += 5
    elif "vus" in significance:
        score += 2
    elif "benign" in significance:
        score -= 2

    if "splice" in consequence:
        score += 4
    elif "missense" in consequence:
        score += 3
    elif "stop" in consequence or "frameshift" in consequence:
        score += 5
    elif "synonymous" in consequence:
        score -= 1

    if af is not None:
        if af < 0.001:
            score += 3
        elif af < 0.01:
            score += 2
        elif af > 0.05:
            score -= 2

    if item.genotype == "1/1":
        score += 1

    return score


def rank_recessive_score(item: VariantAnnotation, roh_segments: list[RohSegment] | None) -> int:
    score = 0
    consequence = (item.consequence or "").lower()
    significance = (item.clinical_significance or "").lower()
    af = _parse_af(item.gnomad_af)

    if item.genotype == "1/1":
        score += 4
    if is_variant_in_roh(item, roh_segments):
        score += 5
    if "splice" in consequence:
        score += 4
    elif "missense" in consequence:
        score += 3
    elif "stop" in consequence or "frameshift" in consequence:
        score += 5
    elif "synonymous" in consequence:
        score -= 2

    if af is not None:
        if af < 0.001:
            score += 4
        elif af < 0.01:
            score += 2
        elif af > 0.05:
            score -= 3

    if "pathogenic" in significance:
        score += 3
    elif "benign" in significance:
        score -= 3

    return score


def build_ranked_candidates(
    annotations: list[VariantAnnotation],
    roh_segments: list[RohSegment] | None,
    limit: int = 8,
) -> list[RankedCandidate]:
    ranked = [
        RankedCandidate(
            item=item,
            score=rank_candidate_score(item) + (3 if is_variant_in_roh(item, roh_segments) else 0) + (1 if item.genotype == "1/1" else 0),
            in_roh=is_variant_in_roh(item, roh_segments),
        )
        for item in annotations
    ]
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked[:limit]


def _parse_af(raw_value: str) -> float | None:
    if not raw_value:
        return None
    token = raw_value.strip().split(" ", 1)[0]
    try:
        return float(token)
    except ValueError:
        return None
