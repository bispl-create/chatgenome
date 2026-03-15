from __future__ import annotations

from app.models import AnalysisFacts, RecommendationItem


def build_recommendations(facts: AnalysisFacts) -> list[RecommendationItem]:
    recommendations: list[RecommendationItem] = []

    if not facts.samples:
        recommendations.append(
            RecommendationItem(
                id="REC1",
                title="Confirm sample-level metadata",
                rationale="The file does not expose sample names, which makes downstream interpretation harder.",
                action="Check whether the VCF was stripped of sample columns or exported in a site-only form.",
                priority="high",
            )
        )
    else:
        recommendations.append(
            RecommendationItem(
                id="REC1",
                title="Attach deterministic annotation before LLM interpretation",
                rationale="Raw VCF rows do not provide clinical meaning on their own.",
                action="Run VEP or snpEff, then add ClinVar and gnomAD lookups before generating narrative output.",
                priority="high",
            )
        )

    if "symbolic" in facts.variant_types:
        recommendations.append(
            RecommendationItem(
                id="REC2",
                title="Handle symbolic ALT alleles separately",
                rationale="Symbolic alleles such as <*> can represent non-concrete alternate states and should not be over-interpreted.",
                action="Split symbolic ALT records into a dedicated review path in the UI and annotation pipeline.",
                priority="medium",
            )
        )

    homozygous_alt = facts.genotype_counts.get("1/1", 0)
    heterozygous = facts.genotype_counts.get("0/1", 0) + facts.genotype_counts.get("1/0", 0)
    if homozygous_alt > heterozygous:
        recommendations.append(
            RecommendationItem(
                id="REC3",
                title="Evaluate homozygosity patterns",
                rationale="A high number of homozygous alternate calls can be relevant for ROH, ancestry, or recessive filtering workflows.",
                action="Add runs-of-homozygosity analysis and recessive-model filtering to the next analysis stage.",
                priority="medium",
            )
        )

    if facts.genome_build_guess is None:
        recommendations.append(
            RecommendationItem(
                id="REC4",
                title="Resolve genome build before annotation",
                rationale="Annotation and literature joins can become misleading when the assembly is uncertain.",
                action="Infer the genome build from header metadata or require the user to confirm GRCh37 vs GRCh38.",
                priority="high",
            )
        )

    return recommendations
