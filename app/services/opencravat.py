from __future__ import annotations

import csv
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

from app.models import OpenCravatPreviewRow, OpenCravatRequest, OpenCravatResponse


OPENCRAVAT_OUTPUT_DIR = Path(
    os.getenv(
        "OPENCRAVAT_OUTPUT_DIR",
        "/Users/jongcye/Documents/Codex/workspace/bioinformatics_vcf_evidence_mvp/outputs/opencravat",
    )
)
OPENCRAVAT_LOCAL_ROOT = Path(
    os.getenv(
        "OPENCRAVAT_LOCAL_ROOT",
        "/Users/jongcye/Documents/Codex/workspace/bioinformatics_vcf_evidence_mvp/.opencravat",
    )
)
OPENCRAVAT_SHARED_MODULES_DIR = Path(
    os.getenv(
        "OPENCRAVAT_SHARED_MODULES_DIR",
        "/Users/Shared/open-cravat/modules",
    )
)
OPENCRAVAT_TIMEOUT_SECONDS = int(os.getenv("OPENCRAVAT_TIMEOUT_SECONDS", "10"))
OPENCRAVAT_POST_TIMEOUT_GRACE_SECONDS = int(os.getenv("OPENCRAVAT_POST_TIMEOUT_GRACE_SECONDS", "3"))


def _resolve_oc_bin() -> str:
    explicit = os.getenv("OPENCRAVAT_OC_BIN")
    if explicit:
        return explicit
    default_venv = Path(__file__).resolve().parents[2] / ".venv/bin/oc"
    if default_venv.exists():
        return str(default_venv)
    found = shutil.which("oc")
    if found:
        return found
    raise FileNotFoundError(
        "OpenCRAVAT executable not found. Install open-cravat and ensure `oc` is available, or set OPENCRAVAT_OC_BIN."
    )


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def _default_run_name(vcf_path: str) -> str:
    return _safe_name(Path(vcf_path).stem)


def _ensure_system_conf() -> Path:
    OPENCRAVAT_LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
    conf_dir = OPENCRAVAT_LOCAL_ROOT / "conf"
    work_dir = OPENCRAVAT_LOCAL_ROOT / "workspace"
    jobs_dir = OPENCRAVAT_LOCAL_ROOT / "jobs"
    log_dir = OPENCRAVAT_LOCAL_ROOT / "logs"
    metrics_dir = OPENCRAVAT_LOCAL_ROOT / "metrics"
    for path in (conf_dir, work_dir, jobs_dir, log_dir, metrics_dir, work_dir / "cache"):
        path.mkdir(parents=True, exist_ok=True)

    system_conf_path = conf_dir / "cravat-system.yml"
    system_conf = "\n".join(
        [
            "publish_url: https://publish.opencravat.org",
            "store_url: https://store.opencravat.org",
            "metrics_url: https://metrics.opencravat.org",
            f"work_dir: {work_dir}",
            f"modules_dir: {OPENCRAVAT_SHARED_MODULES_DIR}",
            f"jobs_dir: {jobs_dir}",
            f"log_dir: {log_dir}",
            f"metrics_dir: {metrics_dir}",
            "",
        ]
    )
    system_conf_path.write_text(system_conf, encoding="utf-8")
    return system_conf_path


def _prepare_request(request: OpenCravatRequest) -> tuple[str, Path, Path, str]:
    input_path = Path(request.vcf_path).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"VCF not found: {request.vcf_path}")
    oc_bin = _resolve_oc_bin()
    output_dir = Path(request.output_dir).expanduser().resolve() if request.output_dir else OPENCRAVAT_OUTPUT_DIR.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_name = _safe_name(request.run_name or _default_run_name(request.vcf_path))
    return oc_bin, input_path, output_dir, run_name


def _resolve_oc_python(oc_bin: str) -> str:
    candidate = Path(oc_bin).resolve().parent / "python"
    if candidate.exists():
        return str(candidate)
    return shutil.which("python3") or "python3"


def _detect_report_path(output_dir: Path, run_name: str, suffixes: tuple[str, ...]) -> str | None:
    for suffix in suffixes:
        path = output_dir / f"{run_name}{suffix}"
        if path.exists():
            return str(path)
    return None


def _detect_variant_table_path(output_dir: Path, run_name: str) -> str | None:
    for suffix in (".crv", ".original_input.var", ".extra_vcf_info.var"):
        path = output_dir / f"{run_name}{suffix}"
        if path.exists() and path.stat().st_size > 0:
            return str(path)
    return None


