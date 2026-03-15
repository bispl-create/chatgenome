from __future__ import annotations

import json
import os
import re
import urllib.request

from app.models import AnalysisChatRequest, AnalysisChatResponse


def _is_korean(text: str) -> bool:
    return bool(re.search(r"[\uac00-\ud7a3]", text))


def _flatten_studio_context(studio_context: dict) -> dict[str, object]:
    return {
        "active_view": studio_context.get("active_view"),
        "qc_summary": studio_context.get("qc_summary"),
        "clinical_coverage": studio_context.get("clinical_coverage"),
        "symbolic_alt_review": studio_context.get("symbolic_alt_review"),
        "roh_review": studio_context.get("roh_review"),
        "candidate_variants": studio_context.get("candidate_variants"),
        "clinvar_review": studio_context.get("clinvar_review"),
        "vep_consequence": studio_context.get("vep_consequence"),
        "selected_annotation": studio_context.get("selected_annotation"),
    }


def _compact_analysis_context(payload: AnalysisChatRequest) -> dict[str, object]:
    analysis = payload.analysis
    context = {
        "analysis_id": analysis.analysis_id,
        "draft_answer": analysis.draft_answer,
        "facts": {
            "file_name": analysis.facts.file_name,
            "genome_build_guess": analysis.facts.genome_build_guess,
            "record_count": analysis.facts.record_count,
            "samples": analysis.facts.samples,
            "variant_types": analysis.facts.variant_types,
            "warnings": analysis.facts.warnings,
        },
        "annotations": [
            {
                "pos": item.pos_1based,
                "gene": item.gene,
                "consequence": item.consequence,
                "rsid": item.rsid,
                "clinical_significance": item.clinical_significance,
                "condition": item.clinvar_conditions,
                "gnomad_af": item.gnomad_af,
            }
            for item in payload.analysis.annotations[:6]
        ],
        "roh_segments": [
            {
                "sample": item.sample,
                "contig": item.contig,
                "start_1based": item.start_1based,
                "end_1based": item.end_1based,
                "length_bp": item.length_bp,
                "marker_count": item.marker_count,
                "quality": item.quality,
            }
            for item in payload.analysis.roh_segments[:6]
        ],
        "references": [
            {"id": item.id, "title": item.title, "url": item.url}
            for item in payload.analysis.references[:8]
        ],
        "recommendations": [
            {"id": item.id, "title": item.title, "action": item.action}
            for item in payload.analysis.recommendations[:6]
        ],
    }
    if payload.studio_context:
        context["studio_context"] = _flatten_studio_context(payload.studio_context)
    return context


