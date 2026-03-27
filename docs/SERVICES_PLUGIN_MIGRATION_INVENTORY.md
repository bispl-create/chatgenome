# Services To Plugin Migration Inventory

## Goal

Move the codebase toward a plugin-native platform where:

- new tools are added mainly under `plugins/<tool>/`
- `app/services` keeps platform-core orchestration code
- workflow- and source-level expansion does not require editing core files in normal cases

## Target Structure

### Platform Core

These should remain under `app/services/`:

- chat routing
- workflow orchestration
- workflow response assembly
- bootstrap launching
- source registry
- tool discovery and generic tool execution
- jobs and cache utilities

### Plugin-Native Tool Logic

These should move into plugin folders as `logic.py` or equivalent:

- tool-specific business logic
- tool-specific local execution wrappers
- tool-specific parsing and output shaping

### Shared Domain Helpers

These may remain shared for now, but should be treated as reusable libraries rather than tool entrypoints:

- recommendation builders
- reference builders
- lightweight annotation/card helper functions

## Current Classification

### Keep In Platform Core

- `app/services/chat.py`
- `app/services/workflows.py`
- `app/services/workflow_responses.py`
- `app/services/workflow_transforms.py`
- `app/services/workflow_fallbacks.py`
- `app/services/workflow_hooks.py`
- `app/services/workflow_internal_steps.py`
- `app/services/workflow_agent.py`
- `app/services/source_bootstrap.py`
- `app/services/source_registry.py`
- `app/services/tool_runner.py`
- `app/services/jobs.py`
- `app/services/cache_store.py`

Reason:

- these files implement routing, orchestration, registry lookup, bootstrap flow, response assembly, or reusable execution primitives

### Tool-Specific Files To Migrate Into Plugins

- `app/services/gatk_liftover.py`
  - target plugin: `plugins/gatk_liftover_vcf_tool/logic.py`
- `app/services/samtools.py`
  - target plugin: `plugins/samtools_execution_tool/logic.py`
- `app/services/snpeff.py`
  - target plugin: `plugins/snpeff_execution_tool/logic.py`
- `app/services/ldblockshow.py`
  - target plugin: `plugins/ldblockshow_execution_tool/logic.py`
- `app/services/plink.py`
  - target plugin: `plugins/plink_execution_tool/logic.py`
- `app/services/r_vcf_plots.py`
  - target plugins:
    - `plugins/qqman_execution_tool/logic.py`
    - future `cmplot` or plot plugin if separated
- `app/services/fastqc.py`
  - target plugin: `plugins/fastqc_execution_tool/logic.py`
- `app/services/filtering.py`
  - target plugin: `plugins/filtering_view_tool/logic.py`
- `app/services/roh_analysis.py`
  - target plugin: `plugins/roh_analysis_tool/logic.py`
- `app/services/cadd_lookup.py`
  - target plugin: `plugins/cadd_lookup_tool/logic.py`
- `app/services/revel_lookup.py`
  - target plugin: `plugins/revel_lookup_tool/logic.py`
- `app/services/candidate_ranking.py`
  - target plugin: `plugins/candidate_ranking_tool/logic.py`
- `app/services/prs_prep.py`
  - target plugin or internal engine:
    - likely `plugins/plink_execution_tool/logic.py` for score-specific helpers
    - or a new `plugins/prs_prep_tool/`
- `app/services/summary_stats.py`
  - mostly summary-statistics ingestion logic
  - likely target:
    - `plugins/clinical_coverage_tool/logic.py` if reused there, or
    - a future dedicated `summary_stats_intake` plugin
- `app/services/vcf_summary.py`
  - target plugin: `plugins/vcf_qc_tool/logic.py`
- `app/services/variant_annotation.py`
  - target plugin: `plugins/annotation_tool/logic.py`

Reason:

- these files implement concrete tool behavior and should not remain in platform core long-term

### Shared Domain Helpers To Keep Shared For Now

- `app/services/annotation.py`
  - card/draft-answer helpers used by workflow response assembly
- `app/services/recommendation.py`
  - shared recommendation builder
- `app/services/references.py`
  - shared reference bundle builder

Reason:

- these are reused across multiple workflow steps and are closer to shared presentation/domain helpers than direct tool entrypoints

## Migration Priority

### Priority 1: Straightforward Single-Tool Moves

These are the best first pilots because each file maps cleanly to one plugin.

1. `app/services/samtools.py`
2. `app/services/gatk_liftover.py`
3. `app/services/snpeff.py`
4. `app/services/ldblockshow.py`
5. `app/services/fastqc.py`

### Priority 2: Multi-Mode Or Multi-Consumer Tool Logic

These are still tool-specific, but carry more workflow coupling.

1. `app/services/plink.py`
2. `app/services/filtering.py`
3. `app/services/roh_analysis.py`
4. `app/services/cadd_lookup.py`
5. `app/services/revel_lookup.py`

### Priority 3: Logic That May Need Refactoring Before Moving

These should likely move after platform core is slightly more stable.

1. `app/services/candidate_ranking.py`
2. `app/services/prs_prep.py`
3. `app/services/summary_stats.py`
4. `app/services/vcf_summary.py`
5. `app/services/variant_annotation.py`

## Recommended Migration Pattern

For each tool migration:

1. add `plugins/<tool>/logic.py`
2. move the tool-specific service implementation into that file
3. keep `plugins/<tool>/run.py` thin
4. update any direct imports in core code to call the plugin logic or run through generic runtime helpers
5. leave platform-core helpers in `app/services/`

Thin `run.py` target pattern:

```python
from app.services.plugin_runtime import run_plugin_cli
from .logic import execute

if __name__ == "__main__":
    run_plugin_cli(execute)
```

## What Should Not Happen

- new workflows should not require edits to `workflow_hooks.py`, `workflow_fallbacks.py`, or `workflow_internal_steps.py` unless a genuinely new reusable behavior is introduced
- new tools should not require edits to `chat.py`, `main.py`, or `workflows.py` in the normal case
- `app/services` should not accumulate new tool-specific modules once plugin-native migration starts

## Recommended Next Execution Order

1. introduce `plugin_runtime.py`
2. migrate `samtools.py`
3. migrate `gatk_liftover.py`
4. migrate `snpeff.py`
5. migrate `ldblockshow.py`
6. migrate `fastqc.py`
7. re-check direct `@tool` and workflow execution after each migration
