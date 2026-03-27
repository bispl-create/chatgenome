# Frontend Renderer Inventory

## Goal

`webapp/app/page.tsx`의 현재 Studio 렌더링을 inventory해서:

- 어떤 부분이 `generic renderer`로 흡수 가능한지
- 어떤 부분이 `custom card`로 남아야 하는지
- 어떤 순서로 분해하면 안전한지

를 명확히 정리한다.

이 문서는 `F1. current renderer inventory` 결과물이다.

---

## Current Studio Surface

현재 Studio view 분기는 아래 `StudioView` union에 직접 매달려 있다.

- `candidates`
- `acmg`
- `provenance`
- `coverage`
- `rawqc`
- `sumstats`
- `prs_prep`
- `qqman`
- `samtools`
- `snpeff`
- `plink`
- `liftover`
- `ldblockshow`
- `symbolic`
- `roh`
- `qc`
- `table`
- `clinvar`
- `vep`
- `references`
- `igv`
- `annotations`

현재 구조는 `page.tsx` 안에서 `activeStudioView === "..."` 조건으로 각 card를 직접 렌더하는 방식이다.

---

## Source Shell

현재도 사실상 공통 shell은 이미 존재한다.

- 좌측 source/session panel
- 중앙 chat panel
- 우측 studio card grid
- 하단 `studioCanvas`

따라서 다음 단계의 목표는 shell을 다시 만드는 것이 아니라, `studioCanvas` 안쪽의 card 렌더링을 generic registry 구조로 바꾸는 것이다.

즉 generic화 대상의 핵심은:

- `studioCards.map(...)`
- `openStudioView(card.id)`
- `activeStudioView`별 상세 panel 렌더링

이다.

---

## Existing Reusable Primitives

현재 `page.tsx` 안에는 이미 generic card로 키울 수 있는 primitive가 있다.

- `MetricTile`
- `DistributionList`
- `VariantTable`
- `MarkdownAnswer`
- `AnnotationDetailCard`

그리고 JSX 패턴 수준의 reusable block도 반복된다.

- `resultMetricGrid`
- `resultList`
- `resultSectionSplit`
- `miniCard`
- `resultActionRow`
- `variantTableWrap`
- warning list 패턴
- artifact link button 패턴

즉 완전히 처음부터 generic renderer를 만드는 것이 아니라, 현재 있는 primitive를 추출해 registry로 올리는 작업이 맞다.

---

## Generic Renderer Candidates

아래 view들은 대부분 공통 primitive 조합으로 표현 가능하다.

### 1. Metric + List + Artifacts형

공통 패턴:

- 상단 metric grid
- 중간 result list
- 하단 artifact/action links

대표 view:

- `samtools`
- `snpeff`
- `liftover`
- `ldblockshow`
- `qqman`
- `coverage`

generic card 후보:

- `MetricSummaryCard`
- `KeyValueListCard`
- `ArtifactLinksCard`
- `WarningListCard`

### 2. Metric + Distribution형

공통 패턴:

- 상단 metric grid
- 분포 요약 1~2개
- 간단한 note

대표 view:

- `qc`
- `vep`
- `clinvar`
- 일부 `provenance`

generic card 후보:

- `DistributionSummaryCard`
- `NoteCard`

### 3. Table/Preview형

공통 패턴:

- preview table
- 검색/필터 또는 load-more
- optional selection

대표 view:

- `sumstats`
- `prs_prep`의 score-file preview
- `table`

generic card 후보:

- `PreviewTableCard`
- `SearchableTableCard`

### 4. Reference/Text형

공통 패턴:

- markdown/text body
- ordered list of references

대표 view:

- `references`
- 일부 provenance/help/answer 영역

generic card 후보:

- `TextBlockCard`
- `ReferenceListCard`

---

## Custom Renderer Candidates

아래 view들은 generic primitive만으로는 부족하거나 interaction이 강하다.

### 1. `annotations`

이유:

- annotation dropdown
- annotation search
- `AnnotationDetailCard`
- selection state와 detail state가 강하게 연결됨

판정:

- custom 유지
- 다만 내부 section 일부는 generic primitive로 분해 가능

### 2. `igv`

이유:

- 브라우저 embed
- 외부 viewer 성격

판정:

- custom 유지

### 3. `plink`

이유:

- 실행 form
- command preview
- `qc`/`score` 두 모드
- 결과 shape도 mode별로 다름

판정:

- custom 유지
- 단, 결과 metric/list/action 부분은 일부 generic primitive 사용 가능

### 4. `rawqc`

이유:

- FastQC module card 반복은 generic에 가깝지만,
- source-level review card 성격이 강하고 report action도 결합됨

판정:

- 1차는 custom 유지
- 후속 단계에서 `module review` 부분만 generic list card로 추출 가능

### 5. `prs_prep`

이유:

