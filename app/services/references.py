from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request

from app.models import AnalysisFacts, ReferenceItem, VariantAnnotation
from app.services.cache_store import load_cache, save_cache


def _base_references(facts: AnalysisFacts) -> list[ReferenceItem]:
    refs: list[ReferenceItem] = [
        ReferenceItem(
            id="REF1",
            title="The variant call format and VCFtools",
            source="Bioinformatics / PMC",
            url="https://pmc.ncbi.nlm.nih.gov/articles/PMC3137218/",
            note="Foundational reference for interpreting VCF fields and genotype encoding.",
        ),
        ReferenceItem(
            id="REF2",
            title="VCF version 4.2 specification",
            source="SAMtools / hts-specs",
            url="https://samtools.github.io/hts-specs/VCFv4.2.pdf",
            note="Primary technical specification for symbolic alleles, FILTER, FORMAT, and GT semantics.",
        ),
    ]

    if facts.file_name.startswith("roh") or any("1/1" in key for key in facts.genotype_counts):
        refs.append(
            ReferenceItem(
                id="REF3",
                title="BCFtools/RoH: a hidden Markov model approach for detecting autozygosity",
                source="Bioinformatics / PMC",
                url="https://pmc.ncbi.nlm.nih.gov/articles/PMC4892413/",
                note="Helpful when the VCF may be part of a runs-of-homozygosity workflow.",
            )
        )

    return refs


def _clean_condition(text: str) -> str:
    if not text or text == ".":
        return ""
    if text.lower() in {"not provided", "not specified"}:
        return ""
    return text


def _best_condition(text: str) -> str:
    cleaned = _clean_condition(text)
    if not cleaned:
        return ""
    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    informative = [
        part
        for part in parts
        if part.lower() not in {"not provided", "not specified", "."}
    ]
    if not informative:
        return ""
    informative.sort(key=len, reverse=True)
    return informative[0]


def _build_search_queries(facts: AnalysisFacts, annotations: list[VariantAnnotation]) -> list[dict[str, object]]:
    queries: list[dict[str, object]] = []
    seen: set[str] = set()
    max_query_count = int(os.getenv("LITERATURE_MAX_QUERIES", "6"))

    def add_query(query: str, priority: int, label: str) -> None:
        if len(queries) >= max_query_count:
            return
        normalized = " ".join(query.split())
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        queries.append({"query": normalized, "priority": priority, "label": label})

    # Annotation-driven queries first.
    sorted_annotations = sorted(
        annotations,
        key=lambda item: (
            item.clinical_significance != ".",
            item.genotype == "1/1",
            item.consequence in {"missense_variant", "splice_acceptor_variant"},
            item.rsid != ".",
        ),
        reverse=True,
    )
    for annotation in sorted_annotations[:3]:
        alt = annotation.alts[0] if annotation.alts else ""
        consequence = annotation.consequence if annotation.consequence != "." else ""
        condition = _best_condition(annotation.clinvar_conditions)

        if annotation.rsid != "." and condition:
            add_query(f'"{annotation.rsid}" "{condition}"', 120, "variant_condition")
            add_query(f'"{annotation.rsid}" "{condition}" review', 118, "variant_condition_review")
        if annotation.rsid != "." and annotation.gene != ".":
            add_query(f'"{annotation.rsid}" "{annotation.gene}"', 110, "variant_gene")
        if annotation.rsid != ".":
            add_query(f'"{annotation.rsid}" variant', 100, "variant_only")
        if annotation.gene != "." and condition:
            add_query(f'"{annotation.gene}" "{condition}" variant', 90, "gene_condition")
            add_query(f'"{annotation.gene}" "{condition}" review', 92, "gene_condition_review")
            add_query(f'"{annotation.gene}" "{condition}" clinical review', 94, "gene_condition_clinical_review")
        if condition:
            add_query(f'"{condition}" review genetics', 86, "condition_review")
            add_query(f'"{condition}" clinical review variant', 88, "condition_clinical_review")
        if annotation.gene != "." and consequence:
            add_query(f'"{annotation.gene}" "{consequence}" variant', 80, "gene_consequence")
            add_query(f'"{annotation.gene}" "{consequence}" review', 82, "gene_consequence_review")

        # Fall back to a literal genomic description when rsID is missing.
        if annotation.rsid == "." and annotation.gene != "." and alt:
            add_query(
                f'"{annotation.gene}" "{annotation.ref}>{alt}" variant',
                70,
                "gene_literal_variant",
            )

    # File-level support queries stay as fallback.
    add_query('"variant call format" genomics', 20, "format_background")
    add_query('"VCF" interpretation bioinformatics review', 20, "interpretation_background")

    if "symbolic" in facts.variant_types:
        add_query('"symbolic allele" VCF interpretation', 25, "symbolic_background")

    homozygous_alt = facts.genotype_counts.get("1/1", 0)
    heterozygous = facts.genotype_counts.get("0/1", 0) + facts.genotype_counts.get("1/0", 0)
    if facts.file_name.startswith("roh") or homozygous_alt > heterozygous:
        add_query('"runs of homozygosity" variant calling review', 30, "roh_background")
        add_query('"autozygosity" sequencing review', 30, "autozygosity_background")

    return queries


