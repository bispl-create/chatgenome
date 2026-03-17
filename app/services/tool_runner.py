from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from app.models import ToolInfo


ROOT_DIR = Path(__file__).resolve().parents[2]
PLUGINS_DIR = ROOT_DIR / "plugins"


def discover_tools() -> list[ToolInfo]:
    tools: list[ToolInfo] = []
    if not PLUGINS_DIR.exists():
        return tools

    for manifest_path in sorted(PLUGINS_DIR.glob("*/tool.json")):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        tools.append(
            ToolInfo(
                name=str(payload.get("name", manifest_path.parent.name)),
                description=str(payload.get("description", "")),
                task=str(payload.get("task", "unknown")),
                modality=str(payload.get("modality", "genomics")),
                approval_required=bool(payload.get("approval_required", False)),
                source=str(payload.get("source", "plugin")),
            )
        )
    return tools


def run_tool(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    tool_dir = _find_tool_dir(tool_name)
    run_path = tool_dir / "run.py"
    if not run_path.exists():
        raise FileNotFoundError(f"Tool runner not found for {tool_name}: {run_path}")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as input_file:
        json.dump(payload, input_file, ensure_ascii=False)
        input_path = input_file.name

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as output_file:
        output_path = output_file.name

    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    pythonpath_parts = [str(ROOT_DIR)]
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    command = [sys.executable, str(run_path), "--input", input_path, "--output", output_path]
    completed = subprocess.run(
        command,
        cwd=str(ROOT_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"Tool {tool_name} failed with exit code {completed.returncode}: "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )

    return json.loads(Path(output_path).read_text(encoding="utf-8"))


def _find_tool_dir(tool_name: str) -> Path:
    for manifest_path in PLUGINS_DIR.glob("*/tool.json"):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(payload.get("name")) == tool_name:
            return manifest_path.parent
    raise FileNotFoundError(f"Tool manifest not found for {tool_name}")
