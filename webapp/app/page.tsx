"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import IgvBrowser from "./components/IgvBrowser";

type TranscriptAnnotation = {
  transcript_id: string;
  transcript_biotype: string;
  canonical: string;
  exon: string;
  intron: string;
  hgvsc: string;
  hgvsp: string;
  protein_id: string;
  amino_acids: string;
  codons: string;
};

type VariantAnnotation = {
  contig: string;
  pos_1based: number;
  ref: string;
  alts: string[];
  genotype: string;
  gene: string;
  consequence: string;
  rsid: string;
  transcript_id: string;
  transcript_biotype: string;
  canonical: string;
  exon: string;
  intron: string;
  hgvsc: string;
  hgvsp: string;
  protein_id: string;
  amino_acids: string;
  codons: string;
  transcript_options: TranscriptAnnotation[];
  clinical_significance: string;
  clinvar_conditions: string;
  gnomad_af: string;
  source_url: string;
};

type AnalysisResponse = {
  analysis_id: string;
  draft_answer: string;
  facts: {
    file_name: string;
    record_count: number;
    samples: string[];
    genome_build_guess: string | null;
    variant_types: Record<string, number>;
    genotype_counts: Record<string, number>;
    qc: {
      pass_rate: number | null;
      missing_gt_rate: number | null;
      multi_allelic_rate: number | null;
      symbolic_alt_rate: number | null;
      snv_fraction: number | null;
      indel_fraction: number | null;
      transition_transversion_ratio: number | null;
      het_hom_alt_ratio: number | null;
    };
  };
  annotations: VariantAnnotation[];
  roh_segments?: Array<{
    sample: string;
    contig: string;
    start_1based: number;
    end_1based: number;
    length_bp: number;
    marker_count: number;
    quality: number;
  }>;
  references: Array<{
    id: string;
    title: string;
    source: string;
    url: string;
    note: string;
  }>;
};

type ChatMessage = {
  role: "assistant" | "user";
  content: string;
  kind?: "status" | "summary";
};

type AnalysisQuestionTurn = {
  role: "user" | "assistant";
  content: string;
};

type StudioView =
  | "candidates"
  | "acmg"
  | "provenance"
  | "coverage"
  | "symbolic"
  | "roh"
  | "qc"
  | "table"
  | "clinvar"
  | "vep"
  | "references"
  | "igv"
  | "annotations";

