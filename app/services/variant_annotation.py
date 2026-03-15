from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Iterable

import pysam

from app.models import AnalysisFacts, TranscriptAnnotation, VariantAnnotation, VariantExample
from app.services.cache_store import load_cache, save_cache


def _ensembl_base_url(build_guess: str | None) -> str:
    if build_guess and "GRCh37" in build_guess:
        return "https://grch37.rest.ensembl.org"
    return "https://rest.ensembl.org"


def _get_json(url: str) -> object:
    ttl_seconds = int(os.getenv("EXTERNAL_HTTP_CACHE_TTL_SECONDS", "86400"))
    cached = load_cache("http_json", url, ttl_seconds=ttl_seconds)
    if cached is not None:
        return cached

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Bioinformatics-VCF-Evidence-MVP/0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=float(os.getenv("ANNOTATION_TIMEOUT_SECONDS", "8"))) as response:
        payload = json.loads(response.read().decode("utf-8"))
    save_cache("http_json", url, payload)
    return payload


def _match_variant(variant_items: list[dict], ref: str, alts: list[str]) -> dict | None:
    alt_set = set(alts)
    for item in variant_items:
        alleles = set(item.get("alleles") or [])
        if ref in alleles and alt_set.intersection(alleles):
            return item
    return variant_items[0] if variant_items else None


def _fetch_refsnp_annotation(rsid: str) -> dict | None:
    numeric = rsid.removeprefix("rs")
    if not numeric.isdigit():
        return None
    payload = _get_json(f"https://api.ncbi.nlm.nih.gov/variation/v0/refsnp/{numeric}")
    return payload if isinstance(payload, dict) else None


def _fetch_vep_annotation(base_url: str, contig: str, pos_1based: int, alt: str) -> dict | None:
    region = f"{contig}:{pos_1based}-{pos_1based}"
    encoded_region = urllib.parse.quote(region, safe=":-")
    encoded_alt = urllib.parse.quote(alt, safe="")
    url = (
        f"{base_url}/vep/human/region/{encoded_region}/{encoded_alt}"
        "?hgvs=1&protein=1&numbers=1&canonical=1&xref_refseq=1&transcript_version=1"
    )
    payload = _get_json(url)
    if isinstance(payload, list) and payload:
        first = payload[0]
        return first if isinstance(first, dict) else None
    return payload if isinstance(payload, dict) else None


def _match_allele_annotation(refsnp_payload: dict, ref: str, alt: str) -> dict | None:
    snapshot = refsnp_payload.get("primary_snapshot_data", {})
    allele_annotations = snapshot.get("allele_annotations", [])
    placements = snapshot.get("placements_with_allele", [])

    for placement in placements:
        alleles = placement.get("alleles", [])
        for idx, allele_info in enumerate(alleles):
            spdi = allele_info.get("allele", {}).get("spdi", {})
            if (
                spdi.get("deleted_sequence") == ref
                and spdi.get("inserted_sequence") == alt
                and idx < len(allele_annotations)
            ):
                return allele_annotations[idx]
    return None


def _best_gnomad_af(allele_annotation: dict) -> str:
    best_value: float | None = None
    best_label = "."
    for entry in allele_annotation.get("frequency", []):
        study_name = entry.get("study_name", "")
        if "GnomAD" not in study_name:
            continue
        allele_count = entry.get("allele_count")
        total_count = entry.get("total_count")
        if not isinstance(allele_count, int) or not isinstance(total_count, int) or total_count == 0:
            continue
        value = allele_count / total_count
        if best_value is None or value > best_value:
            best_value = value
            best_label = f"{value:.6g} ({study_name})"
    return best_label


def _best_clinvar_summary(allele_annotation: dict) -> tuple[str, str, str, str]:
    clinical_entries = allele_annotation.get("clinical", [])
    if not clinical_entries:
        return ".", ".", ".", "."

    rank = {
        "practice_guideline": 5,
        "reviewed_by_expert_panel": 4,
        "criteria_provided_multiple_submitters_no_conflicts": 3,
        "criteria_provided_single_submitter": 2,
        "criteria_provided_conflicting_classifications": 1,
        "no_assertion_criteria_provided": 0,
    }

    def has_informative_disease(item: dict) -> bool:
        names = [name.strip().lower() for name in item.get("disease_names") or []]
        return any(name not in {"not provided", "not specified", "."} for name in names)

    best = sorted(
        clinical_entries,
        key=lambda item: (
            has_informative_disease(item),
            rank.get(item.get("review_status", ""), -1),
        ),
        reverse=True,
    )[0]

    significance = ",".join(best.get("clinical_significances") or []) or "."
    review_status = best.get("review_status", ".")
    conditions = ",".join(best.get("disease_names") or []) or "."
    accession = best.get("accession_version", ".")
    return significance, review_status, conditions, accession