def _search_europe_pmc(query: str, limit: int = 3) -> list[dict[str, object]]:
    encoded = urllib.parse.quote(query)
    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        f"?query={encoded}&format=json&pageSize={limit}&resultType=core"
    )
    ttl_seconds = int(os.getenv("EXTERNAL_HTTP_CACHE_TTL_SECONDS", "86400"))
    cache_key = f"europepmc::{query}::{limit}"
    cached = load_cache("literature_search", cache_key, ttl_seconds=ttl_seconds)
    if cached is not None:
        return cached

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Bioinformatics-VCF-Evidence-MVP/0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=float(os.getenv("LITERATURE_TIMEOUT_SECONDS", "8"))) as response:
        payload = json.loads(response.read().decode("utf-8"))
    results = payload.get("resultList", {}).get("result", [])
    save_cache("literature_search", cache_key, results)
    return results


def _search_pubmed_reviews(term: str, limit: int = 2) -> list[dict[str, object]]:
    email = os.getenv("PUBMED_EMAIL", "")
    tool = "Bioinformatics-VCF-Evidence-MVP"
    ttl_seconds = int(os.getenv("EXTERNAL_HTTP_CACHE_TTL_SECONDS", "86400"))
    cache_key = f"pubmed_review::{term}::{limit}"
    cached = load_cache("literature_search", cache_key, ttl_seconds=ttl_seconds)
    if cached is not None:
        return cached

    encoded_term = urllib.parse.quote(term)
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    esearch_url = (
        f"{base}/esearch.fcgi?db=pubmed&retmode=json&sort=relevance&retmax={limit}"
        f"&term={encoded_term}"
    )
    if email:
        esearch_url += f"&email={urllib.parse.quote(email)}&tool={urllib.parse.quote(tool)}"

    request = urllib.request.Request(esearch_url, headers={"User-Agent": tool})
    with urllib.request.urlopen(request, timeout=float(os.getenv("LITERATURE_TIMEOUT_SECONDS", "8"))) as response:
        search_payload = json.loads(response.read().decode("utf-8"))

    ids = search_payload.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    id_param = ",".join(ids)
    esummary_url = f"{base}/esummary.fcgi?db=pubmed&retmode=json&id={urllib.parse.quote(id_param)}"
    if email:
        esummary_url += f"&email={urllib.parse.quote(email)}&tool={urllib.parse.quote(tool)}"

    request = urllib.request.Request(esummary_url, headers={"User-Agent": tool})
    with urllib.request.urlopen(request, timeout=float(os.getenv("LITERATURE_TIMEOUT_SECONDS", "8"))) as response:
        summary_payload = json.loads(response.read().decode("utf-8"))

    results: list[dict[str, object]] = []
    summary_result = summary_payload.get("result", {})
    for pmid in ids:
        item = summary_result.get(pmid)
        if not isinstance(item, dict):
            continue
        pub_types = item.get("pubtype", [])
        authors = item.get("authors", [])
        author_names = [author.get("name") for author in authors if isinstance(author, dict) and author.get("name")]
        results.append(
            {
                "pmid": pmid,
                "title": item.get("title") or "Untitled article",
                "journalTitle": item.get("fulljournalname") or item.get("source") or "PubMed",
                "pubYear": str(item.get("pubdate") or "")[:4] or "n.d.",
                "pubType": "; ".join(pub_types) if isinstance(pub_types, list) else str(pub_types),
                "authorString": ", ".join(author_names[:3]),
                "sourceSystem": "PubMed",
            }
        )
    save_cache("literature_search", cache_key, results)
    return results


def _rank_result(
    item: dict[str, object],
    query_meta: dict[str, object],
    annotations: list[VariantAnnotation],
) -> int:
    score = int(query_meta["priority"])
    text = " ".join(
        [
            str(item.get("title") or ""),
            str(item.get("abstractText") or ""),
            str(item.get("keywordList") or ""),
        ]
    ).lower()

    exact_variant_match = False
    exact_gene_match = False
    exact_condition_match = False

    for annotation in annotations:
        if annotation.rsid != "." and annotation.rsid.lower() in text:
            score += 50
            exact_variant_match = True
        if annotation.gene != "." and annotation.gene.lower() in text:
            score += 20
            exact_gene_match = True
        condition = _best_condition(annotation.clinvar_conditions).lower()
        if condition and condition in text:
            score += 25
            exact_condition_match = True
        if annotation.consequence != "." and annotation.consequence.lower() in text:
            score += 8

    pub_type = str(item.get("pubType") or "").lower()
    title = str(item.get("title") or "").lower()
    if "review" in pub_type or "review" in title:
        score += 12
    if "human" in text or "clinical" in text or "patient" in text:
        score += 8
    if "mouse" in text or "arabidopsis" in text or "lentil" in text or "rapeseed" in text:
        score -= 30
    if item.get("pmid"):
        score += 5
    if re.search(r"\bcase report\b", text):
        score -= 6

    label = str(query_meta["label"])
    if label in {"variant_condition", "variant_condition_review", "variant_gene", "variant_only"} and not exact_variant_match:
        score -= 80
    if label in {
        "gene_condition",
        "gene_condition_review",
        "gene_condition_clinical_review",
        "gene_consequence",
        "gene_consequence_review",
        "gene_literal_variant",
    } and not exact_gene_match:
        score -= 100
    if label in {"gene_condition", "gene_condition_review", "gene_condition_clinical_review"} and not exact_condition_match:
        score -= 25
    if label in {"condition_review", "condition_clinical_review"} and not exact_condition_match:
        score -= 60
    if label in {"condition_review", "condition_clinical_review"} and "review" not in pub_type and "review" not in title:
        score -= 10
    if label == "pubmed_gene_condition_review":
        if exact_gene_match:
            score += 20
        if exact_condition_match:
            score += 20
        if "review" in pub_type or "review" in title:
            score += 10

    return score


