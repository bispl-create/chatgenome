from __future__ import annotations

import json
import os
import re
import urllib.request

from app.models import WorkflowAgentResponse, WorkflowReplyRequest, WorkflowStartRequest


def _model_name() -> str:
    return os.getenv("OPENAI_WORKFLOW_MODEL", "gpt-5-nano")


def _fallback_parse(message: str) -> tuple[str, int | None]:
    text = message.strip().lower()
    scope = "all" if any(token in text for token in ["all", "전체", "모두", "전부"]) else "representative"
    if any(token in text for token in ["representative", "대표", "sample", "few"]):
        scope = "representative"
    match = re.search(r"(\d{1,6})", text)
    limit = int(match.group(1)) if match else (200 if scope == "all" else None)
    return scope, limit


def start_workflow(payload: WorkflowStartRequest) -> WorkflowAgentResponse:
    return WorkflowAgentResponse(
        assistant_message=(
            f"`{payload.file_name}` 파일을 받았습니다. annotation scope와 range(limit)를 알려주세요. "
            "별도 지시가 없으면 representative로 시작합니다. 예: `all로 200개`, `representative로 진행`."
        ),
        should_start_analysis=False,
        parsed_scope="representative",
        parsed_limit=None,
        used_fallback=True,
        model=_model_name(),
    )


def _call_openai_for_options(payload: WorkflowReplyRequest) -> WorkflowAgentResponse:
    api_key = os.getenv("OPENAI_API_KEY")
    model = _model_name()
    if not api_key:
        scope, limit = _fallback_parse(payload.message)
        return WorkflowAgentResponse(
            assistant_message=(
                f"알겠습니다. `{payload.file_name}` 파일을 scope={scope}, "
                f"range(limit)={limit if limit is not None else 'default'} 기준으로 분석하겠습니다."
            ),
            should_start_analysis=True,
            parsed_scope=scope,  # type: ignore[arg-type]
            parsed_limit=limit,
            used_fallback=True,
            model=model,
        )

    system_prompt = (
        "You are a genomics workflow intake assistant. "
        "Interpret the user's option reply for a VCF analysis workflow. "
        "Return only JSON with keys: assistant_message, should_start_analysis, parsed_scope, parsed_limit. "
        "parsed_scope must be 'representative' or 'all'. "
        "parsed_limit should be an integer or null. "
        "If the user does not clearly ask for all/full coverage, default to representative. "
        "The assistant_message should briefly confirm the interpreted options in Korean."
    )
    user_prompt = (
        f"VCF file name: {payload.file_name}\n"
        f"User option reply: {payload.message}\n"
        "Examples:\n"
        "- 'all로 200개' => parsed_scope='all', parsed_limit=200\n"
        "- 'representative로 진행' => parsed_scope='representative', parsed_limit=null\n"
        "- '전체 annotation 500개' => parsed_scope='all', parsed_limit=500\n"
    )
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
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

    output_text = result.get("output_text", "").strip()
    if not output_text:
        output = result.get("output", [])
        texts: list[str] = []
        for item in output:
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    texts.append(content.get("text", ""))
        output_text = "\n".join(texts).strip()

    cleaned = output_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    parsed = json.loads(cleaned)
    scope = parsed.get("parsed_scope", "representative")
    limit = parsed.get("parsed_limit")
    if scope not in {"representative", "all"}:
        scope = "representative"
    if limit is not None:
        try:
            limit = int(limit)
        except Exception:
            limit = None
    return WorkflowAgentResponse(
        assistant_message=parsed.get(
            "assistant_message",
            f"알겠습니다. `{payload.file_name}` 파일 분석을 시작하겠습니다.",
        ),
        should_start_analysis=bool(parsed.get("should_start_analysis", True)),
        parsed_scope=scope,  # type: ignore[arg-type]
        parsed_limit=limit,
        used_fallback=False,
        model=model,
    )


def interpret_workflow_reply(payload: WorkflowReplyRequest) -> WorkflowAgentResponse:
    try:
        return _call_openai_for_options(payload)
    except Exception:
        scope, limit = _fallback_parse(payload.message)
        return WorkflowAgentResponse(
            assistant_message=(
                f"알겠습니다. `{payload.file_name}` 파일을 scope={scope}, "
                f"range(limit)={limit if limit is not None else 'default'} 기준으로 분석하겠습니다."
            ),
            should_start_analysis=True,
            parsed_scope=scope,  # type: ignore[arg-type]
            parsed_limit=limit,
            used_fallback=True,
            model=_model_name(),
        )
