const apiBaseInput = document.querySelector("#api-base");
const vcfPathInput = document.querySelector("#vcf-path");
const fileInput = document.querySelector("#vcf-file");
const analyzePathButton = document.querySelector("#analyze-path");
const analyzeUploadButton = document.querySelector("#analyze-upload");
const statusPill = document.querySelector("#status-pill");
const jobMode = document.querySelector("#job-mode");
const jobStatus = document.querySelector("#job-status");
const userQuestion = document.querySelector("#user-question");
const assistantSummary = document.querySelector("#assistant-summary");
const factGrid = document.querySelector("#fact-grid");
const annotationList = document.querySelector("#annotation-list");
const referenceList = document.querySelector("#reference-list");
const recommendationList = document.querySelector("#recommendation-list");
const uiCardList = document.querySelector("#ui-card-list");
const analysisId = document.querySelector("#analysis-id");
const suggestionButtons = document.querySelectorAll(".suggestion");
let activeJobId = null;

function setStatus(kind, text) {
  statusPill.className = `pill ${kind}`;
  statusPill.textContent = text;
}

function setJobStatus(text) {
  jobStatus.textContent = text;
}

function renderFacts(facts) {
  const variantTypes = Object.entries(facts.variant_types || {})
    .map(([name, count]) => `${name}: ${count}`)
    .join(", ") || "-";

  factGrid.innerHTML = `
    <div class="fact">
      <span>Records</span>
      <strong>${facts.record_count ?? "-"}</strong>
    </div>
    <div class="fact">
      <span>Samples</span>
      <strong>${facts.samples?.length ?? 0}</strong>
    </div>
    <div class="fact">
      <span>Build</span>
      <strong>${facts.genome_build_guess ?? "Unknown"}</strong>
    </div>
    <div class="fact">
      <span>Variant Types</span>
      <strong>${variantTypes}</strong>
    </div>
  `;
}

function renderReferences(references) {
  if (!references.length) {
    referenceList.innerHTML = `<p class="empty-state">No references attached.</p>`;
    return;
  }

  referenceList.innerHTML = references
    .map(
      (item) => `
        <article class="evidence-item">
          <h3>${item.id}: ${item.title}</h3>
          <p>${item.note}</p>
          <span class="tagline">${item.source}</span>
          <p><a href="${item.url}" target="_blank" rel="noreferrer">Open source</a></p>
        </article>
      `,
    )
    .join("");
}

function renderAnnotations(annotations) {
  if (!annotationList) {
    return;
  }
  if (!annotations.length) {
    annotationList.innerHTML = `<p class="empty-state">No live annotations attached.</p>`;
    return;
  }

  annotationList.innerHTML = annotations
    .map(
      (item) => `
        <article class="mini-card">
          <h3>${item.contig}:${item.pos_1based} ${item.ref}&gt;${item.alts.join(",")}</h3>
          <p>${item.gene} | ${item.consequence} | rsID ${item.rsid}</p>
          <p>ClinVar: ${item.clinical_significance} | Review: ${item.clinvar_review_status}</p>
          <p>Conditions: ${item.clinvar_conditions} | gnomAD AF: ${item.gnomad_af}</p>
          <p>Ensembl MAF: ${item.maf}</p>
          ${item.source_url !== "." ? `<p><a href="${item.source_url}" target="_blank" rel="noreferrer">Open annotation</a></p>` : ""}
        </article>
      `,
    )
    .join("");
}

function renderRecommendations(recommendations) {
  if (!recommendations.length) {
    recommendationList.innerHTML = `<p class="empty-state">No recommendations generated.</p>`;
    return;
  }

  recommendationList.innerHTML = recommendations
    .map(
      (item) => `
        <article class="recommendation-item">
          <h3>${item.title}</h3>
          <p>${item.rationale}</p>
          <p><strong>Action:</strong> ${item.action}</p>
          <span class="priority">${item.priority}</span>
        </article>
      `,
    )
    .join("");
}

function renderUiCards(cards) {
  if (!cards.length) {
    uiCardList.innerHTML = `<p class="empty-state">No structured cards available.</p>`;
    return;
  }

  uiCardList.innerHTML = cards
    .map(
      (card) => `
        <article class="mini-card">
          <h3>${card.title}</h3>
          <p>${(card.items || []).join(" | ")}</p>
        </article>
      `,
    )
    .join("");
}

