# Tool Plugin Guide

This guide explains how a collaborator can add a new tool to `ChatGenome`.

The current architecture is:

1. `ChatGenome` receives a VCF and user request.
2. The orchestrator skill decides which registered tools should run.
3. The shared runner executes tools from `plugins/`.
4. Tool output is returned as structured JSON.
5. `Studio` renders the resulting artifacts and `Chat` explains grounded outputs.

## What A Collaborator Needs To Submit

Each tool should live in its own folder under:

```text
plugins/<tool_folder>/
```

The minimum required files are:

```text
plugins/<tool_folder>/
  tool.json
  run.py
```

Optional files:

```text
plugins/<tool_folder>/
  README.md
  requirements.txt
  assets/
```

## Required `tool.json`

Each tool must provide a `tool.json` manifest.

Example:

```json
{
  "name": "example_variant_tool",
  "description": "Summarizes a variant subset for a specific review task.",
  "task": "variant-summary",
  "modality": "genomics",
  "approval_required": false,
  "source": "plugin"
}
```

Field meanings:

- `name`: unique tool name shown in the registry
- `description`: short explanation for collaborators and UI tooltips
- `task`: stable task label such as `vcf-qc`, `annotation`, or `roh-analysis`
- `modality`: current domain, usually `genomics`
- `approval_required`: whether chat should ask for approval before execution
- `source`: use `plugin` for collaborator tools, `internal` for core tools maintained in the app

## Required `run.py`

The shared runner executes:

```bash
python run.py --input <input.json> --output <output.json>
```

Your script must:

1. Read the JSON payload from `--input`
2. Perform deterministic work
3. Write a JSON result to `--output`
4. Exit with code `0` on success
5. Exit non-zero with a meaningful error message on failure

Minimal template:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))

    result = {
        "tool": "example_variant_tool",
        "summary": "Explain briefly what the tool did.",
        "artifacts": {}
    }

    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
```

## Input Contract

`ChatGenome` tool payloads are plain JSON dictionaries. Different tools receive different keys.

Typical inputs include:

- `vcf_path`
- `facts`
- `annotations`
- `roh_segments`
- `references`
- `recommendations`
- `limit`
- `scope`

Examples from the current built-in tools:

- `vcf_qc_tool`
  - input: `vcf_path`, `max_examples`
- `annotation_tool`
  - input: `vcf_path`, `facts`, `scope`, `limit`
- `roh_analysis_tool`
  - input: `vcf_path`
- `candidate_ranking_tool`
  - input: `annotations`, `roh_segments`, `limit`

When adding a new tool, document the expected input keys in the tool's local `README.md` if they are not obvious.

## Output Contract

At minimum, return:

```json
{
  "tool": "example_variant_tool",
  "summary": "What the tool produced."
}
```

Depending on the task, a tool may also return:

- `facts`
- `annotations`
- `roh_segments`
- `candidate_variants`
- `clinvar_summary`
- `consequence_summary`
- `clinical_coverage_summary`
- `filtering_summary`
- `symbolic_alt_summary`
- `draft_answer`

The key rule is:

- return structured JSON
- do not return markdown-only text when a structured shape is possible

## How Registration Works

The registry is discovered automatically from:

```text
plugins/*/tool.json
```

You do not need to edit a central list to make the tool discoverable.

Registry code:

- [tool_runner.py](/Users/jongcye/Documents/Codex/workspace/bioinformatics_vcf_evidence_mvp/app/services/tool_runner.py)

## How To Connect A Tool To The App

There are two parts:

1. Tool execution
2. UI use

### 1. Tool execution in backend

In most cases, a core maintainer wires the tool into backend analysis flow in:

- [main.py](/Users/jongcye/Documents/Codex/workspace/bioinformatics_vcf_evidence_mvp/app/main.py)

Pattern:

```python
try:
    tool_result = run_tool("example_variant_tool", {...})
    used_tools.append("example_variant_tool")
    # parse structured result here
except Exception:
    # fallback logic here
```

### 2. UI rendering

If the tool produces a new structured artifact, `Studio` may need a renderer in:

- [page.tsx](/Users/jongcye/Documents/Codex/workspace/bioinformatics_vcf_evidence_mvp/webapp/app/page.tsx)

Not every tool needs a brand-new card. Some tools can feed existing cards.

## Recommended Design Rules

- Prefer deterministic outputs over free-form prose
- Keep input and output small and explicit
- Reuse existing models when possible
- Do not embed secrets in tool code
- Do not assume network access unless explicitly arranged
- Fail clearly when dependencies are missing

## Testing Checklist

Before submitting a tool:

1. Validate the manifest:

```bash
cat plugins/<tool_folder>/tool.json
```

2. Run the script directly with a sample JSON input

3. Run Python syntax checks:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile plugins/<tool_folder>/run.py
```

4. If backend wiring changed, run:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall app plugins
```

5. If frontend rendering changed, run:

```bash
cd webapp
PATH=/Users/jongcye/Documents/Codex/.local/node-v22.14.0-darwin-arm64/bin:$PATH npm run build
```

## Suggested Submission Format For Collaborators

Submit:

- the plugin folder
- a short `README.md`
- expected input keys
- example output JSON
- notes on required dependencies

Good collaborator handoff example:

```text
plugins/example_variant_tool/
  tool.json
  run.py
  README.md
  sample_input.json
  sample_output.json
```

## Current Built-In Tools

At the moment, `ChatGenome` includes:

- `vcf_qc_tool`
- `annotation_tool`
- `roh_analysis_tool`
- `candidate_ranking_tool`
- `clinvar_review_tool`
- `vep_consequence_tool`
- `clinical_coverage_tool`
- `filtering_view_tool`
- `symbolic_alt_tool`
- `grounded_summary_tool`

These are good references for new collaborator tools.