def _studio_guided_answer(payload: AnalysisChatRequest) -> AnalysisChatResponse | None:
    studio = payload.studio_context or {}
    if not studio:
        return None

    question = payload.question.lower()
    citations = [item.id for item in payload.analysis.references[:3]]

    if "initial grounded summary" in question or "studio-grounded summary" in question:
        backend_summary = (payload.analysis.draft_answer or "").strip()
        qc = studio.get("qc_summary") or {}
        coverage = studio.get("clinical_coverage") or []
        symbolic = studio.get("symbolic_alt_review") or {}
        roh = studio.get("roh_review") or {}
        candidates = studio.get("candidate_variants") or []
        clinvar = studio.get("clinvar_review") or []
        consequence = studio.get("vep_consequence") or []

        coverage_lines = [f"- {item.get('label')}: {item.get('detail')}" for item in coverage[:4]]
        candidate_lines = [
            f"- {item.get('gene') or 'Unknown'} {item.get('locus')} | score {item.get('score')} | consequence={item.get('consequence')} | ClinVar={item.get('clinical_significance')} | in ROH={item.get('in_roh')}"
            for item in candidates[:3]
        ]
        roh_lines = [
            f"- {item.get('contig')}:{item.get('start_1based')}-{item.get('end_1based')} | {(item.get('length_bp') or 0) / 1_000_000:.2f} Mb | markers {item.get('marker_count')} | quality {item.get('quality')}"
            for item in (roh.get("segments") or [])[:3]
        ]
        clinvar_lines = [f"- {item.get('label')}: {item.get('count')}" for item in clinvar[:4]]
        consequence_lines = [f"- {item.get('label')}: {item.get('count')}" for item in consequence[:4]]
        answer = (
            f"This VCF contains {payload.analysis.facts.record_count} records across {len(payload.analysis.facts.contigs)} contig(s) "
            f"and appears to align to {payload.analysis.facts.genome_build_guess or 'an unknown genome build'}. "
            "The summary below reflects both the backend draft summary and the current Studio-derived review state.\n\n"
            "## Backend grounded summary\n"
            f"{backend_summary if backend_summary else '- No backend draft summary is available.'}\n\n"
            "## QC and file status\n"
            f"- PASS rate: {((qc.get('pass_rate') or 0) * 100):.1f}%\n"
            f"- Ti/Tv ratio: {qc.get('ti_tv') if qc.get('ti_tv') is not None else 'n/a'}\n"
            f"- Missing genotype rate: {((qc.get('missing_gt_rate') or 0) * 100):.1f}%\n"
            f"- Het/HomAlt ratio: {qc.get('het_hom_alt_ratio') if qc.get('het_hom_alt_ratio') is not None else 'n/a'}\n\n"
            "## Annotation coverage\n"
            f"{chr(10).join(coverage_lines) if coverage_lines else '- Coverage detail is not available.'}\n\n"
            "## Functional and clinical review\n"
            f"{chr(10).join(consequence_lines) if consequence_lines else '- Consequence summary is not available.'}\n"
            f"{chr(10).join(clinvar_lines) if clinvar_lines else '- ClinVar distribution is not available.'}\n\n"
            "## Candidate and recessive signals\n"
            f"{chr(10).join(candidate_lines) if candidate_lines else '- No ranked candidate variants are available yet.'}\n"
            f"{chr(10).join(roh_lines) if roh_lines else '- No ROH segments are currently available.'}\n\n"
            "## Special record handling\n"
            f"- Symbolic ALT records separated for review: {symbolic.get('count', 0)}\n\n"
            f"Grounding references: {', '.join(citations) if citations else 'foundational references'}."
        )
        return AnalysisChatResponse(answer=answer, citations=citations, used_fallback=False)

    if "roh" in question or "recessive" in question or "열성" in payload.question or "동형접합" in payload.question:
        roh = studio.get("roh_review") or {}
        segments = roh.get("segments") or []
        shortlist = roh.get("recessive_shortlist") or []
        if _is_korean(payload.question):
            segment_lines = [
                f"- {item.get('contig')}:{item.get('start_1based')}-{item.get('end_1based')} | {item.get('length_bp')} bp | markers {item.get('marker_count')} | quality {item.get('quality')}"
                for item in segments[:5]
            ]
            shortlist_lines = [
                f"- {item.get('gene') or 'Unknown'} {item.get('locus')} | score {item.get('score')} | genotype {item.get('genotype')} | in ROH={item.get('in_roh')} | consequence={item.get('consequence')} | gnomAD={item.get('gnomad_af')}"
                for item in shortlist[:5]
            ]
            answer = (
                "ROH / Recessive Review 결과는 현재 Studio 계산값 기준으로 보면 다음과 같습니다.\n\n"
                "1. ROH 구간\n"
                f"{chr(10).join(segment_lines) if segment_lines else '- 검출된 ROH 구간이 없습니다.'}\n\n"
                "2. 열성 후보 shortlist\n"
                f"{chr(10).join(shortlist_lines) if shortlist_lines else '- 현재 shortlist 후보가 없습니다.'}\n\n"
                "3. 해석\n"
                "- 이 화면의 열성 후보 점수는 `1/1`, ROH overlap, consequence, gnomAD, ClinVar를 함께 반영한 triage 점수입니다.\n"
                "- 최종 임상 판단은 아니며, segregation, phenotype, 전체 VCF 범위의 annotation을 추가로 봐야 합니다."
            )
        else:
            answer = "ROH / recessive review is available in the Studio context, but the current UI is configured primarily for Korean responses."
        return AnalysisChatResponse(answer=answer, citations=citations, used_fallback=False)

    if "clinvar" in question:
        review = studio.get("clinvar_review") or []
        lines = [f"- {item.get('label')}: {item.get('count')}" for item in review[:8]]
        answer = (
            "ClinVar Review 카드 설명입니다.\n\n"
            "1. 분포\n"
            f"{chr(10).join(lines) if lines else '- ClinVar 분포 데이터가 없습니다.'}\n\n"
            "2. 의미\n"
            "- 이 카드는 현재 annotation subset에서 clinical significance가 어떻게 분포하는지 보여줍니다.\n"
            "- `benign`, `pathogenic`, `VUS`, `unreviewed` 같은 값은 ClinVar 또는 관련 임상 주석 필드에서 온 것입니다."
        )
        return AnalysisChatResponse(answer=answer, citations=citations, used_fallback=False)

    if "coverage" in question or "coverage" in str(studio.get("active_view", "")).lower() or "coverage" in payload.question.lower() or "주석" in payload.question and "coverage" in question:
        coverage = studio.get("clinical_coverage") or []
        lines = [f"- {item.get('label')}: {item.get('detail')}" for item in coverage[:6]]
        answer = (
            "Clinical Coverage 카드 설명입니다.\n\n"
            "1. 현재 coverage\n"
            f"{chr(10).join(lines) if lines else '- Coverage 요약이 없습니다.'}\n\n"
            "2. 의미\n"
            "- 이 카드는 현재 annotation 결과가 ClinVar, gnomAD, gene mapping, HGVS, protein change 기준으로 얼마나 채워졌는지 보여줍니다.\n"
            "- 값이 낮을수록 추가 annotation이 더 필요합니다."
        )
        return AnalysisChatResponse(answer=answer, citations=citations, used_fallback=False)

    if "candidate" in question or "후보" in payload.question:
        candidates = studio.get("candidate_variants") or []
        lines = [
            f"- {item.get('gene') or 'Unknown'} {item.get('locus')} | score {item.get('score')} | {item.get('consequence')} | ClinVar={item.get('clinical_significance')} | in ROH={item.get('in_roh')}"
            for item in candidates[:6]
        ]
        answer = (
            "Candidate Variants 카드 설명입니다.\n\n"
            "1. 상위 후보\n"
            f"{chr(10).join(lines) if lines else '- 현재 후보 리스트가 없습니다.'}\n\n"
            "2. 의미\n"
            "- 점수는 consequence, ClinVar, gnomAD, genotype, 그리고 ROH overlap 신호를 함께 반영한 triage용 점수입니다.\n"
            "- 높은 점수일수록 먼저 검토할 가치가 크지만, 임상 확정 점수는 아닙니다."
        )
        return AnalysisChatResponse(answer=answer, citations=citations, used_fallback=False)

    if "vep" in question or "consequence" in question or "효과" in payload.question:
        consequence = studio.get("vep_consequence") or []
        lines = [f"- {item.get('label')}: {item.get('count')}" for item in consequence[:8]]
        answer = (
            "VEP Consequence 카드 설명입니다.\n\n"
            "1. consequence 분포\n"
            f"{chr(10).join(lines) if lines else '- consequence 요약이 없습니다.'}\n\n"
            "2. 의미\n"
            "- 이 카드는 VEP 기반 consequence가 어떤 유형으로 많이 분포하는지 보여줍니다.\n"
            "- 예를 들어 missense, splice, synonymous 비율을 보고 어떤 변이를 우선 볼지 정할 수 있습니다."
        )
        return AnalysisChatResponse(answer=answer, citations=citations, used_fallback=False)

    return None


