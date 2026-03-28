from __future__ import annotations

import base64
import io
from pathlib import Path
import sys
from typing import Any

from app.models import DicomSourceResponse
from app.services.tool_runner import discover_tools


WINDOW_PRESETS = [
    {"id": "default", "label": "default", "width": None, "center": None},
    {"id": "soft", "label": "soft", "width": 400.0, "center": 40.0},
    {"id": "lung", "label": "lung", "width": 1500.0, "center": -600.0},
    {"id": "bone", "label": "bone", "width": 1800.0, "center": 400.0},
    {"id": "brain", "label": "brain", "width": 80.0, "center": 40.0},
]


def _ensure_imaging_dependencies() -> None:
    candidates = [
        Path(__file__).resolve().parents[3] / "clinical_multimodal_workspace/.venv/lib/python3.9/site-packages",
        Path(__file__).resolve().parents[3] / "dicom_tools/.venv/lib/python3.9/site-packages",
    ]
    for candidate in candidates:
        candidate_str = str(candidate)
        if candidate.exists() and candidate_str not in sys.path:
            sys.path.append(candidate_str)


def _load_imaging_modules() -> tuple[Any | None, Any | None, Any | None]:
    _ensure_imaging_dependencies()
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None
    try:
        import pydicom  # type: ignore
    except Exception:
        pydicom = None
    try:
        from PIL import Image  # type: ignore
    except Exception:
        Image = None
    return np, pydicom, Image


def _read_dicom_metadata(raw: bytes) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "patient_id": "not available",
        "study_instance_uid": "not available",
        "series_instance_uid": "not available",
        "study_description": "not available",
        "series_description": "not available",
        "modality": "not available",
        "rows": "not available",
        "columns": "not available",
        "instance_number": "not available",
        "preview": {"available": False, "image_data_url": None, "message": "Preview not available"},
        "preview_presets": {},
    }
    _, pydicom, _ = _load_imaging_modules()
    if pydicom is None:
        return meta

    try:
        dataset = pydicom.dcmread(io.BytesIO(raw), stop_before_pixels=True, force=True)
        meta.update(
            {
                "patient_id": str(getattr(dataset, "PatientID", "not available")),
                "study_instance_uid": str(getattr(dataset, "StudyInstanceUID", "not available")),
                "series_instance_uid": str(getattr(dataset, "SeriesInstanceUID", "not available")),
                "study_description": str(getattr(dataset, "StudyDescription", "not available")),
                "series_description": str(getattr(dataset, "SeriesDescription", "not available")),
                "modality": str(getattr(dataset, "Modality", "not available")),
                "rows": str(getattr(dataset, "Rows", "not available")),
                "columns": str(getattr(dataset, "Columns", "not available")),
                "instance_number": str(getattr(dataset, "InstanceNumber", "not available")),
            }
        )
        meta["preview"] = _build_dicom_preview(raw)
        meta["preview_presets"] = _build_dicom_preview_presets(raw)
    except Exception:
        pass
    return meta


def _normalize_dicom_array(raw: bytes, window_width: float | None = None, window_center: float | None = None) -> tuple[Any | None, str]:
    np, pydicom, _ = _load_imaging_modules()
    if pydicom is None or np is None:
        return None, "Preview dependencies are not installed."

    try:
        dataset = pydicom.dcmread(io.BytesIO(raw), force=True)
        pixel_array = dataset.pixel_array
        array = np.asarray(pixel_array)
        if array.ndim == 4:
            array = array[0, 0]
        elif array.ndim == 3:
            if array.shape[-1] not in (3, 4):
                array = array[0]

        if array.ndim == 2:
            array = array.astype(np.float32)
            slope = float(getattr(dataset, "RescaleSlope", 1) or 1)
            intercept = float(getattr(dataset, "RescaleIntercept", 0) or 0)
            array = array * slope + intercept

            ww = window_width
            wc = window_center
            if ww is None or wc is None:
                ww = getattr(dataset, "WindowWidth", None)
                wc = getattr(dataset, "WindowCenter", None)
                if isinstance(ww, (list, tuple)):
                    ww = ww[0]
                if isinstance(wc, (list, tuple)):
                    wc = wc[0]

            if ww is not None and wc is not None:
                ww = float(ww)
                wc = float(wc)
                lower = wc - ww / 2.0
                upper = wc + ww / 2.0
                normalized = ((array - lower) / max(upper - lower, 1e-6) * 255.0).clip(0, 255).astype(np.uint8)
            else:
                min_value = float(array.min())
                max_value = float(array.max())
                if max_value == min_value:
                    normalized = np.zeros_like(array, dtype=np.uint8)
                else:
                    normalized = ((array - min_value) / (max_value - min_value) * 255.0).clip(0, 255).astype(np.uint8)

            if str(getattr(dataset, "PhotometricInterpretation", "")).upper() == "MONOCHROME1":
                normalized = 255 - normalized
            return normalized, "Preview generated"

        if array.ndim == 3 and array.shape[-1] in (3, 4):
            normalized = array.astype(np.float32)
            min_value = float(normalized.min())
            max_value = float(normalized.max())
            if max_value != min_value:
                normalized = ((normalized - min_value) / (max_value - min_value) * 255.0).clip(0, 255)
            return normalized.astype(np.uint8), "Preview generated"

        return None, f"Unsupported DICOM pixel shape: {tuple(array.shape)}"
    except Exception as exc:
        return None, f"Preview generation failed: {exc}"