def _to_reference_item(item: dict[str, object], ref_id: str, query_label: str, score: int) -> ReferenceItem:
    pmid = item.get("pmid")
    pmcid = item.get("pmcid")
    doi = item.get("doi")
    title = str(item.get("title") or "Untitled article")
    journal = str(item.get("journalTitle") or "Europe PMC")
    year = str(item.get("pubYear") or "n.d.")
    abstract = str(item.get("abstractText") or "")
    author_string = str(item.get("authorString") or "")
    snippet = " ".join(abstract.split())[:220]
    if snippet:
        note = f"{journal} ({year}). {snippet} [match={query_label}; score={score}]"
    elif author_string:
        note = f"{journal} ({year}). Authors: {author_string}. [match={query_label}; score={score}]"
    else:
        note = f"{journal} ({year}). Retrieved from Europe PMC search. [match={query_label}; score={score}]"

    if pmid:
        article_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        source = "PubMed / Europe PMC"
    elif pmcid:
        article_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
        source = "PMC / Europe PMC"
    elif doi:
        article_url = f"https://doi.org/{doi}"
        source = "DOI / Europe PMC"
    else:
        article_url = str(item.get("uri") or "https://europepmc.org/")
        source = str(item.get("sourceSystem") or "Europe PMC")

    return ReferenceItem(
        id=ref_id,
        title=title,
        source=source,
        url=article_url,
        note=note,
    )


def _live_literature_references(
    facts: AnalysisFacts,
    annotations: list[VariantAnnotation],
    start_index: int,
) -> list[ReferenceItem]:
    max_results = int(os.getenv("LITERATURE_MAX_RESULTS", "4"))
    candidates: list[dict[str, object]] = []
    seen_titles: set[str] = set()
    direct_pubmed_refs: list[ReferenceItem] = []

    for query_meta in _build_search_queries(facts, annotations):
        try:
            hits = _search_europe_pmc(str(query_meta["query"]), limit=3)
        except Exception:
            continue

        for hit in hits:
            title = str(hit.get("title") or "").strip().lower()
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            candidates.append(
                {
                    "score": _rank_result(hit, query_meta, annotations),
                    "query_label": query_meta["label"],
                    "item": hit,
                }
            )

    pubmed_terms: list[tuple[str, str]] = []
    for annotation in annotations:
        condition = _best_condition(annotation.clinvar_conditions)
        if annotation.gene != "." and condition:
            pubmed_terms.append(
                (
                    f'("{annotation.gene}"[Title/Abstract]) AND ("{condition}"[Title/Abstract]) '
                    '(review[Publication Type] OR review[Title])',
                    "pubmed_gene_condition_review",
                )
            )

    for term, label in pubmed_terms[:2]:
        try:
            hits = _search_pubmed_reviews(term, limit=2)
        except Exception:
            continue

        for hit in hits:
            title = str(hit.get("title") or "").strip().lower()
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            score = _rank_result(hit, {"priority": 96, "label": label}, annotations) + 10
            direct_pubmed_refs.append(
                _to_reference_item(
                    hit,
                    ref_id="LIT",
                    query_label=label,
                    score=score,
                )
            )

    refs: list[ReferenceItem] = []
    for ref in direct_pubmed_refs[:2]:
        if len(refs) >= max_results:
            break
        refs.append(ref)

    ranked = sorted(candidates, key=lambda item: int(item["score"]), reverse=True)[:max_results]
    for candidate in ranked:
        if len(refs) >= max_results:
            break
        threshold = 70
        if str(candidate["query_label"]) == "pubmed_gene_condition_review":
            threshold = 60
        if int(candidate["score"]) < threshold:
            continue
        refs.append(
            _to_reference_item(
                candidate["item"],
                ref_id="LIT",
                query_label=str(candidate["query_label"]),
                score=int(candidate["score"]),
            )
        )
    for idx, ref in enumerate(refs, start=start_index):
        ref.id = f"REF{idx}"
    return refs


def build_reference_bundle(facts: AnalysisFacts, annotations: list[VariantAnnotation]) -> list[ReferenceItem]:
    refs = _base_references(facts)
    live_refs = _live_literature_references(facts, annotations, start_index=len(refs) + 1)
    return refs + live_refs
