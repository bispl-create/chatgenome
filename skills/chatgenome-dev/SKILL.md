---
name: chatgenome-dev
description: Use when developing, debugging, extending, or handing off the ChatGenome VCF analysis workspace. Covers the FastAPI backend, Next.js Studio UI, grounded chat flow, genomics annotation/QC/ROH features, and GitHub handoff conventions for this repository.
---

# ChatGenome Dev

Use this skill when working on the `ChatGenome` repository.

## Scope

This skill is for:

- frontend work in `webapp/`
- backend/API work in `app/`
- grounded chat and Studio-card integration
- VCF/QC/annotation/ROH analysis features
- GitHub handoff and contributor setup

Do not use this skill for general genomics analysis outside this repo unless the task is explicitly about this app.

## First files to inspect

Start with these files before making assumptions:

- `README.md`
- `HANDOFF.md`
- `app/main.py`
- `app/models.py`
- `app/services/chat.py`
- `app/services/vcf_summary.py`
- `app/services/roh_analysis.py`
- `webapp/app/page.tsx`
- `webapp/app/components/IgvBrowser.tsx`
- `webapp/app/globals.css`

## Working model

Keep this architecture intact unless the task explicitly changes it:

1. Deterministic genomics analysis first
2. Studio summaries computed from analysis artifacts
3. Grounded chat explains analysis and Studio state
4. UI exposes `Sources / Chat / Studio`

The model should explain grounded results, not invent variant interpretation from raw VCF rows.

## Repo-specific conventions

- Backend is `FastAPI` under `app/`
- Frontend is `Next.js` under `webapp/`
- The main user experience lives in `webapp/app/page.tsx`
- Studio cards and chat context must stay aligned
- When a Studio card computes a result that chat should explain, pass that result through `studio_context`
- `.env` must stay local only; use `.env.example` as the template

## Common tasks

### Add or change analysis features

When adding a new analysis result:

1. Prefer generating it in backend services under `app/services/`
2. Add response fields in `app/models.py`
3. Expose it in `app/main.py`
4. Render it in a Studio card
5. Forward a compact summary into chat `studio_context` if users may ask about it

### Fix chat/Studio mismatch

If the user says Chat does not understand a Studio card:

1. Check the frontend-derived Studio summary in `webapp/app/page.tsx`
2. Verify that the same information is sent in `studio_context`
3. Verify `app/services/chat.py` consumes that field deterministically
4. Restart the API if backend code changed

### Frontend bugs

For rendering or layout bugs:

1. Inspect `webapp/app/page.tsx`
2. Inspect `webapp/app/globals.css`
3. If IGV is involved, inspect `webapp/app/components/IgvBrowser.tsx`
4. Run TypeScript checks after changes

## Validation

After meaningful changes, prefer these checks:

- `python3 -m py_compile` on changed backend files
- `npm run build:webapp` or TypeScript checks for frontend changes
- a real local API/UI smoke test if chat, Studio, or analysis flow changed

## Handoff guidance

If the user wants to share this project with collaborators:

- use the GitHub repo as the source of truth
- keep secrets out of git
- ensure `README.md`, `CONTRIBUTING.md`, and `HANDOFF.md` are current
- tell collaborators to copy `.env.example` to `.env` and use their own `OPENAI_API_KEY`

## Related skills

- For genomics file logic, also use [$pysam-genomic-data-analysis](/Users/jongcye/Documents/Codex/.codex/skills/pysam-genomic-data-analysis/SKILL.md)
- For OpenAI product/API questions, also use [$openai-docs](/Users/jongcye/Documents/Codex/.codex/skills/.system/openai-docs/SKILL.md)
