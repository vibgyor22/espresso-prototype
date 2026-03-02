// Espresso Inference Console Frontend
// Wires the HTML console to the Flask API and renders visualizations.

let DATASETS = [];
let RUN_HISTORY = [];
let ACTIVE_RUN = null;

function $(selector) {
  return document.querySelector(selector);
}

function createEl(tag, className, children) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (children) {
    if (Array.isArray(children)) {
      children.forEach((c) => (c ? el.appendChild(c) : null));
    } else if (typeof children === "string") {
      el.textContent = children;
    } else {
      el.appendChild(children);
    }
  }
  return el;
}

function truncate(text, max) {
  if (!text) return "";
  return text.length > max ? text.slice(0, max - 1) + "…" : text;
}

async function fetchJSON(url, options) {
  const resp = await fetch(url, options || {});
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || resp.statusText);
  }
  return resp.json();
}

function setLoading(loading) {
  const overlay = $("#loadingOverlay");
  if (!overlay) return;
  overlay.style.display = loading ? "flex" : "none";
  if (loading) {
    const steps = Array.from(document.querySelectorAll("#loadingSteps .step"));
    steps.forEach((step) => step.classList.remove("active"));
    let idx = 0;
    const advance = () => {
      if (overlay.style.display !== "flex") return;
      steps.forEach((s) => s.classList.remove("active"));
      steps[idx % steps.length].classList.add("active");
      idx += 1;
      setTimeout(advance, 650);
    };
    setTimeout(advance, 200);
  }
}

async function loadDatasets() {
  try {
    const data = await fetchJSON("/api/datasets");
    DATASETS = data || [];
    const select = $("#datasetSelect");
    if (!select) return;
    DATASETS.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.id;
      opt.textContent = d.name;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error("Failed to load datasets", err);
  }

  // After datasets are loaded, try to hydrate history from the audit log
  try {
    const hist = await fetchJSON("/api/history?limit=25");
    const runs = hist.runs || [];
    // The history endpoint only returns metadata; keep it for the left panel list.
    RUN_HISTORY = runs.map((r) => ({
      dataset: { id: r.dataset_id, name: r.dataset_name },
      analysis: {
        intent: { question: r.question },
        selected_model: r.selected_model,
        spec_summary: r.spec_summary,
      },
    }));
    renderHistory();
  } catch (err) {
    console.warn("Unable to load server-side history", err);
  }
}

async function onDatasetChange() {
  const select = $("#datasetSelect");
  const info = $("#datasetInfo");
  const headerStatus = $("#headerStatus");
  const inputHint = $("#inputHint");
  const questionInput = $("#questionInput");
  const sendBtn = $("#sendBtn");

  if (!select || !info) return;
  const id = select.value;
  if (!id) {
    info.textContent = "";
    headerStatus.textContent = "Select a dataset and ask a question";
    inputHint.textContent = "Select a dataset first";
    questionInput.disabled = true;
    sendBtn.disabled = true;
    return;
  }

  try {
    setLoading(true);
    const payload = await fetchJSON(`/api/datasets/${encodeURIComponent(id)}/profile`);
    const meta = payload.dataset || {};
    const profile = payload.profile || {};
    const summary = profile.summary || {};
    const structure = profile.structure || {};

    info.innerHTML = "";
    const nameEl = createEl("div", null, truncate(meta.description || "", 160));

    const pill = createEl("div", "dataset-pill", [
      createEl("span", null, meta.dataset_type || "dataset"),
      createEl("span", null, "•"),
      createEl("span", null, meta.id || ""),
    ]);

    const metrics = createEl("div", "dataset-metrics");
    metrics.appendChild(
      createEl(
        "div",
        "dataset-metric",
        `${summary.n_rows?.toLocaleString?.() || "?"} rows`
      )
    );
    metrics.appendChild(
      createEl(
        "div",
        "dataset-metric",
        `${summary.n_columns?.toLocaleString?.() || "?"} columns`
      )
    );
    if (summary.inferred_time_column) {
      metrics.appendChild(
        createEl("div", "dataset-metric", `time: ${summary.inferred_time_column}`)
      );
    }
    if (summary.inferred_unit_column) {
      metrics.appendChild(
        createEl("div", "dataset-metric", `unit: ${summary.inferred_unit_column}`)
      );
    }

    info.appendChild(nameEl);
    info.appendChild(pill);
    info.appendChild(metrics);

    headerStatus.textContent = "Dataset ready. Ask a question about causality or forecasts.";
    inputHint.textContent = "Ask about causal effects or forecasts on this dataset.";
    questionInput.disabled = false;
    sendBtn.disabled = false;
  } catch (err) {
    console.error("Failed to load dataset profile", err);
    info.textContent = "Error loading dataset profile.";
  } finally {
    setLoading(false);
  }
}

