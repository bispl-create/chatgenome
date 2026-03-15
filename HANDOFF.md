# Handoff Notes

## What this app is

`ChatGenome` is a VCF-focused genomics review workspace with:

- VCF upload and queue-style intake chat
- grounded summary generation
- Studio cards for QC, filtering view, annotation, ClinVar, VEP, ROH/recessive review, and references
- IGV integration for locus review
- GPT-backed workflow intake and analysis explanations

## Key architectural split

- Backend: `FastAPI` in `app/`
- Frontend: `Next.js` in `webapp/`
- Deterministic analysis first, LLM explanation second

## Important files

- `app/main.py`: API entrypoint
- `app/models.py`: request/response schema
- `app/services/vcf_summary.py`: base VCF parsing and QC
- `app/services/variant_annotation.py`: annotation joins
- `app/services/roh_analysis.py`: ROH calling via `bcftools roh`
- `app/services/chat.py`: grounded chat and Studio-aware responses
- `webapp/app/page.tsx`: primary UI and Studio logic
- `webapp/app/components/IgvBrowser.tsx`: IGV embedding

## Current capabilities

- representative or whole-file annotation scope
- ClinVar / gnomAD / transcript / HGVS annotation
- symbolic ALT review
- candidate ranking
- ROH + recessive shortlist
- Studio summaries forwarded into chat context

## Known limitations

- No persistent database
- No authentication / PHI guardrails
- No production-grade ACMG classifier
- ANNOVAR and VEP CLI are not yet integrated as full local pipelines
- Some Studio summaries are still frontend-derived rather than persisted backend artifacts

## Recommended next work

1. Move more Studio-derived summaries into backend response models
2. Add full-batch VEP/snpEff coverage metrics
3. Add deployment-ready Dockerfiles
4. Add phenotype/HPO-driven prioritization
5. Add user auth and protected storage before multi-user deployment
