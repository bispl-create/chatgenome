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
    AnalysisChatRequest,
    AnalysisChatResponse,
    AnalysisJobResponse,
    AnalysisResponse,
    CmplotAssociationRequest,
    FilterRequest,
    FilterResponse,
    FromPathRequest,
    RPlotRequest,
    RPlotResponse,
    SnpEffRequest,
    SnpEffResponse,
    WorkflowAgentResponse,
    WorkflowReplyRequest,
    WorkflowStartRequest,
)
from app.services.annotation import build_draft_answer, build_ui_cards
from app.services.chat import answer_analysis_chat
from app.services.filtering import run_filter
from app.services.jobs import create_job, get_job, run_job
from app.services.recommendation import build_recommendations
from app.services.references import build_reference_bundle
from app.services.r_vcf_plots import RPLOT_OUTPUT_DIR, run_cmplot_association, run_r_vcf_plots
from app.services.roh_analysis import run_roh_analysis
from app.services.snpeff import run_snpeff
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
    facts = summarize_vcf(path, max_examples=max_examples)
    annotations = annotate_variants(
        path,
        facts,
        scope=annotation_scope,
        limit=annotation_limit,
    )
    roh_segments = run_roh_analysis(path)
    reference_annotations = annotations[: min(len(annotations), 20)]
    references = build_reference_bundle(facts, reference_annotations)
    recommendations = build_recommendations(facts)
    ui_cards = build_ui_cards(facts, annotations)
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
        references=references,
        recommendations=recommendations,
        ui_cards=ui_cards,
        draft_answer=draft_answer,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
