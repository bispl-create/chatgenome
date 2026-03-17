from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.models import (
    AnalysisFacts,
    AnalysisChatRequest,
    AnalysisChatResponse,
    AnalysisJobResponse,
    AnalysisResponse,
    CountSummaryItem,
    DetailedCountSummaryItem,
    CmplotAssociationRequest,
    FilterRequest,
    FilterResponse,
    FromPathRequest,
    RankedCandidate,
    RohSegment,
    RPlotRequest,
    RPlotResponse,
    SnpEffRequest,
    SnpEffResponse,
    SymbolicAltSummary,
    ToolInfo,
    VariantAnnotation,
    WorkflowAgentResponse,
    WorkflowReplyRequest,
    WorkflowStartRequest,
)
from app.services.annotation import build_draft_answer, build_ui_cards
from app.services.candidate_ranking import build_ranked_candidates
from app.services.chat import answer_analysis_chat
from app.services.filtering import run_filter
from app.services.jobs import create_job, get_job, run_job
from app.services.recommendation import build_recommendations
from app.services.references import build_reference_bundle
from app.services.r_vcf_plots import RPLOT_OUTPUT_DIR, run_cmplot_association, run_r_vcf_plots
from app.services.roh_analysis import run_roh_analysis
from app.services.snpeff import run_snpeff
from app.services.tool_runner import discover_tools, run_tool
from app.services.variant_annotation import annotate_variants
from app.services.vcf_summary import summarize_vcf
from app.services.workflow_agent import interpret_workflow_reply, start_workflow


def _load_local_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_local_env()