type RohStudioSegment = {
  label: string;
  count: number;
  spanMb: string;
  quality?: number;
  sample?: string;
};

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function formatPercent(value: number | null | undefined) {
  return value == null ? "n/a" : `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? "n/a" : value.toFixed(digits);
}

function AnnotationDetailCard({ item }: { item: VariantAnnotation }) {
  const [selectedTranscriptIndex, setSelectedTranscriptIndex] = useState(0);
  const transcript = item.transcript_options[selectedTranscriptIndex] ?? {
    transcript_id: item.transcript_id,
    transcript_biotype: item.transcript_biotype,
    canonical: item.canonical,
    exon: item.exon,
    intron: item.intron,
    hgvsc: item.hgvsc,
    hgvsp: item.hgvsp,
    protein_id: item.protein_id,
    amino_acids: item.amino_acids,
    codons: item.codons,
  };

  return (
    <article className="miniCard annotationDetailCard">
      <h3>
        {item.gene || "Unknown gene"} | {item.contig}:{item.pos_1based}
      </h3>
      <p>
        {item.ref}&gt;{item.alts.join(",")} | {item.consequence} | {item.rsid || "no-rsID"}
      </p>
      <p>
        Genotype: {item.genotype} | ClinVar: {item.clinical_significance} | gnomAD AF: {item.gnomad_af}
      </p>
      <p>Condition: {item.clinvar_conditions}</p>
      {item.transcript_options.length ? (
        <label className="field compactField">
          <span>Transcript</span>
          <select
            value={selectedTranscriptIndex}
            onChange={(event) => setSelectedTranscriptIndex(Number(event.target.value))}
          >
            {item.transcript_options.map((option, index) => (
              <option key={`${item.contig}-${item.pos_1based}-${option.transcript_id}-${index}`} value={index}>
                {option.transcript_id} | {option.transcript_biotype} | canonical {option.canonical}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <div className="annotationMetaGrid">
        <div className="factBox">
          <span>Transcript</span>
          <strong>{transcript.transcript_id}</strong>
        </div>
        <div className="factBox">
          <span>Biotype</span>
          <strong>{transcript.transcript_biotype}</strong>
        </div>
        <div className="factBox">
          <span>Exon / Intron</span>
          <strong>
            {transcript.exon} / {transcript.intron}
          </strong>
        </div>
        <div className="factBox">
          <span>Canonical</span>
          <strong>{transcript.canonical}</strong>
        </div>
      </div>
      <div className="annotationTextStack">
        <p>HGVSc: {transcript.hgvsc}</p>
        <p>HGVSp: {transcript.hgvsp}</p>
        <p>
          Protein: {transcript.protein_id} | AA: {transcript.amino_acids} | Codons: {transcript.codons}
        </p>
        <p>
          Source:{" "}
          <a href={item.source_url} target="_blank" rel="noreferrer">
            Open annotation reference
          </a>
        </p>
      </div>
    </article>
  );
}

function MarkdownAnswer({ content }: { content: string }) {
  return (
    <div className="markdownAnswer">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}

function summarizeLabel(value: string, fallback: string) {
  const trimmed = value.trim();
  if (!trimmed || trimmed === "." || trimmed === "not available") {
    return fallback;
  }
  return trimmed
    .split(/[;,]/)[0]
    .trim()
    .replace(/_/g, " ");
}

function MetricTile({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "good" | "warn";
}) {
  return (
    <article className={`resultMetricTile resultMetricTile-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function DistributionList({
  items,
  emptyLabel,
}: {
  items: Array<{ label: string; count: number }>;
  emptyLabel: string;
}) {
  const maxValue = items[0]?.count ?? 0;
  if (!items.length) {
    return <p className="emptyState">{emptyLabel}</p>;
  }

  return (
    <div className="distributionList">
      {items.map((item) => {
        const width = maxValue > 0 ? Math.max((item.count / maxValue) * 100, 6) : 0;
        return (
          <div key={item.label} className="distributionRow">
            <div className="distributionMeta">
              <span>{item.label}</span>
              <strong>{item.count}</strong>
            </div>
            <div className="distributionTrack">
              <div className="distributionFill" style={{ width: `${width}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function VariantTable({
  items,
  onSelect,
}: {
  items: VariantAnnotation[];
  onSelect: (item: VariantAnnotation) => void;
}) {
  if (!items.length) {
    return <p className="emptyState">No annotation is available for the current selection.</p>;
  }

  return (
    <div className="variantTableWrap">
      <table className="variantTable">
        <thead>
          <tr>
            <th>Locus</th>
            <th>Gene</th>
            <th>Consequence</th>
            <th>ClinVar</th>
            <th>gnomAD</th>
            <th>HGVS</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={`${item.contig}-${item.pos_1based}-${item.rsid}-${item.hgvsc}`}
              onClick={() => onSelect(item)}
              className="variantTableRow"
            >
              <td>
                {item.contig}:{item.pos_1based}
              </td>
              <td>{item.gene || "Unknown"}</td>
              <td>{summarizeLabel(item.consequence, "Unclassified")}</td>
              <td>{summarizeLabel(item.clinical_significance, "Unreviewed")}</td>
              <td>{item.gnomad_af || "n/a"}</td>
              <td>{item.hgvsp !== "." ? item.hgvsp : item.hgvsc}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function rankCandidateScore(item: VariantAnnotation) {
  let score = 0;
  const significance = item.clinical_significance.toLowerCase();
  const consequence = item.consequence.toLowerCase();
  const afText = (item.gnomad_af || "").trim();
  const af = Number(afText);

  if (significance.includes("pathogenic")) {
    score += 5;
  } else if (significance.includes("vus")) {
    score += 2;
  } else if (significance.includes("benign")) {
    score -= 2;
  }

  if (consequence.includes("splice")) {
    score += 4;
  } else if (consequence.includes("missense")) {
    score += 3;
  } else if (consequence.includes("stop") || consequence.includes("frameshift")) {
    score += 5;
  } else if (consequence.includes("synonymous")) {
    score -= 1;
  }

  if (!Number.isNaN(af)) {
    if (af < 0.001) {
      score += 3;
    } else if (af < 0.01) {
      score += 2;
    } else if (af > 0.05) {
      score -= 2;
    }
  }

  if (item.genotype === "1/1") {
    score += 1;
  }

  return score;
}

function isVariantInRoh(
  item: VariantAnnotation,
  rohSegments:
    | Array<{
        sample: string;
        contig: string;
        start_1based: number;
        end_1based: number;
      }>
    | undefined,
) {
  if (!rohSegments?.length) {
    return false;
  }
  return rohSegments.some(
    (segment) =>
      segment.contig === item.contig &&
      item.pos_1based >= segment.start_1based &&
      item.pos_1based <= segment.end_1based,
  );
}

function rankRecessiveScore(
  item: VariantAnnotation,
  rohSegments:
    | Array<{
        sample: string;
        contig: string;
        start_1based: number;
        end_1based: number;
      }>
    | undefined,
) {
  let score = 0;
  const consequence = item.consequence.toLowerCase();
  const significance = item.clinical_significance.toLowerCase();
  const af = Number((item.gnomad_af || "").trim());

  if (item.genotype === "1/1") {
    score += 4;
  }
  if (isVariantInRoh(item, rohSegments)) {
    score += 5;
  }
  if (consequence.includes("splice")) {
    score += 4;
  } else if (consequence.includes("missense")) {
    score += 3;
  } else if (consequence.includes("stop") || consequence.includes("frameshift")) {
    score += 5;
  } else if (consequence.includes("synonymous")) {
    score -= 2;
  }
  if (!Number.isNaN(af)) {
    if (af < 0.001) {
      score += 4;
    } else if (af < 0.01) {
      score += 2;
    } else if (af > 0.05) {
      score -= 3;
    }
  }
  if (significance.includes("pathogenic")) {
    score += 3;
  } else if (significance.includes("benign")) {
    score -= 3;
  }
  return score;
}

function buildAcmgHints(item: VariantAnnotation) {
  const hints: string[] = [];
  const significance = item.clinical_significance.toLowerCase();
  const consequence = item.consequence.toLowerCase();
  const af = Number((item.gnomad_af || "").trim());

  if (consequence.includes("splice")) {
    hints.push("PVS1-supporting candidate: splice consequence is present and may affect transcript processing.");
  }
  if (consequence.includes("missense")) {
    hints.push("PP3-style review candidate: missense consequence may warrant in-silico evidence review.");
  }
  if (!Number.isNaN(af) && af < 0.001) {
    hints.push("PM2-style review candidate: allele frequency appears very low in gnomAD.");
  }
  if (significance.includes("pathogenic")) {
    hints.push("ClinVar support: existing pathogenic-style assertion is present and should be reviewed for evidence level.");
  }
  if (significance.includes("benign")) {
    hints.push("Benign evidence note: ClinVar currently trends benign, so pathogenic interpretation is less likely.");
  }
  if (!hints.length) {
    hints.push("No strong ACMG-style hint is available from the current fields alone. Additional transcript, phenotype, and segregation review is needed.");
  }
  return hints;
}

function hasMeaningfulText(value: string) {
  const trimmed = value.trim();
  return Boolean(trimmed && trimmed !== "." && trimmed.toLowerCase() !== "not available");
}

export default function Page() {
  const [apiBase, setApiBase] = useState("http://127.0.0.1:8001");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "VCF 파일을 + 버튼으로 첨부하면 제가 annotation scope와 range(limit)를 확인한 뒤 분석을 진행합니다. 별도 지시가 없으면 representative로 시작합니다.",
    },
  ]);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [annotationScope, setAnnotationScope] = useState<"representative" | "all">("representative");
  const [annotationLimit, setAnnotationLimit] = useState("200");
  const [status, setStatus] = useState("Waiting for a VCF");
  const [error, setError] = useState<string | null>(null);
  const [selectedAnnotationIndex, setSelectedAnnotationIndex] = useState(0);
  const [annotationSearch, setAnnotationSearch] = useState("");
  const [optionsAsked, setOptionsAsked] = useState(false);
  const [preAnalysisPrompt, setPreAnalysisPrompt] = useState<string | null>(null);
  const [composerText, setComposerText] = useState("");
  const [isComposing, setIsComposing] = useState(false);
  const [analysisQa, setAnalysisQa] = useState<AnalysisQuestionTurn[]>([]);
  const [followUpAnswer, setFollowUpAnswer] = useState<string | null>(null);
  const [activeStudioView, setActiveStudioView] = useState<StudioView | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const studioCanvasRef = useRef<HTMLElement | null>(null);
  const chatStreamRef = useRef<HTMLDivElement | null>(null);

  function addMessage(message: ChatMessage) {
    setMessages((current) => [...current, message]);
  }

  function buildCitationMap(references: AnalysisResponse["references"]) {
    return new Map(references.map((item, index) => [item.id, index + 1]));
  }

  function formatSummaryWithCitations(text: string, references: AnalysisResponse["references"]) {
    const referenceMap = new Map(
      references.map((item, index) => [
        item.id,
        {
          index: index + 1,
          url: item.url,
          title: item.title,
        },
      ]),
    );

    return text.replace(/\[?(REF\d+)\]?/g, (match, refId: string) => {
      const reference = referenceMap.get(refId);
      if (!reference) {
        return match;
      }
      return `[${reference.index}](${reference.url} "${reference.title}")`;
    });
  }

  function handleAttachClick() {
    fileInputRef.current?.click();
  }

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    if (!file) {
      return;
    }
    setAttachedFile(file);
    setAnalysis(null);
    setFollowUpAnswer(null);
    setAnalysisQa([]);
    setActiveStudioView(null);
    setSelectedAnnotationIndex(0);
    setAnnotationSearch("");
    setOptionsAsked(true);
    setPreAnalysisPrompt("Please input VCF analysis scope and its range..");
    setError(null);
    setStatus("File attached");
    void requestWorkflowStart(file.name);
    event.target.value = "";
  }

  async function handleStartAnalysis(parsedScope?: "representative" | "all", parsedLimit?: string) {
    if (!attachedFile) {
      setError("먼저 + 버튼으로 VCF 파일을 첨부해 주세요.");
      return;
    }

    const effectiveScope = parsedScope ?? annotationScope;
    const effectiveLimit = parsedLimit ?? annotationLimit;
    setAnnotationScope(effectiveScope);
    setAnnotationLimit(effectiveLimit);
    setError(null);
    setStatus("Analyzing");
    addMessage({
      role: "assistant",
      content: "pysam으로 VCF header, sample, record count, 기본 QC를 읽고 있습니다.",
      kind: "status",
    });
    await sleep(350);
    addMessage({
      role: "assistant",
      content:
        "현재 run은 요약과 주석 중심이라 bcftools/GATK hard filtering는 적용하지 않고, 원본 VCF를 그대로 해석합니다. 필터 조건이 필요해지면 그 단계에서 bcftools filter 또는 GATK VariantFiltration을 호출하겠습니다.",
      kind: "status",
    });
    await sleep(350);
    addMessage({
      role: "assistant",
      content:
        "변이 주석은 Ensembl VEP REST로 consequence, transcript, HGVS, protein 정보를 붙이고, ClinVar/refsnp와 gnomAD를 기준으로 clinical significance와 allele frequency를 확인하고 있습니다.",
      kind: "status",
    });

    try {
      const formData = new FormData();
      formData.append("file", attachedFile);
      formData.append("annotation_scope", effectiveScope);
      if (effectiveScope === "all" && effectiveLimit.trim()) {
        formData.append("annotation_limit", effectiveLimit);
      }

      const response = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/analysis/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const payload: AnalysisResponse = await response.json();
      setAnalysis(payload);
      setFollowUpAnswer(null);
      setAnalysisQa([]);
      setActiveStudioView(null);
      setSelectedAnnotationIndex(0);
      setOptionsAsked(false);
      setComposerText("");
      setStatus("Grounded summary ready");
      addMessage({
        role: "assistant",
        content:
          "분석이 끝났습니다. 아래에 grounded summary와 references를 정리해두었고, 맨 아래 IGV에서 같은 annotation을 바로 확인할 수 있습니다.",
        kind: "summary",
      });
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : String(caught);
      setError(message);
      setStatus("Analysis failed");
      addMessage({
        role: "assistant",
        content: `분석 중 오류가 발생했습니다: ${message}`,
      });
    }
  }

  async function handleComposerSubmit() {
    const text = composerText.trim();
    if (!text) {
      return;
    }

    if (!attachedFile) {
      addMessage({ role: "user", content: text });
      addMessage({
        role: "assistant",
        content: "먼저 + 버튼으로 VCF 파일을 첨부해 주세요.",
      });
      setComposerText("");
      return;
    }

    if (optionsAsked) {
      addMessage({ role: "user", content: text });
      setComposerText("");
      await requestWorkflowReply(text);
      return;
    }

    if (analysis) {
      setComposerText("");
      await handleAskAnalysisQuestion(text);
      return;
    }

    addMessage({ role: "user", content: text });
    addMessage({
      role: "assistant",
      content: "먼저 VCF를 첨부하거나 업로드 후 옵션을 답해 주세요.",
    });
    setComposerText("");
  }

  async function requestWorkflowStart(fileName: string) {
    try {
      const response = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/workflow/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_name: fileName }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const payload = await response.json();
      addMessage({
        role: "assistant",
        content: `${payload.assistant_message} (workflow model: ${payload.model})`,
        kind: "status",
      });
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : String(caught);
      addMessage({
        role: "assistant",
        content:
          `GPT workflow intake 호출에 실패했습니다: ${message}. ` +
          "예: `all로 200개`, `representative로 진행`처럼 답해 주세요.",
        kind: "status",
      });
    }
  }

  async function requestWorkflowReply(message: string) {
    if (!attachedFile) {
      return;
    }
    setStatus("Parsing scope and range...");
    try {
      const response = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/workflow/reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_name: attachedFile.name, message }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const payload = await response.json();
      setStatus(payload.should_start_analysis ? "Preparing analysis..." : "Scope received");
      addMessage({
        role: "assistant",
        content: `${payload.assistant_message} (workflow model: ${payload.model})`,
        kind: "status",
      });
      if (payload.should_start_analysis) {
        await handleStartAnalysis(
          payload.parsed_scope,
          payload.parsed_limit != null ? String(payload.parsed_limit) : annotationLimit,
        );
      }
    } catch (caught) {
      const msg = caught instanceof Error ? caught.message : String(caught);
      addMessage({
        role: "assistant",
        content:
          `GPT workflow option parsing에 실패했습니다: ${msg}. ` +
          "예: `all로 200개`, `representative로 진행`처럼 다시 입력해 주세요.",
      });
    }
  }

  async function handleAskAnalysisQuestion(questionText?: string) {
    const text = questionText?.trim() ?? "";
    if (!text || !analysis) {
      return;
    }

    setStatus("Generating answer...");
    setAnalysisQa((current) => [...current, { role: "user", content: text }]);

    try {
      const response = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/chat/analysis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text,
          analysis,
          history: analysisQa.map((turn) => ({ role: turn.role, content: turn.content })),
          studio_context: studioContext,
        }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const payload = await response.json();
      setAnalysisQa((current) => [...current, { role: "assistant", content: payload.answer }]);
      setFollowUpAnswer(payload.answer);
      setStatus("Answer ready");
    } catch (caught) {
      const msg = caught instanceof Error ? caught.message : String(caught);
      setAnalysisQa((current) => [
        ...current,
        { role: "assistant", content: `설명 요청 중 오류가 발생했습니다: ${msg}` },
      ]);
      setStatus("Answer failed");
    }
  }

  const searchedAnnotations = useMemo(() => {
    const query = annotationSearch.trim().toLowerCase();
    if (!analysis) {
      return [];
    }
    if (!query) {
      return analysis.annotations;
    }
    return analysis.annotations.filter((item) =>
      [item.gene, item.consequence, item.clinical_significance, item.clinvar_conditions, item.rsid]
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }, [analysis, annotationSearch]);

  const safeSelectedIndex =
    searchedAnnotations.length === 0
      ? 0
      : Math.min(selectedAnnotationIndex, searchedAnnotations.length - 1);
  const selectedAnnotation = searchedAnnotations[safeSelectedIndex] ?? searchedAnnotations[0] ?? null;
  const summaryText = analysis ? formatSummaryWithCitations(analysis.draft_answer, analysis.references) : null;
  const displayedAnswer = followUpAnswer ?? summaryText;
  const hasInteractiveState = Boolean(attachedFile || analysis || messages.length > 1);
  const latestStatusMessage =
    [...messages].reverse().find((message) => message.kind === "status" || message.kind === "summary")?.content ?? "";
  const sourceStatusDetail = useMemo(() => {
    if (status === "Generating answer...") {
      return "ChatGenome is reading the current analysis and Studio results to prepare a grounded response.";
    }
    if (status === "Parsing scope and range...") {
      return "ChatGenome is interpreting your scope and range reply before launching the analysis.";
    }
    if (status === "Preparing analysis...") {
      return "The workflow reply was accepted. ChatGenome is now preparing the grounded VCF analysis run.";
    }
    if (status === "Scope received") {
      return "The scope and range were understood. If analysis does not start automatically, refine the instruction in chat.";
    }
    if (status === "Analyzing") {
      return "Reading the VCF, attaching deterministic annotation, and preparing grounded outputs.";
    }
    if (status === "File attached") {
      return "The VCF is attached. Reply in chat with the analysis scope and range.";
    }
    if (status === "Awaiting scope and range") {
      return "The file is attached. Reply in chat with scope/range, or leave it broad and representative mode will be used.";
    }
    if (status === "Answer ready") {
      return "The latest answer is ready in Chat and grounded against the current analysis context.";
    }
    if (status === "Grounded summary ready") {
      return "The initial grounded summary is ready. You can continue asking questions about any Studio result.";
    }
    if (status === "Answer failed") {
      return "The last chat response failed. Retry the question and ChatGenome will attempt the grounded explanation again.";
    }
    return latestStatusMessage;
  }, [latestStatusMessage, status]);
  const chatHeaderStatus =
    status === "Generating answer..." ||
    status === "Parsing scope and range..." ||
    status === "Preparing analysis..." ||
    status === "Analyzing" ||
    status === "File attached" ||
    status === "Scope received" ||
    status === "Awaiting scope and range" ||
    status === "Answer failed"
      ? status
      : analysis
        ? "Analysis ready"
        : status;
  const chatTurns = [
    ...(preAnalysisPrompt
      ? [
          {
            role: "assistant" as const,
            content: preAnalysisPrompt,
          },
        ]
      : []),
    ...messages
      .filter((message) => message.role === "user")
      .map((message) => ({ role: message.role, content: message.content })),
    ...(analysis
      ? [
          {
            role: "assistant" as const,
            content:
              summaryText ??
              "분석이 완료되면 grounded summary가 여기에 표시됩니다.",
          },
        ]
      : []),
    ...analysisQa,
  ];
  const qcMetrics = analysis?.facts.qc ?? null;
  const clinvarCounts = useMemo(() => {
    if (!analysis) {
      return [];
    }
    const counts = new Map<string, number>();
    analysis.annotations.forEach((item) => {
      const key = summarizeLabel(item.clinical_significance, "Unreviewed");
      counts.set(key, (counts.get(key) ?? 0) + 1);
    });
    return [...counts.entries()]
      .map(([label, count]) => ({ label, count }))
      .sort((left, right) => right.count - left.count);
  }, [analysis]);
  const consequenceCounts = useMemo(() => {
    if (!analysis) {
      return [];
    }
    const counts = new Map<string, number>();
    analysis.annotations.forEach((item) => {
      const key = summarizeLabel(item.consequence, "Unclassified");
      counts.set(key, (counts.get(key) ?? 0) + 1);
    });
    return [...counts.entries()]
      .map(([label, count]) => ({ label, count }))
      .sort((left, right) => right.count - left.count)
      .slice(0, 10);
  }, [analysis]);
  const geneCounts = useMemo(() => {
    if (!analysis) {
      return [];
    }
    const counts = new Map<string, number>();
    analysis.annotations.forEach((item) => {
      const key = item.gene?.trim() || "Unknown";
      counts.set(key, (counts.get(key) ?? 0) + 1);
    });
    return [...counts.entries()]
      .map(([label, count]) => ({ label, count }))
      .sort((left, right) => right.count - left.count)
      .slice(0, 8);
  }, [analysis]);
  const candidateVariants = useMemo(() => {
    if (!analysis) {
      return [];
    }
    return [...analysis.annotations]
      .map((item) => {
        const rohBoost = isVariantInRoh(item, analysis.roh_segments) ? 3 : 0;
        const homAltBoost = item.genotype === "1/1" ? 1 : 0;
        return {
          item,
          score: rankCandidateScore(item) + rohBoost + homAltBoost,
          inRoh: isVariantInRoh(item, analysis.roh_segments),
        };
      })
      .sort((left, right) => right.score - left.score)
      .slice(0, 8);
  }, [analysis]);
  const clinicalCoverage = useMemo(() => {
    if (!analysis || analysis.annotations.length === 0) {
      return [];
    }
    const total = analysis.annotations.length;
    const ratio = (count: number) => `${Math.round((count / total) * 100)}%`;
    const clinvarCount = analysis.annotations.filter(
      (item) => hasMeaningfulText(item.clinical_significance) || hasMeaningfulText(item.clinvar_conditions),
    ).length;
    const gnomadCount = analysis.annotations.filter((item) => hasMeaningfulText(item.gnomad_af)).length;
    const geneCount = analysis.annotations.filter((item) => hasMeaningfulText(item.gene)).length;
    const hgvsCount = analysis.annotations.filter(
      (item) => hasMeaningfulText(item.hgvsc) || hasMeaningfulText(item.hgvsp),
    ).length;
    const proteinCount = analysis.annotations.filter((item) => hasMeaningfulText(item.hgvsp)).length;
    return [
      { label: "ClinVar coverage", count: clinvarCount, detail: `${clinvarCount}/${total} annotated (${ratio(clinvarCount)})` },
      { label: "gnomAD coverage", count: gnomadCount, detail: `${gnomadCount}/${total} annotated (${ratio(gnomadCount)})` },
      { label: "Gene mapping", count: geneCount, detail: `${geneCount}/${total} annotated (${ratio(geneCount)})` },
      { label: "HGVS coverage", count: hgvsCount, detail: `${hgvsCount}/${total} annotated (${ratio(hgvsCount)})` },
      { label: "Protein change", count: proteinCount, detail: `${proteinCount}/${total} annotated (${ratio(proteinCount)})` },
    ];
  }, [analysis]);
  const symbolicAnnotations = useMemo(() => {
    if (!analysis) {
      return [];
    }
    return analysis.annotations.filter((item) => item.alts.some((alt) => alt.startsWith("<") && alt.endsWith(">")));
  }, [analysis]);
  const rohCandidates = useMemo(() => {
    if (!analysis) {
      return { items: [] as VariantAnnotation[], segments: [] as RohStudioSegment[] };
    }
    const homAlt = [...analysis.annotations]
      .filter((item) => item.genotype === "1/1")
      .sort((left, right) =>
        left.contig === right.contig ? left.pos_1based - right.pos_1based : left.contig.localeCompare(right.contig),
      );

    const segments: RohStudioSegment[] = [];
    let start = homAlt[0];
    let previous = homAlt[0];
    let count = homAlt[0] ? 1 : 0;
    for (let index = 1; index < homAlt.length; index += 1) {
      const current = homAlt[index];
      const sameContig = current.contig === previous.contig;
      const closeEnough = current.pos_1based - previous.pos_1based <= 2_000_000;
      if (sameContig && closeEnough) {
        count += 1;
        previous = current;
        continue;
      }
      if (start && previous && count >= 2) {
        segments.push({
          label: `${start.contig}:${start.pos_1based}-${previous.pos_1based}`,
          count,
          spanMb: `${((previous.pos_1based - start.pos_1based) / 1_000_000).toFixed(2)} Mb`,
        });
      }
      start = current;
      previous = current;
      count = 1;
    }
    if (start && previous && count >= 2) {
      segments.push({
        label: `${start.contig}:${start.pos_1based}-${previous.pos_1based}`,
        count,
        spanMb: `${((previous.pos_1based - start.pos_1based) / 1_000_000).toFixed(2)} Mb`,
      });
    }
    const actualSegments: RohStudioSegment[] = (analysis.roh_segments ?? []).map((segment) => ({
      label: `${segment.contig}:${segment.start_1based}-${segment.end_1based}`,
      count: segment.marker_count,
      spanMb: `${(segment.length_bp / 1_000_000).toFixed(2)} Mb`,
      quality: segment.quality,
      sample: segment.sample,
    }));
    return { items: homAlt.slice(0, 8), segments: actualSegments.length ? actualSegments : segments.slice(0, 6) };
  }, [analysis]);
  const recessiveShortlist = useMemo(() => {
    if (!analysis) {
      return [];
    }
    return [...analysis.annotations]
      .filter((item) => item.genotype === "1/1" || isVariantInRoh(item, analysis.roh_segments))
      .map((item) => ({
        item,
        score: rankRecessiveScore(item, analysis.roh_segments),
        inRoh: isVariantInRoh(item, analysis.roh_segments),
      }))
      .sort((left, right) => right.score - left.score)
      .slice(0, 8);
  }, [analysis]);
  const studioCards: Array<{ id: StudioView; title: string; subtitle: string }> = [
    { id: "provenance", title: "Workflow Setup", subtitle: "Tools, scope, and run policy" },
    { id: "qc", title: "QC Summary", subtitle: "PASS, Ti/Tv, GT quality" },
    { id: "coverage", title: "Clinical Coverage", subtitle: "Annotation completeness view" },
    { id: "table", title: "Filtering View", subtitle: "Searchable variant triage" },
    { id: "symbolic", title: "Symbolic ALT Review", subtitle: "Structural-style records split out" },
    { id: "roh", title: "ROH / Recessive", subtitle: "Hom-alt and ROH-style review" },
    { id: "candidates", title: "Candidate Variants", subtitle: "Ranked review shortlist" },
    { id: "vep", title: "VEP Consequence", subtitle: "Consequence and gene burden" },
    { id: "clinvar", title: "ClinVar Review", subtitle: "Clinical significance mix" },
    { id: "annotations", title: "Annotation Cards", subtitle: "Variant detail cards" },
    { id: "igv", title: "IGV Plot", subtitle: "Locus visualization" },
    { id: "acmg", title: "ACMG Review", subtitle: "Evidence hints, not final calls" },
    { id: "references", title: "References", subtitle: "Linked evidence" },
  ];
  const studioContext = useMemo(() => {
    if (!analysis) {
      return {};
    }
    return {
      active_view: activeStudioView,
      qc_summary: {
        pass_rate: qcMetrics?.pass_rate,
        ti_tv: qcMetrics?.transition_transversion_ratio,
        missing_gt_rate: qcMetrics?.missing_gt_rate,
        het_hom_alt_ratio: qcMetrics?.het_hom_alt_ratio,
      },
      clinical_coverage: clinicalCoverage.slice(0, 5),
      symbolic_alt_review: {
        count: symbolicAnnotations.length,
        examples: symbolicAnnotations.slice(0, 5).map((item) => ({
          locus: `${item.contig}:${item.pos_1based}`,
          gene: item.gene,
          alts: item.alts,
          consequence: item.consequence,
          genotype: item.genotype,
        })),
      },
      roh_review: {
        segment_count: analysis.roh_segments?.length ?? 0,
        segments: (analysis.roh_segments ?? []).slice(0, 5).map((segment) => ({
          sample: segment.sample,
          contig: segment.contig,
          start_1based: segment.start_1based,
          end_1based: segment.end_1based,
          length_bp: segment.length_bp,
          marker_count: segment.marker_count,
          quality: segment.quality,
        })),
        recessive_shortlist: recessiveShortlist.slice(0, 6).map(({ item, score, inRoh }) => ({
          locus: `${item.contig}:${item.pos_1based}`,
          gene: item.gene,
          rsid: item.rsid,
          consequence: item.consequence,
          genotype: item.genotype,
          gnomad_af: item.gnomad_af,
          score,
          in_roh: inRoh,
        })),
      },
      candidate_variants: candidateVariants.slice(0, 6).map(({ item, score, inRoh }) => ({
        locus: `${item.contig}:${item.pos_1based}`,
        gene: item.gene,
        rsid: item.rsid,
        consequence: item.consequence,
        clinical_significance: item.clinical_significance,
        gnomad_af: item.gnomad_af,
        score,
        in_roh: inRoh,
      })),
      clinvar_review: clinvarCounts.slice(0, 8),
      vep_consequence: consequenceCounts.slice(0, 10),
      selected_annotation: selectedAnnotation
        ? {
            locus: `${selectedAnnotation.contig}:${selectedAnnotation.pos_1based}`,
            gene: selectedAnnotation.gene,
            rsid: selectedAnnotation.rsid,
            consequence: selectedAnnotation.consequence,
            clinical_significance: selectedAnnotation.clinical_significance,
            gnomad_af: selectedAnnotation.gnomad_af,
            hgvsc: selectedAnnotation.hgvsc,
            hgvsp: selectedAnnotation.hgvsp,
          }
        : null,
    };
  }, [
    activeStudioView,
    analysis,
    candidateVariants,
    clinicalCoverage,
    clinvarCounts,
    consequenceCounts,
    qcMetrics,
    recessiveShortlist,
    selectedAnnotation,
    symbolicAnnotations,
  ]);

  function openStudioView(view: StudioView) {
    setActiveStudioView(view);
    window.setTimeout(() => {
      studioCanvasRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
  }

  useEffect(() => {
    const node = chatStreamRef.current;
    if (!node) {
      return;
    }
    node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [chatTurns.length]);

  return (
    <main className="shell notebookShell">
      <header className="appTopbar">
        <div className="appBrand">
          <img src="/chatgenome-dna.svg" alt="" className="appBrandIconImage" />
          <span className="appBrandName">ChatGenome</span>
        </div>
        <div className="appCopyright">Copyright 2026. BISPL@KAIST AI, All rights reserved.</div>
      </header>
      <div className="notebookGrid">
        <aside className="notebookPanel sourcePanel">
          <div className="notebookHeader">
            <h2>Sources</h2>
          </div>
          <div className="sourcePanelBody">
            <button type="button" className="sourceAddButton" onClick={handleAttachClick}>
              + Add VCF source
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".vcf,.gz,.vcf.gz"
              onChange={handleFileChange}
              className="hiddenInput"
            />
            <label className="field">
              <span>API base URL</span>
              <input value={apiBase} onChange={(event) => setApiBase(event.target.value)} />
            </label>
            <div className="sourceList">
              {attachedFile ? (
                <article className="sourceItem sourceItemActive">
                  <div>
                    <strong>{attachedFile.name}</strong>
                    <p>Active VCF source</p>
                  </div>
                  <span className="sourceBadge">1</span>
                </article>
              ) : (
                <div className="sourceEmpty">
                  <p>Attach a VCF or VCF.gz file to start analysis.</p>
                </div>
              )}
            </div>
            <div className="sourceMeta">
              <span>Status</span>
              <strong>{status}</strong>
            </div>
            {sourceStatusDetail ? <p className="sourceHint">{sourceStatusDetail}</p> : null}
            {error ? <p className="errorText">{error}</p> : null}
          </div>
        </aside>

        <section className="notebookPanel chatPanel">
          <div className="notebookHeader">
            <h2>Chat</h2>
            <span className="pill">{chatHeaderStatus}</span>
          </div>
          <div className="chatPanelBody">
            <div ref={chatStreamRef} className="chatStream">
              {chatTurns.length ? (
                chatTurns.map((turn, index) => (
                  <article
                    key={`chat-turn-${index}`}
                    className={turn.role === "user" ? "nbUserPrompt" : "nbAssistantAnswer"}
                  >
                    {turn.role === "user" ? (
                      <p className="summaryText nbAnswerText">{turn.content}</p>
                    ) : (
                      <MarkdownAnswer content={turn.content} />
                    )}
                  </article>
                ))
              ) : (
                <div className="chatEmptyState">
                  <h3>Start with one VCF</h3>
                  <p>Upload a VCF on the left, then continue the workflow in this chat.</p>
                </div>
              )}
            </div>

            <div className="chatComposerDock">
              <input
                value={composerText}
                onChange={(event) => setComposerText(event.target.value)}
                onCompositionStart={() => setIsComposing(true)}
                onCompositionEnd={() => setIsComposing(false)}
                placeholder={
                  attachedFile
                    ? optionsAsked
                      ? "예: all로 200개, 비워두면 representative"
                      : "Start typing a follow-up question..."
                    : "Upload a VCF first"
                }
                onKeyDown={(event) => {
                  if (isComposing || event.nativeEvent.isComposing) {
                    return;
                  }
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void handleComposerSubmit();
                  }
                }}
              />
              <button type="button" className="chatSendButton" onClick={() => void handleComposerSubmit()}>
                →
              </button>
            </div>
          </div>
        </section>

        <aside className="notebookPanel studioPanel">
          <div className="notebookHeader">
            <h2>Studio</h2>
          </div>
          <div className="studioPanelBody">
            <div className="studioGrid">
              {studioCards.map((card) => (
                <button
                  type="button"
                  key={card.id}
                  className={`studioCard ${activeStudioView === card.id ? "studioCardActive" : ""}`}
                  onClick={() => openStudioView(card.id)}
                  disabled={!analysis}
                >
                  <strong>{card.title}</strong>
                  <span>{card.subtitle}</span>
                </button>
              ))}
            </div>
            <div className="studioHint">
              {analysis ? "Choose a card to open a result view." : "Studio cards will activate after the analysis finishes."}
            </div>
          </div>
        </aside>
      </div>

      {analysis && activeStudioView ? (
        <section ref={studioCanvasRef} className="studioCanvas">
          {activeStudioView === "candidates" ? (
            <section className="notebookPanel studioCanvasPanel">
              <div className="notebookHeader">
                <h2>Candidate Variants</h2>
              </div>
              <div className="studioCanvasBody">
                <div className="resultList">
                  {candidateVariants.map(({ item, score, inRoh }) => (
                    <button
                      type="button"
                      key={`${item.contig}-${item.pos_1based}-${item.rsid}-candidate`}
                      className="resultListItem"
                      onClick={() => {
                        const nextIndex = searchedAnnotations.findIndex(
                          (candidate) =>
                            candidate.contig === item.contig &&
                            candidate.pos_1based === item.pos_1based &&
                            candidate.rsid === item.rsid,
                        );
                        setSelectedAnnotationIndex(nextIndex >= 0 ? nextIndex : 0);
                        setActiveStudioView("annotations");
                      }}
                    >
                      <strong>
                        {item.gene || "Unknown"} | {item.contig}:{item.pos_1based}
                      </strong>
                      <span>
                        Score {score} | {summarizeLabel(item.consequence, "Unclassified")} |{" "}
                        {summarizeLabel(item.clinical_significance, "Unreviewed")}
                        {inRoh ? " | inside ROH" : ""}
                        {" | "}gnomAD {item.gnomad_af || "n/a"}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </section>
          ) : null}

          {activeStudioView === "acmg" ? (
            <section className="notebookPanel studioCanvasPanel">
              <div className="notebookHeader">
                <h2>ACMG Review</h2>
              </div>
              <div className="studioCanvasBody">
                <p className="emptyState acmgNote">
                  This is a triage view with ACMG-style evidence hints. It is not a final clinical classification.
                </p>
                <div className="resultList">
                  {candidateVariants.slice(0, 6).map(({ item }) => (
                    <article
                      key={`${item.contig}-${item.pos_1based}-${item.rsid}-acmg`}
                      className="resultListItem resultListStatic"
                    >
                      <strong>
                        {item.gene || "Unknown"} | {item.rsid || `${item.contig}:${item.pos_1based}`}
                      </strong>
                      <span>
                        {summarizeLabel(item.consequence, "Unclassified")} |{" "}
                        {summarizeLabel(item.clinical_significance, "Unreviewed")}
                      </span>
                      <ul className="hintList">
                        {buildAcmgHints(item).map((hint) => (
                          <li key={hint}>{hint}</li>
                        ))}
                      </ul>
                    </article>
                  ))}
                </div>
              </div>
            </section>
          ) : null}

          {activeStudioView === "provenance" ? (
            <section className="notebookPanel studioCanvasPanel">
              <div className="notebookHeader">
                <h2>Analysis Provenance</h2>
              </div>
              <div className="studioCanvasBody">
                <div className="resultMetricGrid">
                  <MetricTile label="Annotation scope" value={annotationScope} />
                  <MetricTile label="Annotation limit" value={annotationScope === "all" ? annotationLimit || "n/a" : "representative"} />
                  <MetricTile label="References" value={String(analysis.references.length)} />
                  <MetricTile label="Annotations" value={String(analysis.annotations.length)} />
                </div>
                <div className="resultSectionSplit">
                  <article className="miniCard">
                    <h3>Tool chain</h3>
                    <ul className="hintList">
                      <li>`pysam` for VCF parsing, file summary, and QC metrics</li>
                      <li>`Ensembl VEP REST` for consequence, transcript, HGVS, and protein fields</li>
                      <li>`ClinVar / NCBI refsnp` for clinical significance and condition labels</li>
                      <li>`gnomAD` frequency joins for population rarity context</li>
                      <li>`OpenAI` models for workflow intake and grounded narrative explanation</li>
                    </ul>
                  </article>
                  <article className="miniCard">
                    <h3>Current run policy</h3>
                    <ul className="hintList">
                      <li>Filtering tools such as `bcftools` and `GATK` are available but were not automatically applied in this summary-first run.</li>
                      <li>Representative annotation is the default unless the user explicitly requests a wider range.</li>
                      <li>Studio cards are derived from the current annotated subset, not from a separate hidden analysis branch.</li>
                    </ul>
                  </article>
                </div>
              </div>
            </section>
          ) : null}

          {activeStudioView === "qc" ? (
            <section className="notebookPanel studioCanvasPanel">
              <div className="notebookHeader">
                <h2>QC Summary</h2>
              </div>
              <div className="studioCanvasBody">
                <div className="resultMetricGrid">
                  <MetricTile label="PASS rate" value={formatPercent(qcMetrics?.pass_rate)} tone="good" />
                  <MetricTile
                    label="Ti/Tv"
                    value={formatNumber(qcMetrics?.transition_transversion_ratio)}
                    tone="neutral"
                  />
                  <MetricTile
                    label="Missing GT"
                    value={formatPercent(qcMetrics?.missing_gt_rate)}
                    tone="warn"
                  />
                  <MetricTile
                    label="Het/HomAlt"
                    value={formatNumber(qcMetrics?.het_hom_alt_ratio)}
                    tone="neutral"
                  />
                  <MetricTile
                    label="Multi-allelic"
                    value={formatPercent(qcMetrics?.multi_allelic_rate)}
                    tone="neutral"
                  />
                  <MetricTile
                    label="Symbolic ALT"
                    value={formatPercent(qcMetrics?.symbolic_alt_rate)}
                    tone="neutral"
                  />
                  <MetricTile label="SNV fraction" value={formatPercent(qcMetrics?.snv_fraction)} tone="good" />
                  <MetricTile label="Indel fraction" value={formatPercent(qcMetrics?.indel_fraction)} tone="neutral" />
                </div>
                <div className="resultSectionSplit">
                  <article className="miniCard">
                    <h3>Genotype composition</h3>
                    <DistributionList
                      items={Object.entries(analysis.facts.genotype_counts)
                        .map(([label, count]) => ({ label, count }))
                        .sort((left, right) => right.count - left.count)}
                      emptyLabel="No genotype counts are available."
                    />
                  </article>
                  <article className="miniCard">
                    <h3>Variant classes</h3>
                    <DistributionList
                      items={Object.entries(analysis.facts.variant_types)
                        .map(([label, count]) => ({ label, count }))
                        .sort((left, right) => right.count - left.count)}
                      emptyLabel="No variant class counts are available."
                    />
                  </article>
                </div>
              </div>
            </section>
          ) : null}

          {activeStudioView === "coverage" ? (
            <section className="notebookPanel studioCanvasPanel">
              <div className="notebookHeader">
                <h2>Clinical Annotation Coverage</h2>
              </div>
              <div className="studioCanvasBody">
                <div className="resultList">
                  {clinicalCoverage.map((item) => (
                    <article key={item.label} className="resultListItem resultListStatic">
                      <strong>{item.label}</strong>
                      <span>{item.detail}</span>
                    </article>
                  ))}
                </div>
              </div>
            </section>
          ) : null}

          {activeStudioView === "table" ? (
            <section className="notebookPanel studioCanvasPanel">
              <div className="notebookHeader">
                <h2>Variant Table</h2>
                <span className="pill">{searchedAnnotations.length} rows</span>
              </div>
              <div className="studioCanvasBody">
                <div className="oeAnnotationControls">
                  <label className="field">
                    <span>Search gene / consequence / ClinVar</span>
                    <input
                      value={annotationSearch}
                      onChange={(event) => {
                        setAnnotationSearch(event.target.value);
                        setSelectedAnnotationIndex(0);
                      }}
                      placeholder="e.g. PALMD, missense_variant, benign"
                    />
                  </label>
                </div>
                <VariantTable
                  items={searchedAnnotations}
                  onSelect={(item) => {
                    const nextIndex = searchedAnnotations.findIndex(
                      (candidate) =>
                        candidate.contig === item.contig &&
                        candidate.pos_1based === item.pos_1based &&
                        candidate.rsid === item.rsid,
                    );
                    setSelectedAnnotationIndex(nextIndex >= 0 ? nextIndex : 0);
                    setActiveStudioView("annotations");
                  }}
                />
              </div>
            </section>
          ) : null}

          {activeStudioView === "symbolic" ? (
            <section className="notebookPanel studioCanvasPanel">
              <div className="notebookHeader">
                <h2>Symbolic ALT Review</h2>
              </div>
              <div className="studioCanvasBody">
                <p className="emptyState acmgNote">
                  Symbolic ALT records are separated here so they are not over-interpreted as ordinary SNV/indel calls.
                </p>
                {symbolicAnnotations.length ? (
                  <div className="resultList">
                    {symbolicAnnotations.map((item) => (
                      <button
                        type="button"
                        key={`${item.contig}-${item.pos_1based}-${item.rsid}-symbolic`}
                        className="resultListItem"
                        onClick={() => {
                          const nextIndex = searchedAnnotations.findIndex(
                            (candidate) =>
                              candidate.contig === item.contig &&
                              candidate.pos_1based === item.pos_1based &&
                              candidate.rsid === item.rsid,
                          );
                          setSelectedAnnotationIndex(nextIndex >= 0 ? nextIndex : 0);
                          setActiveStudioView("annotations");
                        }}
                      >
                        <strong>
                          {item.contig}:{item.pos_1based} | {item.gene || "Unknown"} | {item.alts.join(",")}
                        </strong>
                        <span>
                          {summarizeLabel(item.consequence, "Unclassified")} | genotype {item.genotype}
                        </span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="emptyState">No symbolic ALT records are present in the current annotated subset.</p>
                )}
              </div>
            </section>
          ) : null}

          {activeStudioView === "roh" ? (
            <section className="notebookPanel studioCanvasPanel">
              <div className="notebookHeader">
                <h2>ROH / Recessive Review</h2>
              </div>
              <div className="studioCanvasBody">
                <p className="emptyState acmgNote">
                  This is a homozygous-alt review and ROH-style heuristic from the current annotated subset. A full
                  production workflow should add `bcftools roh` on the complete callset.
                </p>
                <div className="resultSectionSplit">
                  <article className="miniCard">
                    <h3>ROH-style segments</h3>
                    {rohCandidates.segments.length ? (
                      <div className="resultList">
                        {rohCandidates.segments.map((segment) => (
                          <article key={segment.label} className="resultListItem resultListStatic">
                            <strong>{segment.label}</strong>
                            <span>
                              {segment.count} markers | span {segment.spanMb}
                              {segment.quality != null ? ` | quality ${segment.quality.toFixed(1)}` : ""}
                              {segment.sample ? ` | ${segment.sample}` : ""}
                            </span>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="emptyState">No multi-site homozygous stretches were detected in the current subset.</p>
                    )}
                  </article>
                  <article className="miniCard">
                    <h3>Recessive-model candidates</h3>
                    {recessiveShortlist.length ? (
                      <div className="resultList">
                        {recessiveShortlist.map(({ item, score, inRoh }) => (
                          <button
                            type="button"
                            key={`${item.contig}-${item.pos_1based}-${item.rsid}-roh`}
                            className="resultListItem"
                            onClick={() => {
                              const nextIndex = searchedAnnotations.findIndex(
                                (candidate) =>
                                  candidate.contig === item.contig &&
                                  candidate.pos_1based === item.pos_1based &&
                                  candidate.rsid === item.rsid,
                              );
                              setSelectedAnnotationIndex(nextIndex >= 0 ? nextIndex : 0);
                              setActiveStudioView("annotations");
                            }}
                          >
                            <strong>
                              {item.gene || "Unknown"} | {item.contig}:{item.pos_1based}
                            </strong>
                            <span>
                              score {score} | genotype {item.genotype}
                              {inRoh ? " | inside ROH" : ""}
                              {" | "}
                              {summarizeLabel(item.consequence, "Unclassified")} | gnomAD {item.gnomad_af || "n/a"}
                            </span>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="emptyState">No homozygous alternate candidates are present in the current annotated subset.</p>
                    )}
                  </article>
                </div>
              </div>
            </section>
          ) : null}

          {activeStudioView === "clinvar" ? (
            <section className="notebookPanel studioCanvasPanel">
              <div className="notebookHeader">
                <h2>ClinVar Review</h2>
              </div>
              <div className="studioCanvasBody">
                <div className="resultSectionSplit">
                  <article className="miniCard">
                    <h3>Clinical significance mix</h3>
                    <DistributionList items={clinvarCounts} emptyLabel="No ClinVar-style labels were found." />
                  </article>
                  <article className="miniCard">
                    <h3>Representative records</h3>
                    <div className="resultList">
                      {analysis.annotations.slice(0, 8).map((item) => (
                        <button
                          type="button"
                          key={`${item.contig}-${item.pos_1based}-${item.rsid}-clinvar`}
                          className="resultListItem"
                          onClick={() => {
                            const nextIndex = searchedAnnotations.findIndex(
                              (candidate) =>
                                candidate.contig === item.contig &&
                                candidate.pos_1based === item.pos_1based &&
                                candidate.rsid === item.rsid,
                            );
                            setSelectedAnnotationIndex(nextIndex >= 0 ? nextIndex : 0);
                            setActiveStudioView("annotations");
                          }}
                        >
                          <strong>
                            {item.gene || "Unknown"} | {item.rsid || `${item.contig}:${item.pos_1based}`}
                          </strong>
                          <span>
                            {summarizeLabel(item.clinical_significance, "Unreviewed")} |{" "}
                            {summarizeLabel(item.clinvar_conditions, "No condition")}
                          </span>
                        </button>
                      ))}
                    </div>
                  </article>
                </div>
              </div>
            </section>
          ) : null}

          {activeStudioView === "vep" ? (
            <section className="notebookPanel studioCanvasPanel">
              <div className="notebookHeader">
                <h2>VEP Consequence</h2>
              </div>
              <div className="studioCanvasBody">
                <div className="resultSectionSplit">
                  <article className="miniCard">
                    <h3>Top consequences</h3>
                    <DistributionList items={consequenceCounts} emptyLabel="No consequence labels were found." />
                  </article>
                  <article className="miniCard">
                    <h3>Gene burden</h3>
                    <DistributionList items={geneCounts} emptyLabel="No gene burden summary is available." />
                  </article>
                </div>
              </div>
            </section>
          ) : null}

          {activeStudioView === "references" ? (
            <section className="notebookPanel studioCanvasPanel">
              <div className="notebookHeader">
                <h2>References</h2>
              </div>
              <div className="studioCanvasBody">
                <ol className="referenceList">
                  {analysis.references.map((item, index) => (
                    <li key={item.id}>
                      <span className="referenceIndex">[{index + 1}]</span>{" "}
                      <a href={item.url} target="_blank" rel="noreferrer">
                        {item.title}
                      </a>
                    </li>
                  ))}
                </ol>
              </div>
            </section>
          ) : null}

          {activeStudioView === "igv" ? (
            <section className="studioCanvasPanel">
              <IgvBrowser
                buildGuess={analysis.facts.genome_build_guess ?? null}
                annotations={searchedAnnotations}
                selectedIndex={safeSelectedIndex}
              />
            </section>
          ) : null}

          {activeStudioView === "annotations" ? (
            <section className="notebookPanel studioCanvasPanel">
              <div className="notebookHeader">
                <h2>Annotations</h2>
              </div>
              <div className="studioCanvasBody">
                <div className="oeAnnotationControls">
                  <label className="field">
                    <span>Search gene / consequence / ClinVar</span>
                    <input
                      value={annotationSearch}
                      onChange={(event) => {
                        setAnnotationSearch(event.target.value);
                        setSelectedAnnotationIndex(0);
                      }}
                      placeholder="e.g. PALMD, missense_variant, benign"
                    />
                  </label>
                  <label className="field">
                    <span>Annotation dropdown</span>
                    <select
                      value={safeSelectedIndex}
                      onChange={(event) => setSelectedAnnotationIndex(Number(event.target.value))}
                      disabled={!searchedAnnotations.length}
                    >
                      {searchedAnnotations.length ? (
                        searchedAnnotations.map((item, index) => (
                          <option key={`${item.contig}-${item.pos_1based}-${item.rsid}-${index}`} value={index}>
                            {item.gene || "Unknown"} | {item.contig}:{item.pos_1based} | {item.rsid || "no-rsID"} | {item.consequence}
                          </option>
                        ))
                      ) : (
                        <option value={0}>No annotations matched the search</option>
                      )}
                    </select>
                  </label>
                </div>
                {selectedAnnotation ? (
                  <AnnotationDetailCard item={selectedAnnotation} />
                ) : (
                  <p className="emptyState">No annotation is available for the current selection.</p>
                )}
              </div>
            </section>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