function pushMessage(role, text, meta) {
  const welcome = $("#welcomeState");
  const messages = $("#messagesContainer");
  if (!messages) return;

  if (welcome && welcome.style.display !== "none") {
    welcome.style.display = "none";
    messages.style.display = "flex";
  }

  const row = createEl("div", `message-row ${role}`);
  const bubble = createEl("div", `message-bubble ${role}`);

  if (meta && role === "system") {
    const metaRow = createEl("div", "message-meta");
    if (meta.model) {
      metaRow.appendChild(createEl("span", "model-pill", meta.model));
    }
    if (meta.status) {
      metaRow.appendChild(createEl("span", null, meta.status));
    }
    bubble.appendChild(metaRow);
  }

  const content = createEl("div", null);
  content.textContent = text;
  bubble.appendChild(content);
  row.appendChild(bubble);
  messages.appendChild(row);
  messages.scrollTop = messages.scrollHeight;

  return { row, bubble, content };
}

async function sendQuestion() {
  const select = $("#datasetSelect");
  const input = $("#questionInput");
  const sendBtn = $("#sendBtn");
  const headerStatus = $("#headerStatus");

  if (!select || !input || !sendBtn) return;
  const datasetId = select.value;
  const question = input.value.trim();
  if (!datasetId || !question) return;

  sendBtn.disabled = true;

  const userMsg = pushMessage("user", question);
  const systemPlaceholder = pushMessage("system", "Thinking…", {
    model: "Pending",
    status: "Preparing diagnostics",
  });

  try {
    setLoading(true);
    headerStatus.textContent = "Running diagnostics, estimating model, and interpreting…";

    const body = JSON.stringify({ dataset_id: datasetId, question });
    const resp = await fetchJSON("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });

    ACTIVE_RUN = resp;
    RUN_HISTORY.unshift(resp);
    renderHistory();

    const analysis = resp.analysis || {};
    const intent = analysis.intent || {};
    const model = analysis.selected_model || "unknown";
    const diagnostics = analysis.diagnostics_overview || {};
    const diagText = diagnostics.text || "";

    const shortSummaryLines = [];
    if (model === "arima") {
      const mr = (analysis.model_results || [])[0] || {};
      const res = mr.results || {};
      if (res.last_value != null && res.forecast_next_period != null) {
        const change =
          Number(res.forecast_next_period) - Number(res.last_value);
        const dir =
          change > 0 ? "increase" : change < 0 ? "decrease" : "stay roughly flat";
        shortSummaryLines.push(
          `Forecast suggests ${dir} from ${Number(res.last_value).toFixed(
            2
          )} to ${Number(res.forecast_next_period).toFixed(2)} next period.`
        );
      }
    } else if (model === "diff_in_diff") {
      const mr = (analysis.model_results || [])[0] || {};
      const res = mr.results || {};
      if (res.treatment_effect != null && res.pvalue != null) {
        const eff = Number(res.treatment_effect);
        const p = Number(res.pvalue);
        shortSummaryLines.push(
          `Estimated treatment effect ${eff >= 0 ? "increases" : "reduces"} the outcome by ${eff.toFixed(
            2
          )} (p=${p.toFixed(4)}).`
        );
      }
    }
    if (diagText) {
      const firstLine = diagText.split("\n").find((l) => l.trim());
      if (firstLine) {
        shortSummaryLines.push(firstLine.trim());
      }
    }

    systemPlaceholder.content.textContent =
      shortSummaryLines.join(" ") || "Analysis completed.";
    const modelLabel =
      model === "arima"
        ? "AR(1) Forecast"
        : model === "diff_in_diff"
          ? "Difference-in-Differences"
          : model;
    systemPlaceholder.bubble
      .querySelector(".model-pill")
      ?.replaceWith(createEl("span", "model-pill", modelLabel));

    const button = createEl("button", "results-button", "Open full console view");
    button.addEventListener("click", () => openResultsModal(resp));
    systemPlaceholder.bubble.appendChild(button);

    headerStatus.textContent = "Analysis complete. Interrogate the results or run another question.";
    input.value = "";
  } catch (err) {
    console.error("Analysis error", err);
    systemPlaceholder.content.textContent =
      "Error running analysis. The backend reported: " + err.message;
    systemPlaceholder.bubble
      .querySelector(".model-pill")
      ?.replaceWith(createEl("span", "model-pill", "Error"));
  } finally {
    setLoading(false);
    sendBtn.disabled = false;
  }
}

function renderHistory() {
  const list = $("#historyList");
  if (!list) return;
  list.innerHTML = "";
  RUN_HISTORY.forEach((run, idx) => {
    const meta = run.dataset || {};
    const analysis = run.analysis || {};
    const intent = analysis.intent || {};
    const model = analysis.selected_model || "unknown";
    const item = createEl("div", "history-item");
    const title = createEl(
      "div",
      "history-item-title",
      truncate(intent.question || "", 60)
    );
    const metaLine = createEl(
      "div",
      "history-item-meta",
      `${meta.name || meta.id || "dataset"} • ${model}`
    );
    item.appendChild(title);
    item.appendChild(metaLine);
    item.addEventListener("click", () => openResultsModal(run));
    list.appendChild(item);
  });
}

let chartJsLoaded = false;

async function ensureChartJs() {
  if (chartJsLoaded || window.Chart) {
    chartJsLoaded = true;
    return;
  }
  await new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src =
      "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js";
    script.onload = () => {
      chartJsLoaded = true;
      resolve();
    };
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

let activeChart = null;

async function openResultsModal(run) {
  const overlay = $("#resultsModal");
  const container = $("#resultsContainer");
  if (!overlay || !container) return;

  overlay.style.display = "flex";
  container.innerHTML = "";

  const dataset = run.dataset || {};
  const analysis = run.analysis || {};
  const intent = analysis.intent || {};
  const model = analysis.selected_model || "unknown";
  const modelResults = analysis.model_results || [];
  const mainResult = modelResults[0] || {};
  const diagnosticsOverview = analysis.diagnostics_overview || {};

  const header = createEl("div", "results-header");
  const title = createEl(
    "div",
    "results-title",
    intent.question || "Analysis results"
  );
  const subtitle = createEl(
    "div",
    "results-subtitle",
    `${dataset.name || dataset.id || "dataset"} • ${
      model === "arima"
        ? "AR(1) Forecast"
        : model === "diff_in_diff"
          ? "Difference-in-Differences"
          : model
    }`
  );
  header.appendChild(title);
  header.appendChild(subtitle);

  const grid = createEl("div", "results-grid");

  const left = createEl("div", "results-panel");
  left.appendChild(createEl("div", "results-panel-title", "Model & Visuals"));

  const miniRow = createEl("div", "mini-metric-row");
  if (model === "arima") {
    const res = mainResult.results || {};
    miniRow.appendChild(
      createEl(
        "div",
        "mini-metric",
        `AR(1): ${Number(res.ar1_coef || 0).toFixed(3)}`
      )
    );
    miniRow.appendChild(
      createEl(
        "div",
        "mini-metric",
        `RMSE: ${Number(res.rmse || 0).toFixed(3)}`
      )
    );
    miniRow.appendChild(
      createEl(
        "div",
        "mini-metric",
        `Obs: ${Number(res.n_obs || 0).toLocaleString()}`
      )
    );
  } else if (model === "diff_in_diff") {
    const res = mainResult.results || {};
    miniRow.appendChild(
      createEl(
        "div",
        "mini-metric",
        `Effect: ${Number(res.treatment_effect || 0).toFixed(2)}`
      )
    );
    miniRow.appendChild(
      createEl(
        "div",
        "mini-metric",
        `p=${Number(res.pvalue || 1).toFixed(4)}`
      )
    );
    miniRow.appendChild(
      createEl(
        "div",
        "mini-metric",
        `R²: ${Number(res.r_squared || 0).toFixed(3)}`
      )
    );
  }
  left.appendChild(miniRow);

  const chartWrapper = createEl("div", "chart-wrapper");
  const canvas = createEl("canvas", "chart-canvas");
  canvas.id = "resultsChart";
  chartWrapper.appendChild(canvas);
  left.appendChild(chartWrapper);

  const right = createEl("div", "results-panel");
  right.appendChild(
    createEl("div", "results-panel-title", "Interpretation & Diagnostics")
  );

  const interp = createEl("div", "interpretation-block");
  const interpText = mainResult.llm_interpretation || "";
  if (interpText) {
    // Basic markdown-ish rendering: split into lines, make bullets
    const lines = interpText.split("\n").filter((l) => l.trim().length > 0);
    const ul = document.createElement("ul");
    lines.forEach((line) => {
      const li = document.createElement("li");
      li.textContent = line.replace(/^[-•]\s*/, "");
      ul.appendChild(li);
    });
    interp.appendChild(ul);
  } else {
    interp.textContent = "No interpretation available.";
  }

  const diags = createEl("div", "diagnostics-list");
  const diag = diagnosticsOverview.diagnostics || {};
  const checks = diag.checks || [];
  if (checks.length > 0) {
    const headerLine = createEl(
      "div",
      null,
      `Diagnostics (${diag.model || "model"}):`
    );
    diags.appendChild(headerLine);
    const tags = createEl("div", null);
    checks.forEach((check) => {
      const tag = createEl(
        "span",
        "diagnostic-tag " + (check.is_violated ? "fail" : "ok"),
        check.interpretation || check.test
      );
      tags.appendChild(tag);
    });
    diags.appendChild(tags);
  } else if (diagnosticsOverview.text) {
    diags.textContent = diagnosticsOverview.text;
  } else {
    diags.textContent = "No diagnostics available.";
  }

  right.appendChild(interp);
  right.appendChild(diags);

  grid.appendChild(left);
  grid.appendChild(right);

  container.appendChild(header);
  container.appendChild(grid);

  $("#closeModal")?.addEventListener("click", () => {
    overlay.style.display = "none";
  });

  await ensureChartJs();
  if (activeChart) {
    activeChart.destroy();
    activeChart = null;
  }

  const ctx = document.getElementById("resultsChart");
  if (!ctx || !window.Chart) return;

  if (model === "arima") {
    const res = mainResult.results || {};
    const histVals = res.historical_values || [];
    const histTimes = res.historical_times || [];
    const forecasts = res.forecasts || [];
    const forecastTimes = res.forecast_times || [];
    const labels = histTimes.concat(forecastTimes);
    const histData = histVals.concat(Array(forecasts.length).fill(null));
    const forecastData = Array(histVals.length).fill(null).concat(forecasts);

    activeChart = new window.Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Historical",
            data: histData,
            borderColor: "#ffb35c",
            backgroundColor: "rgba(255,179,92,0.2)",
            tension: 0.3,
          },
          {
            label: "Forecast",
            data: forecastData,
            borderColor: "#8f5fff",
            backgroundColor: "rgba(143,95,255,0.2)",
            borderDash: [6, 4],
            tension: 0.3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            ticks: { color: "#c3b7e6" },
          },
          y: {
            ticks: { color: "#c3b7e6" },
          },
        },
        plugins: {
          legend: { labels: { color: "#f7f2ff" } },
        },
      },
    });
  } else if (model === "diff_in_diff") {
    const res = mainResult.results || {};
    const effect = Number(res.treatment_effect || 0);
    const se = Number(res.se || 0);
    const ciLower = effect - 1.96 * se;
    const ciUpper = effect + 1.96 * se;

    activeChart = new window.Chart(ctx, {
      type: "bar",
      data: {
        labels: ["Effect"],
        datasets: [
          {
            label: "Estimated effect",
            data: [effect],
            backgroundColor: "rgba(255,179,92,0.7)",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              afterBody() {
                return [`95% CI: [${ciLower.toFixed(2)}, ${ciUpper.toFixed(2)}]`];
              },
            },
          },
        },
        scales: {
          x: { ticks: { color: "#c3b7e6" } },
          y: {
            ticks: { color: "#c3b7e6" },
            grid: { color: "rgba(255,255,255,0.06)" },
          },
        },
      },
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const datasetSelect = $("#datasetSelect");
  const sendBtn = $("#sendBtn");
  const input = $("#questionInput");
  const suggestions = document.querySelectorAll(".suggestion-chip");

  if (datasetSelect) {
    datasetSelect.addEventListener("change", onDatasetChange);
  }

  if (sendBtn) {
    sendBtn.addEventListener("click", (e) => {
      e.preventDefault();
      sendQuestion();
    });
  }

  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendQuestion();
      }
    });
  }

  suggestions.forEach((btn) => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-question");
      if (!q) return;
      if (input) {
        input.value = q;
        input.focus();
      }
    });
  });

  const closeModal = $("#closeModal");
  const modalOverlay = $("#resultsModal");
  if (closeModal && modalOverlay) {
    closeModal.addEventListener("click", () => {
      modalOverlay.style.display = "none";
    });
    modalOverlay.addEventListener("click", (e) => {
      if (e.target === modalOverlay) {
        modalOverlay.style.display = "none";
      }
    });
  }

  loadDatasets();
});