app = FastAPI(title="Bioinformatics VCF Evidence MVP", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:3001",
        "http://localhost:3001",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _analyze_vcf(
    path: str,
    annotation_scope: str = "representative",
    annotation_limit: int | None = None,
) -> AnalysisResponse:
    max_examples = int(os.getenv("MAX_EXAMPLE_VARIANTS", "8"))
    used_tools: list[str] = []
    tool_registry = discover_tools()

    try:
        qc_result = run_tool(
            "vcf_qc_tool",
            {
                "vcf_path": path,
                "max_examples": max_examples,
            },
        )
        facts = AnalysisFacts(**qc_result["facts"])
        used_tools.append("vcf_qc_tool")
    except Exception:
        facts = summarize_vcf(path, max_examples=max_examples)

    try:
        annotation_result = run_tool(
            "annotation_tool",
            {
                "vcf_path": path,
                "facts": facts.model_dump(),
                "scope": annotation_scope,
                "limit": annotation_limit,
            },
        )
        annotations = [VariantAnnotation(**item) for item in annotation_result["annotations"]]
        used_tools.append("annotation_tool")
    except Exception:
        annotations = annotate_variants(
            path,
            facts,
            scope=annotation_scope,
            limit=annotation_limit,
        )
    try:
        roh_result = run_tool("roh_analysis_tool", {"vcf_path": path})
        roh_segments = [RohSegment(**item) for item in roh_result["roh_segments"]]
        used_tools.append("roh_analysis_tool")
    except Exception:
        roh_segments = run_roh_analysis(path)
    try:
        candidate_result = run_tool(
            "candidate_ranking_tool",
            {
                "annotations": [item.model_dump() for item in annotations],
                "roh_segments": [item.model_dump() for item in roh_segments],
                "limit": 8,
            },
        )
        candidate_variants = [RankedCandidate(**item) for item in candidate_result["candidate_variants"]]
        used_tools.append("candidate_ranking_tool")
    except Exception:
        candidate_variants = build_ranked_candidates(annotations, roh_segments, limit=8)
    try:
        clinvar_result = run_tool(
            "clinvar_review_tool",
            {"annotations": [item.model_dump() for item in annotations]},
        )
        clinvar_summary = [CountSummaryItem(**item) for item in clinvar_result["clinvar_summary"]]
        used_tools.append("clinvar_review_tool")
    except Exception:
        counts: dict[str, int] = {}
        for item in annotations:
            key = item.clinical_significance.strip() if item.clinical_significance and item.clinical_significance != "." else "Unreviewed"
            counts[key] = counts.get(key, 0) + 1
        clinvar_summary = [CountSummaryItem(label=label, count=count) for label, count in sorted(counts.items(), key=lambda part: part[1], reverse=True)]
    try:
        consequence_result = run_tool(
            "vep_consequence_tool",
            {
                "annotations": [item.model_dump() for item in annotations],
                "limit": 10,
            },
        )
        consequence_summary = [CountSummaryItem(**item) for item in consequence_result["consequence_summary"]]
        used_tools.append("vep_consequence_tool")
    except Exception:
        counts = {}
        for item in annotations:
            key = item.consequence.strip() if item.consequence and item.consequence != "." else "Unclassified"
            counts[key] = counts.get(key, 0) + 1
        consequence_summary = [
            CountSummaryItem(label=label, count=count)
            for label, count in sorted(counts.items(), key=lambda part: part[1], reverse=True)[:10]
        ]
    try:
        coverage_result = run_tool(
            "clinical_coverage_tool",
            {"annotations": [item.model_dump() for item in annotations]},
        )
        clinical_coverage_summary = [
            DetailedCountSummaryItem(**item) for item in coverage_result["clinical_coverage_summary"]
        ]
        used_tools.append("clinical_coverage_tool")
    except Exception:
        total = len(annotations)

        def detail(label: str, count: int) -> DetailedCountSummaryItem:
            percent = round((count / total) * 100) if total else 0
            return DetailedCountSummaryItem(label=label, count=count, detail=f"{count}/{total} annotated ({percent}%)")

        clinical_coverage_summary = [
            detail("ClinVar coverage", sum(1 for item in annotations if (item.clinical_significance and item.clinical_significance != ".") or (item.clinvar_conditions and item.clinvar_conditions != "."))),
            detail("gnomAD coverage", sum(1 for item in annotations if item.gnomad_af and item.gnomad_af != ".")),
            detail("Gene mapping", sum(1 for item in annotations if item.gene and item.gene != ".")),
            detail("HGVS coverage", sum(1 for item in annotations if (item.hgvsc and item.hgvsc != ".") or (item.hgvsp and item.hgvsp != "."))),
            detail("Protein change", sum(1 for item in annotations if item.hgvsp and item.hgvsp != ".")),
        ]
    try:
        filtering_result = run_tool(
            "filtering_view_tool",
            {"annotations": [item.model_dump() for item in annotations]},
        )
        filtering_summary = [DetailedCountSummaryItem(**item) for item in filtering_result["filtering_summary"]]
        used_tools.append("filtering_view_tool")
    except Exception:
        unique_genes = {item.gene.strip() for item in annotations if item.gene and item.gene.strip() not in {"", "."}}
        clinvar_labeled = sum(1 for item in annotations if item.clinical_significance and item.clinical_significance != ".")
        symbolic = sum(1 for item in annotations if any(alt.startswith("<") and alt.endswith(">") for alt in item.alts))
        filtering_summary = [
            DetailedCountSummaryItem(label="Annotated rows", count=len(annotations), detail=f"{len(annotations)} rows currently available in the triage table"),
            DetailedCountSummaryItem(label="Distinct genes", count=len(unique_genes), detail=f"{len(unique_genes)} genes represented in the annotated subset"),
            DetailedCountSummaryItem(label="ClinVar-labeled rows", count=clinvar_labeled, detail=f"{clinvar_labeled} rows contain a ClinVar-style significance label"),
            DetailedCountSummaryItem(label="Symbolic ALT rows", count=symbolic, detail=f"{symbolic} rows are symbolic ALT records that may need separate handling"),
        ]
    try:
        symbolic_result = run_tool(
            "symbolic_alt_tool",
            {"annotations": [item.model_dump() for item in annotations]},
        )
        symbolic_alt_summary = SymbolicAltSummary(**symbolic_result["symbolic_alt_summary"])
        used_tools.append("symbolic_alt_tool")
    except Exception:
        symbolic_items = [item for item in annotations if any(alt.startswith("<") and alt.endswith(">") for alt in item.alts)]
        symbolic_alt_summary = SymbolicAltSummary(
            count=len(symbolic_items),
            examples=[
                {
                    "locus": f"{item.contig}:{item.pos_1based}",
                    "gene": item.gene or "",
                    "alts": item.alts,
                    "consequence": item.consequence or "",
                    "genotype": item.genotype or "",
                }
                for item in symbolic_items[:5]
            ],
        )
    reference_annotations = annotations[: min(len(annotations), 20)]
    references = build_reference_bundle(facts, reference_annotations)
    recommendations = build_recommendations(facts)
    ui_cards = build_ui_cards(facts, annotations)
    try:
        summary_result = run_tool(
            "grounded_summary_tool",
            {
                "facts": facts.model_dump(),
                "annotations": [item.model_dump() for item in annotations],
                "references": [item.model_dump() for item in references],
                "recommendations": [item.model_dump() for item in recommendations],
            },
        )
        draft_answer = str(summary_result["draft_answer"])
        used_tools.append("grounded_summary_tool")
    except Exception:
        draft_answer = build_draft_answer(
            facts,
            annotations,
            [item.id for item in references],
            [item.id for item in recommendations],
        )
    return AnalysisResponse(
        analysis_id=str(uuid.uuid4()),
        facts=facts,
        annotations=annotations,
        roh_segments=roh_segments,
        candidate_variants=candidate_variants,
        clinvar_summary=clinvar_summary,
        consequence_summary=consequence_summary,
        clinical_coverage_summary=clinical_coverage_summary,
        filtering_summary=filtering_summary,
        symbolic_alt_summary=symbolic_alt_summary,
        references=references,
        recommendations=recommendations,
        ui_cards=ui_cards,
        draft_answer=draft_answer,
        used_tools=used_tools,
        tool_registry=tool_registry,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/tools", response_model=list[ToolInfo])
def list_registry_tools() -> list[ToolInfo]:
    return discover_tools()


@app.get("/api/v1/files")
def get_output_file(path: str = Query(..., description="Absolute path to a generated output file")) -> FileResponse:
    file_path = Path(path).resolve()
    allowed_roots = [RPLOT_OUTPUT_DIR.resolve()]
    if not any(root == file_path or root in file_path.parents for root in allowed_roots):
        raise HTTPException(status_code=403, detail="Access to the requested file is not allowed.")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Output file not found: {file_path}")
    return FileResponse(file_path)


@app.post("/api/v1/analysis/from-path", response_model=AnalysisResponse)
def analyze_from_path(request: FromPathRequest) -> AnalysisResponse:
    try:
        return _analyze_vcf(
            request.vcf_path,
            annotation_scope=request.annotation_scope,
            annotation_limit=request.annotation_limit,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Analysis failed: {exc}") from exc


@app.post("/api/v1/analysis/from-path/async", response_model=AnalysisJobResponse)
def analyze_from_path_async(request: FromPathRequest) -> AnalysisJobResponse:
    job_id = create_job()
    run_job(
        job_id,
        lambda: _analyze_vcf(
            request.vcf_path,
            annotation_scope=request.annotation_scope,
            annotation_limit=request.annotation_limit,
        ).model_dump(),
    )
    job = get_job(job_id)
    return AnalysisJobResponse(job_id=job_id, status=job["status"])


@app.get("/api/v1/analysis/jobs/{job_id}", response_model=AnalysisJobResponse)
def get_analysis_job(job_id: str) -> AnalysisJobResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    result = job["result"]
    parsed_result = AnalysisResponse(**result) if isinstance(result, dict) else None
    return AnalysisJobResponse(
        job_id=job_id,
        status=job["status"],
        result=parsed_result,
        error=job["error"],
    )


@app.post("/api/v1/chat/analysis", response_model=AnalysisChatResponse)
def chat_about_analysis(request: AnalysisChatRequest) -> AnalysisChatResponse:
    return answer_analysis_chat(request)


@app.post("/api/v1/workflow/start", response_model=WorkflowAgentResponse)
def begin_workflow(request: WorkflowStartRequest) -> WorkflowAgentResponse:
    return start_workflow(request)


@app.post("/api/v1/workflow/reply", response_model=WorkflowAgentResponse)
def continue_workflow(request: WorkflowReplyRequest) -> WorkflowAgentResponse:
    return interpret_workflow_reply(request)


@app.post("/api/v1/filter/run", response_model=FilterResponse)
def run_filtering(request: FilterRequest) -> FilterResponse:
    try:
        return run_filter(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Filtering failed: {exc}") from exc


@app.post("/api/v1/snpeff/run", response_model=SnpEffResponse)
def run_snpeff_annotation(request: SnpEffRequest) -> SnpEffResponse:
    try:
        return run_snpeff(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"SnpEff failed: {exc}") from exc


@app.post("/api/v1/r/plots", response_model=RPlotResponse)
def run_r_plots(request: RPlotRequest) -> RPlotResponse:
    try:
        return run_r_vcf_plots(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"R plotting failed: {exc}") from exc


@app.post("/api/v1/r/cmplot", response_model=RPlotResponse)
def run_cmplot(request: CmplotAssociationRequest) -> RPlotResponse:
    try:
        return run_cmplot_association(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CMplot association rendering failed: {exc}") from exc


@app.post("/api/v1/analysis/upload", response_model=AnalysisResponse)
async def analyze_upload(
    file: UploadFile = File(...),
    annotation_scope: str = Form("representative"),
    annotation_limit: Optional[int] = Form(None),
) -> AnalysisResponse:
    suffix = Path(file.filename or "upload.vcf").suffix
    if suffix not in {".vcf", ".gz"}:
        raise HTTPException(status_code=400, detail="Only .vcf and .vcf.gz uploads are supported.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        return _analyze_vcf(
            tmp_path,
            annotation_scope=annotation_scope,
            annotation_limit=annotation_limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Analysis failed: {exc}") from exc
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
