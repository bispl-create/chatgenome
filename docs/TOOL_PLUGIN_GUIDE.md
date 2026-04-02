# Tool Plugin Guide

This guide is the short version of the full developer manual.

For the complete architecture and contribution flow, read:
- [DEVELOPER_MANUAL.md](DEVELOPER_MANUAL.md)

## Minimal Tool Submission

Each new tool should live under:

```text
plugins/<tool_folder>/
  tool.json
  logic.py
  run.py   # optional compatibility wrapper
```

## Required Metadata

Your `tool.json` should include:

```json
{
  "name": "example_execution_tool",
  "entrypoint": "plugins.example_execution_tool.logic:execute",
  "description": "Short deterministic tool summary.",
  "task": "example-task",
  "modality": "genomics",
  "approval_required": false,
  "source": "plugin",
  "aliases": ["example"],
  "help": {
    "summary": "What the tool does.",
    "modes": [],
    "options": [],
    "examples": [
      "@example help",
      "@example"
    ],
    "notes": []
  }
}
```

Use `help` metadata for:
- `@toolname help`
- option documentation
- curated examples

Use `entrypoint` metadata for:
- generic backend execution through `tool_runner.run_tool()`
- plugin-native routing without requiring a per-tool subprocess wrapper
- gradually making `run.py` optional

## Workflow-Aware Metadata

If the tool should participate in workflow JSON steps, add `workflow_binding`.

Example:

```json
{
  "workflow_binding": {
    "source_type": "vcf",
    "input_map": {
      "vcf_path": "$source_vcf_path",
      "facts": "$facts"
    },
    "result_path": "annotations",
    "transform": "variant_annotation_list",
    "used_tools_label": "annotation_tool",
    "fallback_transform": "annotation_local",
    "preprocess": "optional_hook_name",
    "postprocess": "optional_hook_name"
  }
}
```

Meaning:
- `input_map`: workflow context -> tool payload
- `result_path`: top-level field to read from tool output
- `transform`: normalize tool output into workflow context models
- `fallback_transform`: optional local fallback when tool execution fails
- `preprocess`: optional reusable payload-preparation hook
- `postprocess`: optional reusable bind/merge hook after tool execution

## Runtime Contract

Preferred contract:
- implement `execute(payload)` in `logic.py`
- declare `"entrypoint": "plugins.<tool_folder>.logic:execute"` in `tool.json`

Optional compatibility contract:
- keep a thin `run.py` that supports:

```bash
python run.py --input <input.json> --output <output.json>
```

If `run.py` is present, it should:

1. read JSON from `--input`
2. perform deterministic work
3. write JSON to `--output`
4. exit successfully on success

Current platform behavior:
- if `tool.json.entrypoint` exists, backend execution prefers direct import/execute
- if `entrypoint` is missing, backend falls back to `run.py`

## Required Integration Steps

After adding the plugin files, make sure you also:

1. define the request/response shape in
   - [../app/models.py](../app/models.py)
2. prefer metadata-first execution wiring
   - add `entrypoint` in `tool.json`
   - add `workflow_binding` before adding bespoke workflow code
   - avoid changing [../app/main.py](../app/main.py), [../app/services/chat.py](../app/services/chat.py), or [../app/services/workflows.py](../app/services/workflows.py) unless the tool introduces a genuinely new behavior type
3. add Studio rendering in
   - [../webapp/app/components/studioRenderers.tsx](../webapp/app/components/studioRenderers.tsx) (register renderer key)
   - [../webapp/app/components/customStudioRenderers.tsx](../webapp/app/components/customStudioRenderers.tsx) or [../webapp/app/components/genericStudioRenderers.tsx](../webapp/app/components/genericStudioRenderers.tsx) (add card component)
4. update orchestrator policy in
   - [../skills/chatgenome-orchestrator/SKILL.md](../skills/chatgenome-orchestrator/SKILL.md)
   if the tool should be recommended or used in workflows

## Testing Checklist

Python syntax:

```bash
python3 -m py_compile app/main.py app/models.py app/services/*.py plugins/<tool_folder>/logic.py
```

Frontend build:

```bash
cd webapp
npm run build
```

Runtime checks:
- `@toolname help`
- direct `@toolname`
- Studio card rendering
- workflow help if the tool is used by a workflow
- workflow execution if the tool participates in structured steps

## Preferred Design Rule

Put:
- policy in `SKILL.md`
- workflow ordering in workflow JSON
- exact tool facts in `tool.json`
- runtime execution in backend services

Avoid introducing new keyword-based chat heuristics unless absolutely necessary.