def _sorted_transcript_consequences(vep_payload: dict | None) -> list[dict]:
    if not isinstance(vep_payload, dict):
        return []

    transcript_consequences = vep_payload.get("transcript_consequences") or []
    if not transcript_consequences:
        return []

    def sort_key(item: dict) -> tuple[int, int, int, str]:
        canonical = 1 if item.get("canonical") else 0
        mane = 1 if item.get("mane_select") else 0
        biotype = 1 if item.get("biotype") == "protein_coding" else 0
        transcript_id = item.get("transcript_id", "")
        return (canonical, mane, biotype, transcript_id)

    return sorted(transcript_consequences, key=sort_key, reverse=True)


def _to_transcript_annotation(item: dict) -> TranscriptAnnotation:
    return TranscriptAnnotation(
        transcript_id=item.get("transcript_id", "."),
        transcript_biotype=item.get("biotype", "."),
        canonical="yes" if item.get("canonical") else "no",
        exon=str(item.get("exon", ".")) if item.get("exon") is not None else ".",
        intron=str(item.get("intron", ".")) if item.get("intron") is not None else ".",
        hgvsc=item.get("hgvsc", "."),
        hgvsp=item.get("hgvsp", "."),
        protein_id=item.get("protein_id", "."),
        amino_acids=item.get("amino_acids", "."),
        codons=item.get("codons", "."),
    )


def _iter_examples_from_vcf(path: str, limit: int | None) -> Iterable[VariantExample]:
    emitted = 0
    with pysam.VariantFile(path) as vcf:
        sample_names = list(vcf.header.samples)
        first_sample = sample_names[0] if sample_names else None
        for rec in vcf:
            if limit is not None and emitted >= limit:
                break
            alts = list(rec.alts or [])
            genotype = "."
            if first_sample:
                gt = rec.samples[first_sample].get("GT")
                genotype = "." if gt is None else "/".join("." if x is None else str(x) for x in gt)
            variant_class = "no_alt"
            if alts:
                classes = sorted(
                    {
                        "symbolic"
                        if alt.startswith("<") and alt.endswith(">")
                        else "SNV"
                        if len(rec.ref) == 1 and len(alt) == 1
                        else "INS"
                        if len(rec.ref) < len(alt)
                        else "DEL"
                        if len(rec.ref) > len(alt)
                        else "MNV_or_complex"
                        for alt in alts
                    }
                )
                variant_class = ",".join(classes)

            emitted += 1
            yield VariantExample(
                contig=rec.contig,
                pos_1based=rec.pos,
                ref=rec.ref,
                alts=alts,
                genotype=genotype,
                variant_class=variant_class,
            )