def _build_dicom_preview(raw: bytes, window_width: float | None = None, window_center: float | None = None) -> dict[str, Any]:
    normalized, message = _normalize_dicom_array(raw, window_width=window_width, window_center=window_center)
    _, _, Image = _load_imaging_modules()
    if normalized is None or Image is None:
        return {"available": False, "image_data_url": None, "message": message}

    if getattr(normalized, "ndim", 0) == 2:
        image = Image.fromarray(normalized, mode="L")
    else:
        image = Image.fromarray(normalized, mode="RGB" if normalized.shape[-1] == 3 else "RGBA")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {"available": True, "image_data_url": f"data:image/png;base64,{encoded}", "message": message}


def _build_dicom_preview_presets(raw: bytes) -> dict[str, Any]:
    previews: dict[str, Any] = {}
    for preset in WINDOW_PRESETS:
        previews[preset["id"]] = {
            "label": preset["label"],
            **_build_dicom_preview(raw, window_width=preset["width"], window_center=preset["center"]),
        }
    return previews


def analyze_dicom_source(dicom_path: str, file_name: str | None = None) -> DicomSourceResponse:
    path = Path(dicom_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"DICOM source not found: {path}")
    raw = path.read_bytes()
    metadata = _read_dicom_metadata(raw)
    metadata["file_name"] = file_name or path.name
    metadata["source_file_path"] = str(path)
    warnings: list[str] = []
    preview = metadata.get("preview") or {}
    if not bool(preview.get("available")):
        warnings.append(str(preview.get("message") or "Preview is not available for this DICOM file."))

    series = [
        {
            "series_instance_uid": metadata.get("series_instance_uid", "not available"),
            "study_instance_uid": metadata.get("study_instance_uid", "not available"),
            "modality": metadata.get("modality", "not available"),
            "study_description": metadata.get("study_description", "not available"),
            "series_description": metadata.get("series_description", "not available"),
            "instance_count": 1,
            "example_files": [file_name or path.name],
            "preview": metadata.get("preview"),
            "preview_presets": metadata.get("preview_presets", {}),
        }
    ]

    artifacts = {
        "metadata": metadata,
        "series": {"series": series},
        "dicom_review": {
            "metadata": metadata,
            "series": series,
            "preview": metadata.get("preview"),
        },
    }
    draft_answer = (
        f"DICOM review is ready for `{file_name or path.name}`.\n\n"
        f"- Modality: {metadata.get('modality', 'not available')}\n"
        f"- Study: {metadata.get('study_description', 'not available')}\n"
        f"- Series: {metadata.get('series_description', 'not available')}\n"
        f"- Matrix: {metadata.get('rows', 'not available')} x {metadata.get('columns', 'not available')}\n\n"
        "The Studio card now shows DICOM metadata, preview state, and series summary. Use `$studio ...` for grounded imaging follow-up."
    )
    return DicomSourceResponse(
        analysis_id="",
        source_dicom_path=str(path),
        file_name=file_name or path.name,
        file_kind="DICOM",
        metadata_items=[metadata],
        series=series,
        studio_cards=[{"id": "dicom_review", "title": "DICOM Review", "subtitle": "Metadata, preview, and series summary"}],
        artifacts=artifacts,
        warnings=warnings,
        draft_answer=draft_answer,
        used_tools=["dicom_review_tool"],
        tool_registry=discover_tools(),
    )


def execute(payload: dict[str, object]) -> dict[str, object]:
    dicom_path = str(payload.get("dicom_path") or "").strip()
    if not dicom_path:
        raise ValueError("`dicom_path` is required.")
    file_name = str(payload.get("file_name") or Path(dicom_path).name).strip()
    analysis = analyze_dicom_source(dicom_path, file_name=file_name)
    return {"analysis": analysis.model_dump()}