def _load_status_info(output_dir: Path, run_name: str) -> tuple[str | None, str | None]:
    status_json_path = output_dir / f"{run_name}.status.json"
    if not status_json_path.exists():
        return None, None
    try:
        import json

        payload = json.loads(status_json_path.read_text(encoding="utf-8"))
        return payload.get("status"), str(status_json_path)
    except Exception:
        return None, str(status_json_path)


def _load_oc_table_preview(path_str: str | None, limit: int) -> list[OpenCravatPreviewRow]:
    if not path_str:
        return []
    path = Path(path_str)
    if not path.exists():
        return []
    rows: list[OpenCravatPreviewRow] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        first_line = handle.readline()
        handle.seek(0)
        if first_line.startswith("#"):
            headers: list[str] | None = None
            for line in handle:
                raw = line.rstrip("\n")
                if raw.startswith("#"):
                    if raw.startswith("#UID\t"):
                        headers = raw[1:].split("\t")
                    continue
                if not headers:
                    continue
                values = raw.split("\t")
                row = {
                    str(key): str(value)
                    for key, value in zip(headers, values)
                }
                rows.append(OpenCravatPreviewRow(columns=row))
                if len(rows) >= limit:
                    break
            return rows

        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            rows.append(OpenCravatPreviewRow(columns={str(key): str(value) for key, value in row.items()}))
            if len(rows) >= limit:
                break
    return rows


def _cleanup_incomplete_run(output_dir: Path, run_name: str) -> None:
    """Remove stale partial artifacts that can confuse a rerun."""
    for path in output_dir.glob(f"{run_name}*"):
        try:
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
        except FileNotFoundError:
            continue


def _wait_for_opencravat_artifact(
    *,
    genome: str,
    input_path: str,
    output_dir: Path,
    run_name: str,
    command_preview: str,
    preview_limit: int,
    seconds: int,
) -> OpenCravatResponse | None:
    deadline = time.time() + max(seconds, 0)
    while time.time() < deadline:
        loaded = load_opencravat_result(
            genome=genome,
            input_path=input_path,
            output_dir=output_dir,
            run_name=run_name,
            command_preview=command_preview,
            preview_limit=preview_limit,
        )
        if loaded is not None:
            return loaded
        time.sleep(1)
    return None


def load_opencravat_result(
    *,
    genome: str,
    input_path: str,
    output_dir: str | Path,
    run_name: str,
    command_preview: str = "oc run <source.vcf> ...",
    preview_limit: int = 5,
) -> OpenCravatResponse | None:
    resolved_output_dir = Path(output_dir).expanduser().resolve()
    status, status_json_path = _load_status_info(resolved_output_dir, run_name)
    sqlite_path = _detect_report_path(resolved_output_dir, run_name, (".sqlite",))
    text_report_path = _detect_report_path(resolved_output_dir, run_name, (".variant.tsv", ".tsv", ".variant.txt", ".txt"))
    variant_table_path = _detect_variant_table_path(resolved_output_dir, run_name)
    excel_report_path = _detect_report_path(resolved_output_dir, run_name, (".xlsx",))
    vcf_report_path = _detect_report_path(resolved_output_dir, run_name, (".vcf", ".vcf.gz"))
    csv_report_path = _detect_report_path(resolved_output_dir, run_name, (".variant.csv", ".csv"))
    if sqlite_path and Path(sqlite_path).exists() and Path(sqlite_path).stat().st_size == 0:
        sqlite_path = None
    if sqlite_path is None and text_report_path is None and variant_table_path is None and excel_report_path is None and vcf_report_path is None and csv_report_path is None:
        return None
    display_status = status
    error_message = None
    if variant_table_path is not None:
        status_value = (status or "").strip().lower()
        if not status_value or status_value == "starting" or status_value.startswith("started ") or status_value == "error":
            display_status = "Partial result available"
            if status_value == "error":
                error_message = (
                    "OpenCRAVAT produced a usable variant table, but one or more downstream reporting steps did not finish."
                )
    preview_source = text_report_path or variant_table_path
    return OpenCravatResponse(
        tool="opencravat",
        genome=genome,
        input_path=input_path,
        output_dir=str(resolved_output_dir),
        run_name=run_name,
        command_preview=command_preview,
        status=display_status,
        error_message=error_message,
        status_json_path=status_json_path,
        sqlite_path=sqlite_path,
        text_report_path=text_report_path,
        variant_table_path=variant_table_path,
        excel_report_path=excel_report_path,
        vcf_report_path=vcf_report_path,
        csv_report_path=csv_report_path,
        preview_rows=_load_oc_table_preview(preview_source, preview_limit),
    )


