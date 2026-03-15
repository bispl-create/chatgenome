# Architecture

## Product Goal

Build an evidence-grounded genomics assistant that behaves like a clinical literature copilot for uploaded VCF files.

## Core Principle

The system should never ask the LLM to interpret raw genomics files directly. Instead:

1. deterministic bioinformatics services create facts
2. evidence services fetch references
3. recommendation services propose next actions
4. the LLM explains only from those structured inputs

## Flow

```mermaid
flowchart LR
    A["User Uploads VCF"] --> B["VCF Parsing Service (pysam)"]
    B --> C["Normalization / Build Checks"]
    C --> D["Annotation Layer"]
    D --> E["Evidence Retrieval"]
    E --> F["Recommendation Engine"]
    F --> G["Grounded Answer Generator"]
    G --> H["Chat UI + Evidence Panel"]
```

## Service Responsibilities

### 1. VCF Parsing Service

- validate file type and index state
- inspect header, contigs, samples, genotype structure
- summarize variant classes and representative records

### 2. Annotation Layer

Future deterministic enrichments:

- VEP or snpEff consequences
- ClinVar significance
- gnomAD frequency
- dbSNP identifiers
- COSMIC/CIViC for somatic workflows
- transcript-aware HGVS strings

### 3. Evidence Retrieval

Suggested sources:

- PubMed
- Europe PMC
- ClinicalTrials.gov
- ClinVar review status and submission summaries
- gene-disease curation resources

Ranking dimensions:

- exact variant match vs gene-only match
- disease match
- evidence type
- recency
- cohort size
- human vs in vitro

### 4. Recommendation Engine

Rule-first logic with optional LLM wording:

- `missense_variant` plus low population frequency:
  - add in silico predictors
  - check segregation
  - search functional studies
- `splice_acceptor_variant`:
  - RNA validation
  - splice predictor
  - transcript-level review
- many homozygous blocks:
  - runs of homozygosity follow-up
  - consanguinity-aware filtering

### 5. LLM Grounded Answer Layer

The answer generator receives:

- file summary
- prioritized variants
- ranked references
- recommendation objects

The answer generator returns:

- prose explanation
- inline citation ids
- explicit uncertainty
- next analysis suggestions

## API Shape

The frontend should consume a structured response:

```json
{
  "analysis_id": "uuid",
  "facts": {},
  "references": [],
  "recommendations": [],
  "ui_cards": [],
  "draft_answer": "Grounded answer text with citation ids like [REF1]."
}
```

## OpenEvidence-Like UI Pattern

- left column: chat and summary
- right column: evidence cards and variant details
- top rail: sample metadata, genome build, filter state
- bottom actions: "Explain", "Show evidence", "Suggest next steps"

## Safety Notes

- keep research use and clinical use clearly separated
- surface build mismatch risk
- surface missing annotation risk
- never hide uncertainty
- require human review for patient-facing interpretation