def _fallback_answer(payload: AnalysisChatRequest) -> AnalysisChatResponse:
    studio_answer = _studio_guided_answer(payload)
    if studio_answer is not None:
        return studio_answer
    analysis = payload.analysis
    top_annotations = analysis.annotations[:3]
    citations = [item.id for item in analysis.references[:3]]
    if _is_korean(payload.question):
        annotation_lines = []
        for item in top_annotations:
            annotation_lines.append(
                f"- {item.gene} {item.consequence} ({item.rsid}, ClinVar={item.clinical_significance}, condition={item.clinvar_conditions})"
            )
        answer = (
            f"현재 분석 파일은 {analysis.facts.file_name}이고, 총 {analysis.facts.record_count}개 변이가 있습니다. "
            f"유전체 빌드는 {analysis.facts.genome_build_guess or '미상'}로 추정됩니다. "
            f"대표 annotation은 다음과 같습니다.\n"
            f"{chr(10).join(annotation_lines) if annotation_lines else '- 대표 annotation이 아직 없습니다.'}\n"
            f"추천 다음 단계는 {', '.join(item.title for item in analysis.recommendations[:3]) or '추가 annotation 확인'} 입니다. "
            f"근거 문헌은 {', '.join(citations) if citations else '기본 reference'}를 참고하세요."
        )
    else:
        annotation_lines = []
        for item in top_annotations:
            annotation_lines.append(
                f"- {item.gene} {item.consequence} ({item.rsid}, ClinVar={item.clinical_significance}, condition={item.clinvar_conditions})"
            )
        answer = (
            f"This analysis contains {analysis.facts.record_count} variants from {analysis.facts.file_name} "
            f"and appears to use {analysis.facts.genome_build_guess or 'an unknown genome build'}. "
            f"Representative annotations include:\n"
            f"{chr(10).join(annotation_lines) if annotation_lines else '- No representative annotations are available yet.'}\n"
            f"Recommended next steps include {', '.join(item.title for item in analysis.recommendations[:3]) or 'additional annotation review'}. "
            f"See {', '.join(citations) if citations else 'the foundational references'} for grounding."
        )
    return AnalysisChatResponse(answer=answer, citations=citations, used_fallback=True)