def run_opencravat(request: OpenCravatRequest) -> OpenCravatResponse:
    oc_bin, input_path, output_dir, run_name = _prepare_request(request)
    command_preview = " ".join([oc_bin, "run", str(input_path), "-l", request.genome, "-d", str(output_dir), "-n", run_name])
    cached = load_opencravat_result(
        genome=request.genome,
        input_path=str(input_path),
        output_dir=output_dir,
        run_name=run_name,
        command_preview=command_preview,
        preview_limit=request.preview_limit,
    )
    if cached is not None:
        return cached

    prior_status, _ = _load_status_info(output_dir, run_name)
    if prior_status and prior_status.lower() == "starting":
        _cleanup_incomplete_run(output_dir, run_name)

    oc_python = _resolve_oc_python(oc_bin)
    system_conf_path = _ensure_system_conf()
    oc_args = [
        "run",
        str(input_path),
        "-l",
        request.genome,
        "-d",
        str(output_dir),
        "-n",
        run_name,
    ]
    if request.annotators:
        oc_args.extend(["-a", *request.annotators])
    if request.report_types:
        oc_args.extend(["-t", *request.report_types])

    wrapper = "\n".join(
        [
            "import sys",
            "import psutil",
            "orig = psutil.swap_memory",
            "def _safe_swap_memory():",
            "    try:",
            "        return orig()",
            "    except Exception:",
            "        from collections import namedtuple",
            "        S = namedtuple('sswap', 'total used free percent sin sout')",
            "        return S(0, 0, 0, 0.0, 0, 0)",
            "psutil.swap_memory = _safe_swap_memory",
            "import cravat.cravat_class as cc",
            "class _LocalManager:",
            "    def register(self, *args, **kwargs):",
            "        return None",
            "    def start(self):",
            "        return None",
            "    def StatusWriter(self, status_json_path):",
            "        return cc.StatusWriter(status_json_path)",
            "cc.MyManager = _LocalManager",
            "from cravat.oc import main",
            "sys.argv = ['oc'] + sys.argv[1:]",
            "main()",
        ]
    )
    cmd = [oc_python, "-c", wrapper, *oc_args]

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(output_dir),
            env={
                **os.environ,
                "OPENCRAVAT_SYSTEM_CONF_PATH": str(system_conf_path),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=OPENCRAVAT_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except Exception:
                process.kill()
            process.wait()
            recovered = _wait_for_opencravat_artifact(
                genome=request.genome,
                input_path=str(input_path),
                output_dir=output_dir,
                run_name=run_name,
                command_preview=command_preview,
                preview_limit=request.preview_limit,
                seconds=OPENCRAVAT_POST_TIMEOUT_GRACE_SECONDS,
            )
            if recovered is not None:
                return recovered
            raise RuntimeError(
                f"OpenCRAVAT timed out after {OPENCRAVAT_TIMEOUT_SECONDS} seconds for run `{run_name}`."
            ) from exc
        completed = subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
    except RuntimeError:
        raise
    except subprocess.TimeoutExpired as exc:
        recovered = _wait_for_opencravat_artifact(
            genome=request.genome,
            input_path=str(input_path),
            output_dir=output_dir,
            run_name=run_name,
            command_preview=command_preview,
            preview_limit=request.preview_limit,
            seconds=OPENCRAVAT_POST_TIMEOUT_GRACE_SECONDS,
        )
        if recovered is not None:
            return recovered
        raise RuntimeError(
            f"OpenCRAVAT timed out after {OPENCRAVAT_TIMEOUT_SECONDS} seconds for run `{run_name}`."
        ) from exc
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "Unknown OpenCRAVAT failure"
        raise RuntimeError(message)

    loaded = load_opencravat_result(
        genome=request.genome,
        input_path=str(input_path),
        output_dir=output_dir,
        run_name=run_name,
        command_preview=" ".join([oc_bin, *oc_args]),
        preview_limit=request.preview_limit,
    )
    if loaded is None:
        raise RuntimeError("OpenCRAVAT completed without producing a usable report artifact.")
    if loaded.status and loaded.status.lower() not in {"finished", "completed", "success"} and loaded.variant_table_path is None:
        raise RuntimeError(f"OpenCRAVAT job ended with status '{loaded.status}'. See {loaded.status_json_path}.")
    return loaded