def _annotate_single_variant(base_url: str, example: VariantExample) -> VariantAnnotation | None:
    region_url = (
        f"{base_url}/overlap/region/human/"
        f"{example.contig}:{example.pos_1based}-{example.pos_1based}"
        "?feature=variation;feature=gene"
    )
    payload = _get_json(region_url)
    if not isinstance(payload, list):
        return None

    variant_items = [item for item in payload if item.get("feature_type") == "variation"]
    gene_items = [item for item in payload if item.get("feature_type") == "gene"]
    matched = _match_variant(variant_items, example.ref, example.alts)
    rsid = matched.get("id", ".") if matched else "."
    consequence = matched.get("consequence_type", ".") if matched else "."
    clinical = ",".join(matched.get("clinical_significance") or []) if matched else ""
    gene = ",".join(sorted({item.get("external_name") or item.get("id") for item in gene_items})) or "."
    maf = "."
    clinvar_accession = "."
    clinvar_review_status = "."
    clinvar_conditions = "."
    gnomad_af = "."
    source_url = "."
    transcript_id = "."
    transcript_biotype = "."
    canonical = "."
    exon = "."
    intron = "."
    hgvsc = "."
    hgvsp = "."
    protein_id = "."
    amino_acids = "."
    codons = "."
    transcript_options: list[TranscriptAnnotation] = []

    if rsid != ".":
        try:
            detail = _get_json(f"{base_url}/variation/human/{urllib.parse.quote(rsid)}")
            if isinstance(detail, dict):
                maf = str(detail.get("MAF", "."))
                if not clinical:
                    clinical = ",".join(detail.get("clinical_significance") or [])
            source_url = (
                "https://grch37.ensembl.org/Homo_sapiens/Variation/Explore?v="
                if "grch37" in base_url
                else "https://www.ensembl.org/Homo_sapiens/Variation/Explore?v="
            ) + urllib.parse.quote(rsid)
        except Exception:
            source_url = "."

        if example.alts:
            try:
                refsnp = _fetch_refsnp_annotation(rsid)
                if refsnp:
                    allele_annotation = _match_allele_annotation(refsnp, example.ref, example.alts[0])
                    if allele_annotation:
                        gnomad_af = _best_gnomad_af(allele_annotation)
                        clin_sig, review_status, conditions, accession = _best_clinvar_summary(allele_annotation)
                        if clin_sig != ".":
                            clinical = clin_sig
                        clinvar_review_status = review_status
                        clinvar_conditions = conditions
                        clinvar_accession = accession
            except Exception:
                pass

    if example.alts:
        try:
            vep_payload = _fetch_vep_annotation(base_url, example.contig, example.pos_1based, example.alts[0])
            sorted_transcripts = _sorted_transcript_consequences(vep_payload)
            transcript_options = [_to_transcript_annotation(item) for item in sorted_transcripts[:5]]
            transcript = sorted_transcripts[0] if sorted_transcripts else {}
            if transcript:
                transcript_id = transcript.get("transcript_id", ".")
                transcript_biotype = transcript.get("biotype", ".")
                canonical = "yes" if transcript.get("canonical") else "no"
                exon = str(transcript.get("exon", ".")) if transcript.get("exon") is not None else "."
                intron = str(transcript.get("intron", ".")) if transcript.get("intron") is not None else "."
                hgvsc = transcript.get("hgvsc", ".")
                hgvsp = transcript.get("hgvsp", ".")
                protein_id = transcript.get("protein_id", ".")
                amino_acids = transcript.get("amino_acids", ".")
                codons = transcript.get("codons", ".")
                if consequence in {"", "."}:
                    terms = transcript.get("consequence_terms") or []
                    consequence = ",".join(terms) if terms else "."
                if gene == ".":
                    gene = transcript.get("gene_symbol") or transcript.get("gene_id") or "."
        except Exception:
            pass

    return VariantAnnotation(
        contig=example.contig,
        pos_1based=example.pos_1based,
        ref=example.ref,
        alts=example.alts,
        genotype=example.genotype,
        rsid=rsid,
        gene=gene,
        consequence=consequence or ".",
        transcript_id=transcript_id,
        transcript_biotype=transcript_biotype,
        canonical=canonical,
        exon=exon,
        intron=intron,
        hgvsc=hgvsc,
        hgvsp=hgvsp,
        protein_id=protein_id,
        amino_acids=amino_acids,
        codons=codons,
        transcript_options=transcript_options,
        clinical_significance=clinical or ".",
        maf=maf,
        clinvar_accession=clinvar_accession,
        clinvar_review_status=clinvar_review_status,
        clinvar_conditions=clinvar_conditions,
        gnomad_af=gnomad_af,
        source_url=source_url,
    )


def annotate_variants(
    path: str,
    facts: AnalysisFacts,
    scope: str = "representative",
    limit: int | None = None,
) -> list[VariantAnnotation]:
    base_url = _ensembl_base_url(facts.genome_build_guess)
    results: list[VariantAnnotation] = []

    if scope == "all":
        effective_limit = limit
        if effective_limit is None:
            configured = int(os.getenv("MAX_ANNOTATED_VARIANTS_ALL", "200"))
            effective_limit = configured if configured > 0 else None
        candidates: Iterable[VariantExample] = _iter_examples_from_vcf(path, effective_limit)
    else:
        representative_limit = limit if limit is not None else int(os.getenv("MAX_EXAMPLE_VARIANT_ANNOTATIONS", "7"))
        candidates = facts.example_variants[:representative_limit]

    for example in candidates:
        try:
            annotation = _annotate_single_variant(base_url, example)
            if annotation is not None:
                results.append(annotation)
        except Exception:
            continue

    return results