def _call_openai(payload: AnalysisChatRequest) -> AnalysisChatResponse:
    studio_answer = _studio_guided_answer(payload)
    if studio_answer is not None:
        return studio_answer
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    if not api_key:
        return _fallback_answer(payload)

    compact_context = _compact_analysis_context(payload)
    system_prompt = (
        "You are a genomics analysis copilot. Answer only from the provided VCF analysis context. "
        "Do not invent variant facts. Be concise, grounded, and mention uncertainty. "
        "Treat studio_context as part of the trusted analysis state, including ROH, coverage, candidate, ClinVar, and consequence summaries when present. "
        "When possible, cite reference ids like REF1 or REF4 inline. "
        "Format the answer in clean Markdown with short sections or bullet points when helpful. "
        "If the user asks for explanation, prefer structured bullets over dense prose."
    )
    history_lines = [{"role": turn.role, "content": turn.content} for turn in payload.history[-6:]]
    user_content = (
        "Question:\n"
        f"{payload.question}\n\n"
        "Analysis context JSON:\n"
        f"{json.dumps(compact_context, ensure_ascii=False)}"
    )
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt},
            *history_lines,
            {"role": "user", "content": user_content},
        ],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(body).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))) as response:
        result = json.loads(response.read().decode("utf-8"))

    output_text = result.get("output_text")
    if not output_text:
        output = result.get("output", [])
        texts: list[str] = []
        for item in output:
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    texts.append(content.get("text", ""))
        output_text = "\n".join(texts).strip()

    citations = sorted(set(re.findall(r"\bREF\d+\b", output_text or "")))
    return AnalysisChatResponse(
        answer=output_text or _fallback_answer(payload).answer,
        citations=citations,
        used_fallback=False,
    )


def answer_analysis_chat(payload: AnalysisChatRequest) -> AnalysisChatResponse:
    try:
        return _call_openai(payload)
    except Exception:
        return _fallback_answer(payload)