- build check
- harmonization
- score-file preview
- readiness narrative

판정:

- custom 유지
- 내부 preview/warning/action section은 generic primitive로 전환 가능

### 6. `candidates`, `acmg`, `roh`, `symbolic`

이유:

- variant-specific navigation
- annotation view와 강하게 연결
- scoring/triage semantics 포함

판정:

- VCF domain custom registry에 남기는 것이 적절

---

## Renderer Families

현재 view를 generic화 기준으로 다시 묶으면 아래와 같다.

### Family A. Generic summary cards

- `samtools`
- `snpeff`
- `liftover`
- `ldblockshow`
- `qqman`
- `coverage`
- `qc`
- `vep`
- `references`

### Family B. Generic preview/table cards

- `sumstats`
- `table`
- `prs_prep` 일부

### Family C. Domain custom VCF cards

- `candidates`
- `acmg`
- `roh`
- `symbolic`
- `clinvar`
- `annotations`
- `igv`

### Family D. Domain custom workflow cards

- `plink`
- `rawqc`
- `prs_prep`
- `provenance`

이 분류를 기준으로 하면, 1차 generic renderer 도입 시 전체 분기의 절반 이상을 generic family A/B로 흡수할 수 있다.

---

## Current Pain Points

현재 구조의 병목은 아래와 같다.

### 1. `StudioView`가 UI 구조와 1:1 결합

현재는:

- card id
- selected view
- renderer implementation

이 하나의 union에 강하게 묶여 있다.

### 2. renderer registry가 아니라 JSX 조건문 묶음

현재는 `activeStudioView === "..."` 분기가 길게 이어진다.

이 때문에:

- 새 view 추가 시 `page.tsx` 수정이 거의 필수
- 어떤 view가 generic 가능한지 드러나지 않음

### 3. result shape와 renderer가 느슨한 contract가 없음

현재는 사실상 컴포넌트가 payload shape를 직접 안다.

앞으로는 최소한 아래 contract가 필요하다.

- `result_kind`
- `requested_view`
- optional `studio.renderer`

---

## Proposed F2 Extraction Targets

`F2. primitive extraction`에서 우선 뽑을 대상은 아래가 적절하다.

### Immediate primitives

- `StudioMetricGrid`
- `StudioWarningList`
- `StudioArtifactLinks`
- `StudioDistributionPanel`
- `StudioPreviewTable`
- `StudioSimpleList`

### Immediate renderer wrappers

- `GenericMetricListArtifactView`
- `GenericDistributionView`
- `GenericPreviewTableView`

---

## Proposed F3 Renderer Registry

권장 구조:

```ts
type StudioRendererKey =
  | "generic.metric_list_artifacts"
  | "generic.distribution"
  | "generic.preview_table"
  | "vcf.annotations"
  | "vcf.candidates"
  | "vcf.igv"
  | "workflow.plink"
  | "workflow.prs_prep"
  | "workflow.rawqc";
```

그리고 registry는 대략 아래 흐름이 적절하다.

1. `studio.renderer`가 있으면 custom renderer registry 조회
2. 없으면 `result_kind + requested_view` 기반 generic renderer 선택
3. 그래도 없으면 fallback text/JSON card 표시

---

## Proposed Migration Order

### Step 1

`page.tsx`에서 아래 view부터 generic wrapper로 치환

- `samtools`
- `snpeff`
- `liftover`
- `ldblockshow`
- `qqman`

이유:

- direct tool 결과라 payload가 비교적 선명함
- metric/list/artifact 패턴이 반복됨

### Step 2

다음 view를 generic distribution/table family로 치환

- `qc`
- `vep`
- `references`
- `sumstats`

### Step 3

custom registry로 분리

- `plink`
- `prs_prep`
- `rawqc`
- `annotations`
- `igv`
- `candidates`
- `acmg`
- `roh`
- `symbolic`

### Step 4

`StudioView` union을 줄이고, `card.id -> renderer key` 매핑으로 전환

---

## Final F1 Conclusion

현재 프런트는 완전히 bespoke는 아니다.

이미 다음 두 가지가 존재한다.

- 재사용 가능한 primitive
- 반복되는 metric/list/table/artifact 패턴

따라서 다음 단계의 핵심은:

- `page.tsx`를 한 번에 갈아엎는 것

이 아니라,

- 기존 반복 패턴을 primitive와 renderer registry로 끌어올리는 것

이다.

이번 inventory 기준으로:

- 먼저 generic화할 수 있는 영역은 `samtools`, `snpeff`, `liftover`, `ldblockshow`, `qqman`, `qc`, `sumstats`, `references`, `vep`
- custom으로 남겨야 하는 핵심은 `annotations`, `igv`, `plink`, `prs_prep`, `rawqc`, `candidates`, `acmg`, `roh`, `symbolic`

로 정리된다.
