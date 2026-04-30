const datasetChoice = document.querySelector("#datasetChoice");
const datasetFile = document.querySelector("#datasetFile");
const fileMeta = document.querySelector("#fileMeta");
const previewTable = document.querySelector("#previewTable");
const datasetMeta = document.querySelector("#datasetMeta");
const form = document.querySelector("#analysisForm");
const statusPill = document.querySelector("#statusPill");
const resultPanel = document.querySelector("#resultPanel");
const resultTitle = document.querySelector("#resultTitle");
const reportLink = document.querySelector("#reportLink");
const metrics = document.querySelector("#metrics");
const interpretation = document.querySelector("#interpretation");
const diagnostics = document.querySelector("#diagnostics");

function setStatus(text, mode = "") {
  statusPill.textContent = text;
  statusPill.className = `status-pill ${mode}`.trim();
}

function fmt(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "NA";
  if (typeof value === "number") {
    if (Math.abs(value) >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
    return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  return String(value);
}

function renderPreview(profile) {
  const rows = profile.preview || [];
  const columns = profile.column_names || [];
  datasetMeta.textContent = `${profile.rows || 0} rows, ${profile.columns || 0} columns`;

  const thead = previewTable.querySelector("thead");
  const tbody = previewTable.querySelector("tbody");
  thead.innerHTML = "";
  tbody.innerHTML = "";

  if (!rows.length || !columns.length) {
    tbody.innerHTML = `<tr><td class="empty-state">No preview available.</td></tr>`;
    return;
  }

  thead.innerHTML = `<tr>${columns.map((col) => `<th>${col}</th>`).join("")}</tr>`;
  rows.forEach((row) => {
    tbody.insertAdjacentHTML(
      "beforeend",
      `<tr>${columns.map((col) => `<td>${fmt(row[col])}</td>`).join("")}</tr>`
    );
  });
}

function metric(label, value) {
  return `
    <div class="metric">
      <div class="metric-label">${label}</div>
      <div class="metric-value">${fmt(value)}</div>
    </div>
  `;
}

function renderResult(payload) {
  const result = payload.result || {};
  resultTitle.textContent = payload.selected_model_label || result.model || "Analysis result";
  reportLink.href = payload.report_url;
  reportLink.hidden = !payload.report_url;

  if (result.forecasts) {
    metrics.innerHTML = [
      metric("Next forecast", result.forecasts[0]),
      metric("RMSE", result.rmse),
      metric("Observations", result.n_obs),
      metric("Engine", result.engine || "model"),
    ].join("");
  } else {
    metrics.innerHTML = [
      metric("Effect", result.effect),
      metric("P-value", result.p_value),
      metric("R-squared", result.r_squared),
      metric("Observations", result.n_obs),
    ].join("");
  }

  interpretation.textContent = result.llm_interpretation || "No interpretation returned.";
  diagnostics.textContent = payload.diagnostics_text || "No diagnostics returned.";
  resultPanel.hidden = false;
  resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

datasetChoice?.addEventListener("change", async () => {
  const id = datasetChoice.value;
  if (!id) return;
  datasetFile.value = "";
  fileMeta.textContent = "Maximum 25 MB";
  setStatus("Loading data");
  const response = await fetch(`/api/datasets/${encodeURIComponent(id)}`);
  const profile = await response.json();
  if (response.ok) {
    renderPreview(profile);
    setStatus("Ready");
  } else {
    setStatus(profile.error || "Could not load", "error");
  }
});

datasetFile?.addEventListener("change", () => {
  const file = datasetFile.files[0];
  if (!file) return;
  datasetChoice.value = "";
  fileMeta.textContent = `${file.name} selected`;
  datasetMeta.textContent = "Upload will preview after analysis";
});

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("Running", "running");
  resultPanel.hidden = true;

  try {
    const response = await fetch("/analyze", {
      method: "POST",
      body: new FormData(form),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Analysis failed");
    renderPreview(payload.data_profile || {});
    renderResult(payload);
    setStatus("Complete");
  } catch (error) {
    setStatus("Needs attention", "error");
    resultPanel.hidden = false;
    resultTitle.textContent = "Analysis could not run";
    reportLink.hidden = true;
    metrics.innerHTML = "";
    interpretation.textContent = error.message;
    diagnostics.textContent = "Check the dataset shape, the research question, and the selected model.";
  }
});
