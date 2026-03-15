from __future__ import annotations

from app.models import AnalysisFacts, VariantAnnotation


def build_ui_cards(facts: AnalysisFacts, annotations: list[VariantAnnotation]) -> list[dict[str, object]]:
    cards: list[dict[str, object]] = [
        {
            "type": "summary",
            "title": "VCF Overview",
            "items": [
                f"Records: {facts.record_count}",
                f"Samples: {len(facts.samples)}",
                f"Build guess: {facts.genome_build_guess or 'unknown'}",
            ],
        },
        {
            "type": "variant_types",
            "title": "Variant Types",
            "items": [f"{name}: {count}" for name, count in sorted(facts.variant_types.items())],
        },
        {
            "type": "qc",
            "title": "QC Summary",
            "items": [
                f"PASS rate: {facts.qc.pass_rate:.1%}" if facts.qc.pass_rate is not None else "PASS rate: unavailable",
                f"Missing GT rate: {facts.qc.missing_gt_rate:.1%}" if facts.qc.missing_gt_rate is not None else "Missing GT rate: unavailable",
                f"Ti/Tv: {facts.qc.transition_transversion_ratio:.2f}" if facts.qc.transition_transversion_ratio is not None else "Ti/Tv: unavailable",
                f"Het/HomAlt: {facts.qc.het_hom_alt_ratio:.2f}" if facts.qc.het_hom_alt_ratio is not None else "Het/HomAlt: unavailable",
            ],
        },
        {
            "type": "examples",
            "title": "Example Variants",
            "items": [
                f"{item.contig}:{item.pos_1based} {item.ref}>{','.join(item.alts) or '.'} GT={item.genotype}"
                for item in facts.example_variants[:5]
            ],
        },
    ]
    if annotations:
        cards.append(
            {
                "type": "annotations",
                "title": "Representative Annotations",
                "items": [
                    (
                        f"{item.contig}:{item.pos_1based} {item.ref}>{','.join(item.alts)} "
                        f"{item.gene} {item.consequence} rsID={item.rsid} "
                        f"HGVSc={item.hgvsc} HGVSp={item.hgvsp} "
                        f"ClinSig={item.clinical_significance} gnomAD={item.gnomad_af}"
                    )
                    for item in annotations[:4]
                ],
            }
        )
    if facts.warnings:
        cards.append(
            {
                "type": "warnings",
                "title": "Warnings",
                "items": facts.warnings,
            }
        )
    return cards


def build_draft_answer(
    facts: AnalysisFacts,
    annotations: list[VariantAnnotation],
    reference_ids: list[str],
    recommendation_ids: list[str],
) -> str:
    build_text = facts.genome_build_guess or "an unknown genome build"
    first_ref = reference_ids[0] if reference_ids else "REF"
    rec_text = ", ".join(recommendation_ids) if recommendation_ids else "no recommendations"
    annotation_text = ""
    if annotations:
        top = annotations[0]
        annotation_text = (
            f" Representative annotation includes {top.contig}:{top.pos_1based} "
            f"in {top.gene or 'an unknown gene'} with consequence {top.consequence}, rsID {top.rsid}, "
            f"HGVSc {top.hgvsc}, and HGVSp {top.hgvsp}. "
        )
    return (
        f"This VCF contains {facts.record_count} records across {len(facts.chrom_counts)} contig(s) "
        f"and appears to align to {build_text}. The file should be explained with grounded VCF semantics, "
        f"not direct model inference, especially because clinical annotation should be attached before any strong claim [{first_ref}]."
        f" QC-wise, the PASS rate is "
        f"{f'{facts.qc.pass_rate:.1%}' if facts.qc.pass_rate is not None else 'unavailable'}"
        f" and the Ti/Tv ratio is "
        f"{f'{facts.qc.transition_transversion_ratio:.2f}' if facts.qc.transition_transversion_ratio is not None else 'unavailable'}."
        f"{annotation_text}"
        f"Recommended next steps are captured in {rec_text}."
    )