function renderResponse(payload) {
  analysisId.textContent = payload.analysis_id;
  assistantSummary.textContent = payload.draft_answer;
  renderFacts(payload.facts);
  renderAnnotations(payload.annotations || []);
  renderReferences(payload.references || []);
  renderRecommendations(payload.recommendations || []);
  renderUiCards(payload.ui_cards || []);
}

function showError(message) {
  assistantSummary.textContent = message;
  referenceList.innerHTML = `<p class="empty-state">No references due to an error.</p>`;
  if (annotationList) {
    annotationList.innerHTML = `<p class="empty-state">No annotations due to an error.</p>`;
  }
  recommendationList.innerHTML = `<p class="empty-state">No recommendations due to an error.</p>`;
  uiCardList.innerHTML = `<p class="empty-state">No cards due to an error.</p>`;
  analysisId.textContent = "Analysis failed";
  setJobStatus("No active job");
}

async function pollJob(apiBase, jobId) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const response = await fetch(`${apiBase}/api/v1/analysis/jobs/${jobId}`);
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `HTTP ${response.status}`);
    }

    const payload = await response.json();
    setJobStatus(`Job ${jobId.slice(0, 8)} is ${payload.status}`);

    if (payload.status === "completed" && payload.result) {
      renderResponse(payload.result);
      setStatus("ready", "Grounded");
      setJobStatus(`Job ${jobId.slice(0, 8)} completed`);
      return;
    }

    if (payload.status === "failed") {
      throw new Error(payload.error || "Async analysis failed");
    }

    setStatus("waiting", payload.status === "queued" ? "Queued" : "Running");
    await new Promise((resolve) => window.setTimeout(resolve, 1200));
  }

  throw new Error("Analysis job timed out while polling");
}

async function analyzeByPath() {
  const apiBase = apiBaseInput.value.trim().replace(/\/$/, "");
  const vcfPath = vcfPathInput.value.trim();
  userQuestion.textContent = `Analyze the local VCF at ${vcfPath} and show grounded evidence plus next-step suggestions.`;
  setStatus("busy", "Submitting");
  setJobStatus("Submitting async job");
  jobMode.textContent = "Path analysis uses async jobs";

  try {
    const response = await fetch(`${apiBase}/api/v1/analysis/from-path/async`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vcf_path: vcfPath }),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `HTTP ${response.status}`);
    }

    const payload = await response.json();
    activeJobId = payload.job_id;
    analysisId.textContent = payload.job_id;
    setStatus("waiting", payload.status === "queued" ? "Queued" : "Running");
    setJobStatus(`Job ${payload.job_id.slice(0, 8)} accepted`);
    assistantSummary.textContent = "Analysis job accepted. Polling for grounded results...";
    await pollJob(apiBase, payload.job_id);
  } catch (error) {
    showError(`Analysis failed: ${error.message}`);
    setStatus("idle", "Retry");
  }
}

async function analyzeByUpload() {
  const apiBase = apiBaseInput.value.trim().replace(/\/$/, "");
  const file = fileInput.files?.[0];
  if (!file) {
    showError("Choose a VCF or VCF.gz file first.");
    return;
  }

  userQuestion.textContent = `Upload ${file.name}, summarize its variants, and provide evidence-aware next steps.`;
  setStatus("busy", "Uploading");
  setJobStatus("Direct upload analysis in progress");
  jobMode.textContent = "Upload analysis uses direct request";

  try {
    const form = new FormData();
    form.append("file", file);

    const response = await fetch(`${apiBase}/api/v1/analysis/upload`, {
      method: "POST",
      body: form,
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `HTTP ${response.status}`);
    }

    const payload = await response.json();
    renderResponse(payload);
    setStatus("ready", "Grounded");
    setJobStatus("Upload analysis completed");
  } catch (error) {
    showError(`Upload analysis failed: ${error.message}`);
    setStatus("idle", "Retry");
  }
}

suggestionButtons.forEach((button) => {
  button.addEventListener("click", () => {
    userQuestion.textContent = button.dataset.question;
  });
});

analyzePathButton.addEventListener("click", analyzeByPath);
analyzeUploadButton.addEventListener("click", analyzeByUpload);
