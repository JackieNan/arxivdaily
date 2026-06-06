const ArxivDailyWorkbench = (() => {
  const state = {
    selectedPaperId: null,
    selectedCard: null,
    templates: [],
    automationTimer: null,
    activeStatusTimer: null,
    searchPage: 1,
    pageSize: 50,
    pageMeta: null,
  };

  const AUTO_AUTOMATION_INTERVAL_MS = 10 * 60 * 1000;
  const ACTIVE_AUTOMATION_POLL_MS = 2500;

  const AUTOMATION_STEP_LABELS = {
    idle: "idle",
    queued: "queued",
    arxiv_date_check: "checking arXiv date",
    preflight: "preflight",
    crawl: "crawl",
    crawl_already_complete: "crawl already complete",
    metadata: "metadata",
    ai: "AI",
    waiting_for_arxiv_update: "waiting for arXiv update",
    metadata_waiting: "metadata waiting",
    no_papers: "no papers",
    complete: "complete",
    failed: "failed",
  };

  const DEFAULT_SUMMARY_TEMPLATE = {
    name: "daily_research",
    language: "Chinese",
    system_prompt: "你是本地 arXiv 论文阅读数据库的中文研究助理。请用简洁中文总结论文，只返回 JSON。",
    input_scope: "abstract",
    is_default: true,
    fields: [
      {
        key: "keywords",
        label: "关键词",
        order: 1,
        prompt: "提炼 5-8 个中文关键词。保留必要英文术语、模型名和 LaTeX 符号。",
        field_type: "keywords",
        enabled: true,
      },
      {
        key: "tldr",
        label: "一句话结论",
        order: 2,
        prompt: "用一句中文概括论文的核心贡献。",
        field_type: "short_sentence",
        enabled: true,
      },
      {
        key: "method",
        label: "核心方法",
        order: 3,
        prompt: "用 2-3 个中文要点解释核心方法。",
        field_type: "bullets",
        enabled: true,
      },
      {
        key: "value",
        label: "阅读价值",
        order: 4,
        prompt: "用中文说明为什么这篇论文值得阅读或暂时跳过。",
        field_type: "bullets",
        enabled: true,
      },
      {
        key: "limits",
        label: "局限",
        order: 5,
        prompt: "用中文列出明显局限、缺失证据或需要进一步确认的点。",
        field_type: "bullets",
        enabled: true,
      },
    ],
  };

  const el = (id) => document.getElementById(id);

  function todayIso() {
    return new Date().toISOString().slice(0, 10);
  }

  function setStatus(message) {
    el("run-status").textContent = message;
  }

  function setDetail(id, message) {
    const node = el(id);
    if (node) node.textContent = message;
  }

  function recordOperation(message, detail = "") {
    setStatus(message);
    setDetail("operation-log", message);
  }

  function setBusy(button, busy) {
    if (!button) return;
    button.disabled = busy;
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!response.ok) {
      throw new Error(await readErrorMessage(response));
    }
    return response.json();
  }

  async function readErrorMessage(response) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const payload = await response.json().catch(() => null);
      if (payload && typeof payload.detail === "string") return payload.detail;
      if (payload) return JSON.stringify(payload);
    }
    const text = await response.text();
    return text.trim() || `HTTP ${response.status}`;
  }

  function renderLatexText(value) {
    const text = String(value ?? "");
    if (window.MathJax && typeof window.MathJax.typesetPromise === "function") {
      return escapeHtml(text);
    }
    return renderLocalLatexText(text);
  }

  function renderLocalLatexText(text) {
    const parts = [];
    const pattern = /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$|\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\])/g;
    let cursor = 0;
    let match;
    while ((match = pattern.exec(text)) !== null) {
      parts.push(escapeHtml(text.slice(cursor, match.index)));
      parts.push(renderLocalFormula(match[0]));
      cursor = match.index + match[0].length;
    }
    parts.push(escapeHtml(text.slice(cursor)));
    return parts.join("");
  }

  function renderLocalFormula(source) {
    const display = source.startsWith("$$") || source.startsWith("\\[");
    const inner = source
      .replace(/^\$\$|\$\$$/g, "")
      .replace(/^\$|\$$/g, "")
      .replace(/^\\\(|\\\)$/g, "")
      .replace(/^\\\[|\\\]$/g, "")
      .trim();
    const className = display ? "math-fallback display" : "math-fallback";
    return `<span class="${className}">${renderTexFragment(inner)}</span>`;
  }

  function renderTexFragment(tex) {
    let html = escapeHtml(tex)
      .replace(/\\,/g, " ")
      .replace(/\\!/g, "")
      .replace(/\\left/g, "")
      .replace(/\\right/g, "");
    const groupedCommands = [
      ["mathscr", "math-script"],
      ["mathcal", "math-script"],
      ["mathbf", "math-bold"],
      ["mathrm", "math-roman"],
      ["rm", "math-roman"],
      ["underline", "math-underline"],
      ["widehat", "math-hat"],
      ["hat", "math-hat"],
    ];
    for (const [command, className] of groupedCommands) {
      html = html.replace(new RegExp(`\\\\${command}\\{([^{}]*)\\}`, "g"), (_, inner) => {
        return `<span class="${className}">${renderTexFragment(inner)}</span>`;
      });
    }
    html = html
      .replace(/\^\{([^{}]*)\}/g, (_, inner) => `<sup>${renderTexFragment(inner)}</sup>`)
      .replace(/_\{([^{}]*)\}/g, (_, inner) => `<sub>${renderTexFragment(inner)}</sub>`)
      .replace(/\^([A-Za-z0-9+\-=])/g, "<sup>$1</sup>")
      .replace(/_([A-Za-z0-9+\-=])/g, "<sub>$1</sub>")
      .replace(/\\rm\s+([A-Za-z]+)/g, '<span class="math-roman">$1</span>');
    const greek = {
      alpha: "α",
      beta: "β",
      gamma: "γ",
      delta: "δ",
      epsilon: "ε",
      theta: "θ",
      lambda: "λ",
      mu: "μ",
      pi: "π",
      sigma: "σ",
      tau: "τ",
      phi: "φ",
      omega: "ω",
      Gamma: "Γ",
      Delta: "Δ",
      Theta: "Θ",
      Lambda: "Λ",
      Pi: "Π",
      Sigma: "Σ",
      Phi: "Φ",
      Omega: "Ω",
    };
    html = html.replace(/\\([A-Za-z]+)/g, (_, command) => greek[command] || command);
    return html;
  }

  function typesetMath(root) {
    if (!window.MathJax || typeof window.MathJax.typesetPromise !== "function") return;
    window.MathJax.typesetPromise([root]).catch((error) => {
      console.warn("MathJax typeset failed", error);
    });
  }

  async function loadSummaryTemplates() {
    try {
      const data = await api("/api/summary-templates");
      state.templates = data.templates || [];
      if (state.templates.length) {
        const defaultTemplate = state.templates.find((template) => template.is_default) || state.templates[0];
        el("summary-template").value = defaultTemplate.name;
        populateTemplateEditor(templateFields(defaultTemplate));
        setDetail(
          "summary-template-help",
          `Template ${defaultTemplate.name} v${defaultTemplate.version} ready.`
        );
      } else {
        populateTemplateEditor(DEFAULT_SUMMARY_TEMPLATE.fields);
        setDetail("summary-template-help", "Create a template before running summaries.");
      }
    } catch (error) {
      setDetail("summary-template-help", `Template load failed: ${error.message}`);
    }
  }

  function templateFields(template) {
    if (Array.isArray(template.fields)) return template.fields;
    if (typeof template.fields_json === "string") {
      try {
        const fields = JSON.parse(template.fields_json);
        if (Array.isArray(fields)) return fields;
      } catch (error) {
        console.warn("Template fields_json parse failed", error);
      }
    }
    return DEFAULT_SUMMARY_TEMPLATE.fields;
  }

  function toggleTemplateEditor() {
    const editor = el("template-editor");
    const nextHidden = !editor.hidden;
    editor.hidden = nextHidden;
    el("template-editor-toggle").textContent = nextHidden ? "Edit Template" : "Close Template";
  }

  function populateTemplateEditor(fields) {
    const byKey = new Map((fields || []).map((field) => [field.key, field]));
    for (const row of document.querySelectorAll(".template-field-row")) {
      const field = byKey.get(row.dataset.templateKey);
      if (!field) continue;
      row.querySelector("[data-template-enabled]").checked = field.enabled !== false;
      row.querySelector("[data-template-label]").value = field.label || row.dataset.templateKey;
      row.querySelector("[data-template-prompt]").value = field.prompt || "";
    }
  }

  function readTemplateEditorFields() {
    return Array.from(document.querySelectorAll(".template-field-row")).map((row, index) => {
      const label = row.querySelector("[data-template-label]").value.trim();
      const prompt = row.querySelector("[data-template-prompt]").value.trim();
      return {
        key: row.dataset.templateKey,
        label: label || row.dataset.templateKey,
        order: index + 1,
        prompt,
        field_type: row.dataset.templateType,
        enabled: row.querySelector("[data-template-enabled]").checked,
      };
    });
  }

  function summaryTemplatePayload() {
    return {
      ...DEFAULT_SUMMARY_TEMPLATE,
      name: el("summary-template").value.trim() || DEFAULT_SUMMARY_TEMPLATE.name,
      fields: readTemplateEditorFields(),
    };
  }

  async function saveSummaryTemplate() {
    const button = el("summary-template-save");
    setBusy(button, true);
    try {
      const payload = summaryTemplatePayload();
      const result = await api("/api/summary-templates", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      el("summary-template").value = payload.name;
      setDetail(
        "summary-template-help",
        `Template ${payload.name} v${result.version} saved.`
      );
      recordOperation(`Saved summary template ${payload.name}`);
      await loadSummaryTemplates();
    } catch (error) {
      setDetail("summary-template-help", `Template create failed: ${error.message}`);
      recordOperation(`Template create failed: ${error.message}`);
    } finally {
      setBusy(button, false);
    }
  }

  function splitList(value) {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function dateValue() {
    return el("date-input").value || todayIso();
  }

  function shiftIsoDate(value, delta) {
    const [year, month, day] = value.split("-").map(Number);
    const shifted = new Date(Date.UTC(year, month - 1, day + delta));
    return shifted.toISOString().slice(0, 10);
  }

  function changeDateByDays(delta) {
    el("date-input").value = shiftIsoDate(dateValue(), delta);
    state.searchPage = 1;
    refreshSelectedDateView();
  }

  async function refreshSelectedDateView() {
    await loadDailyStatus({ silent: true });
    await runSearch({ silent: true });
  }

  function openDateCrawlDialog() {
    el("crawl-date-target").value = dateValue();
    el("crawl-date-dialog").hidden = false;
    el("crawl-date-target").focus();
  }

  function closeDateCrawlDialog() {
    el("crawl-date-dialog").hidden = true;
  }

  async function confirmDateCrawl() {
    const targetDate = el("crawl-date-target").value || dateValue();
    el("date-input").value = targetDate;
    state.searchPage = 1;
    await startDailyAutomation({ button: el("crawl-date-confirm") });
    closeDateCrawlDialog();
  }

  async function startDailyAutomation(options = {}) {
    const silent = options.silent === true;
    const button = silent ? null : options.button || el("crawl-date-open");
    setBusy(button, true);
    try {
      const categories = splitList(el("crawl-categories").value);
      const body = { date: dateValue() };
      const templateName = el("summary-template").value.trim();
      if (categories.length) body.categories = categories;
      if (templateName) body.template_name = templateName;
      body.model = el("summary-model").value.trim() || "local";
      body.crawl_mode = "auto";
      const result = await api("/api/daily/automation/start", {
        method: "POST",
        body: JSON.stringify(body),
      });
      renderAutomationStatus({
        id: result.automation_run_id,
        date: dateValue(),
        status: result.status,
        current_step: "queued",
        updated_at: null,
        error: null,
      });
      el("automation-state").textContent = result.status;
      startActiveStatusPolling();
      await loadDailyStatus({ silent: true });
      await runSearch({ silent: true });
      if (!silent) recordOperation(`Crawl ${dateValue()} ${result.status}; backend run #${result.automation_run_id}`);
    } catch (error) {
      el("automation-state").textContent = "failed";
      setDetail("automation-note", `Automation failed: ${error.message}`);
      if (!silent) recordOperation(`Crawl failed: ${error.message}`);
    } finally {
      setBusy(button, false);
    }
  }

  function summaryRequestBody() {
    const templateName = el("summary-template").value.trim();
    const body = {
      date: dateValue(),
      model: el("summary-model").value.trim() || "local",
    };
    if (templateName) body.template_name = templateName;
    return body;
  }

  async function runAiTriageRequest() {
    return api("/api/ai-triage/run", {
      method: "POST",
      body: JSON.stringify(summaryRequestBody()),
    });
  }

  async function runSummaryAndScore() {
    const button = el("summary-score-run");
    setBusy(button, true);
    try {
      const triage = await runAiTriageRequest();
      const message = triage.status === "not_configured"
        ? "LLM API not configured"
        : `AI triage ${triage.completed}/${triage.requested}; failed ${triage.failed}`;
      setDetail("summary-template-help", message);
      recordOperation(message);
      await loadDailyStatus({ silent: true });
      await runSearch({ silent: true });
    } catch (error) {
      const templateHint = error.message === "summary template not found"
        ? " Save a template first."
        : "";
      setDetail("summary-template-help", `Summary/score failed: ${error.message}.${templateHint}`);
      recordOperation(`Summary/score failed: ${error.message}`);
    } finally {
      setBusy(button, false);
    }
  }

  function dailyStatusParams() {
    const params = new URLSearchParams();
    const templateName = el("summary-template").value.trim();
    const model = el("summary-model").value.trim() || "local";
    params.set("model", model);
    if (templateName) params.set("template_name", templateName);
    return params;
  }

  async function loadDailyStatus(options = {}) {
    const silent = options.silent === true;
    const button = silent ? null : el("status-refresh");
    setBusy(button, true);
    try {
      const params = dailyStatusParams();
      const status = await api(`/api/daily/status/${encodeURIComponent(dateValue())}?${params.toString()}`);
      renderDailyStatus(status);
      syncActiveStatusPolling(status);
      if (!silent) recordOperation(`Daily: ${dailyStatusText(status)}`);
      return status;
    } catch (error) {
      el("automation-state").textContent = "failed";
      setDetail("automation-note", `Daily status failed: ${error.message}`);
      if (!silent) recordOperation(`Daily status failed: ${error.message}`);
      return null;
    } finally {
      setBusy(button, false);
    }
  }

  function renderDailyStatus(status) {
    const cells = el("automation-summary").querySelectorAll("strong");
    cells[0].textContent = status.status;
    cells[0].className = `status-${status.status}`;
    cells[1].textContent = String(status.metadata.total);
    cells[2].textContent = `${status.crawl.complete_category_count}/${status.crawl.expected_category_count}`;
    cells[3].textContent = metadataCoverageText(status, { compact: true });
    cells[4].textContent = `${status.summary.complete}/${status.summary.eligible}`;
    cells[5].textContent = `${status.score.complete}/${status.score.eligible}`;
    setDetail("automation-note", dailyStatusText(status));
    el("automation-state").textContent = status.status;
    el("automation-state").className = `badge status-${status.status}`;
    renderPipelineStatus(status);
  }

  function isAutomationActive(automation) {
    return automation && ["queued", "running"].includes(automation.status);
  }

  function syncActiveStatusPolling(status) {
    if (isAutomationActive(status.automation)) {
      startActiveStatusPolling();
    } else {
      stopActiveStatusPolling();
    }
  }

  function startActiveStatusPolling() {
    if (state.activeStatusTimer) return;
    state.activeStatusTimer = window.setInterval(async () => {
      const status = await loadDailyStatus({ silent: true });
      await runSearch({ silent: true });
      if (!status || !isAutomationActive(status.automation)) {
        stopActiveStatusPolling();
      }
    }, ACTIVE_AUTOMATION_POLL_MS);
  }

  function stopActiveStatusPolling() {
    if (!state.activeStatusTimer) return;
    window.clearInterval(state.activeStatusTimer);
    state.activeStatusTimer = null;
  }

  function renderPipelineStatus(status) {
    renderAutomationStatus(status.automation || {});

    const papers = paperStageStatus(status);
    renderStageStatus({
      stateId: "paper-status-state",
      countId: "paper-status-count",
      detailId: "paper-status-detail",
      ...papers,
    });

    const metadata = metadataStageStatus(status);
    renderStageStatus({
      stateId: "metadata-status-state",
      countId: "metadata-status-count",
      detailId: "metadata-status-detail",
      ...metadata,
    });

    const ai = aiStageStatus(status);
    renderStageStatus({
      stateId: "ai-status-state",
      countId: "ai-status-count",
      detailId: "ai-status-detail",
      ...ai,
    });
  }

  function renderStageStatus({ stateId, countId, detailId, state, count, detail }) {
    const stateNode = el(stateId);
    stateNode.textContent = state;
    stateNode.className = `stage-badge is-${state}`;
    el(countId).textContent = count;
    el(detailId).textContent = detail;
  }

  function renderAutomationStatus(automation) {
    const status = automation.status || "not_started";
    const state = status === "not_started" ? "idle" : status;
    const step = automation.current_step || "idle";
    const stepLabel = AUTOMATION_STEP_LABELS[step] || step;
    const idPart = automation.id ? `#${automation.id}` : "-";
    let detail = automation.id
      ? `Step: ${stepLabel}${automation.updated_at ? `; updated ${automation.updated_at}` : ""}.`
      : "No backend automation run yet.";
    if (automation.error) detail = `${detail} Error: ${automation.error}`;
    renderStageStatus({
      stateId: "automation-status-state",
      countId: "automation-status-count",
      detailId: "automation-status-detail",
      state,
      count: idPart,
      detail,
    });
  }

  function paperStageStatus(status) {
    const parsed = Number(status.crawl.parsed_paper_count || 0);
    const expected = Number(status.crawl.expected_paper_count || 0);
    const preflightTotal = preflightPaperTotal(status);
    const total = preflightTotal || expected || parsed;
    const state = paperStageState(status, parsed, expected);
    const count = total > 0 ? `${parsed}/${total}` : "-";
    let detail = "No paper crawl has started.";
    if (status.automation?.status === "queued" || status.automation?.current_step === "crawl") {
      detail = `Backend is ${status.automation.current_step || status.automation.status}.`;
    } else if (status.automation?.current_step === "crawl_already_complete") {
      detail = "Backend skipped crawl because the latest crawl audit is already complete.";
    } else if (status.automation?.current_step === "preflight") {
      detail = "Backend is verifying today's listing counts before crawl.";
    } else if (status.automation?.status === "failed") {
      detail = `Backend failed: ${status.automation.error || "unknown error"}.`;
    } else if (status.automation?.status === "waiting") {
      detail = status.automation.error || "Backend is waiting for an external condition.";
    } else if (status.automation?.current_step === "no_papers") {
      detail = "Backend completed; selected date currently has no papers in local crawl.";
    } else if (status.crawl.status === "waiting") {
      detail = "Waiting for arXiv to publish the requested listing date.";
    } else if (status.preflight?.status === "complete") {
      detail = `Preflight complete; evidence ${preflightEvidenceUrl()}.`;
    } else if (status.preflight?.status && status.preflight.status !== "not_started") {
      detail = `Preflight ${status.preflight.status}; evidence ${preflightEvidenceUrl()}.`;
    } else if (parsed || expected) {
      detail = `Crawl ${status.crawl.status || "unknown"} for selected date.`;
    }
    return { state, count, detail };
  }

  function paperStageState(status, parsed, expected) {
    if (!parsed && !expected) {
      return status.crawl.status === "waiting" ? "waiting" : "idle";
    }
    if (status.crawl.status === "complete") return "complete";
    if (status.crawl.status === "waiting") return "waiting";
    if (status.crawl.status === "partial") return "partial";
    return "running";
  }

  function metadataStageStatus(status) {
    const total = Number(status.metadata.total || 0);
    const complete = Number(status.metadata.complete || 0);
    const failed = Number(status.metadata.failed || 0);
    const retryable = Number(status.metadata.retryable || 0);
    let state = "running";
    if (!total) state = "idle";
    else if (complete === total) state = "complete";
    else if (failed) state = "failed";
    else if (retryable) state = "waiting";
    const detailParts = [];
    if (failed) detailParts.push(`${failed} failed`);
    if (retryable) detailParts.push(`${retryable} retryable`);
    const detail = total
      ? `${complete} metadata records complete${detailParts.length ? `; ${detailParts.join("; ")}` : ""}.`
      : "No metadata candidates yet.";
    return { state, count: total > 0 ? `${complete}/${total}` : "-", detail };
  }

  function aiStageStatus(status) {
    const total = Math.max(Number(status.summary.eligible || 0), Number(status.score.eligible || 0));
    const complete = Math.min(Number(status.summary.complete || 0), Number(status.score.complete || 0));
    let state = "running";
    if (!total) state = status.summary.template_missing ? "waiting" : "idle";
    else if (complete === total) state = "complete";
    else if (Number(status.summary.failed || 0) || Number(status.score.failed || 0)) state = "failed";
    else if (status.summary.template_missing) state = "waiting";
    const failures = Number(status.summary.failed || 0) + Number(status.score.failed || 0);
    let detail = total
      ? `Summary ${status.summary.complete}/${status.summary.eligible}; score ${status.score.complete}/${status.score.eligible}.`
      : "No AI candidates yet.";
    if (status.summary.template_missing) detail = `${detail} Template missing.`;
    if (failures) detail = `${detail} ${failures} failed.`;
    return { state, count: total > 0 ? `${complete}/${total}` : "-", detail };
  }

  function metadataCoverageText(status, options = {}) {
    if (options.compact) return `${status.metadata.complete}/${status.metadata.total}`;
    const failed = status.metadata.failed ? `; failed ${status.metadata.failed}` : "";
    return `${status.metadata.complete}/${status.metadata.total} complete${failed}`;
  }

  function preflightPaperTotal(status) {
    return Number(status.preflight?.distinct_paper_count || 0);
  }

  function preflightEvidenceUrl(date = dateValue()) {
    return `/api/preflight/${encodeURIComponent(date)}`;
  }

  function preflightStatusText(status) {
    const preflight = status.preflight || {};
    if (!preflight.status || preflight.status === "not_started") {
      return `Preflight not started (${preflightEvidenceUrl()}).`;
    }
    const sourcePart = `${preflight.source_count || 0}/${preflight.category_count || 0} categories`;
    const paperPart = `${status.preflight.distinct_paper_count || 0} distinct papers`;
    const errorPart = preflight.status === "complete"
      ? "all declared counts matched"
      : `errors ${JSON.stringify(preflight.error_counts || {})}`;
    return `Preflight ${preflight.status}: ${paperPart}, ${sourcePart}, ${errorPart}. Evidence: ${preflightEvidenceUrl()}.`;
  }

  function dailyStatusText(status) {
    const blockers = status.blockers && status.blockers.length
      ? `Blockers: ${status.blockers.join(", ")}.`
      : "No blockers.";
    return `Papers ${status.metadata.total}; categories ${status.crawl.complete_category_count}/${status.crawl.expected_category_count}; metadata ${metadataCoverageText(status)}; summary ${status.summary.complete}/${status.summary.eligible}; score ${status.score.complete}/${status.score.eligible}. ${preflightStatusText(status)} ${blockers}`;
  }

  function searchParams() {
    const params = new URLSearchParams();
    const pairs = [
      ["q", el("search-query").value.trim()],
      ["category", el("search-category").value.trim()],
      ["event_type", el("search-event").value],
      ["metadata_status", el("search-metadata").value],
      ["summary_status", el("search-summary").value],
      ["sort", el("search-sort").value],
    ];
    if (el("search-scope").value === "daily") {
      params.set("date", dateValue());
    }
    params.set("page", String(state.searchPage));
    params.set("page_size", String(state.pageSize));
    for (const [key, value] of pairs) {
      if (value) params.set(key, value);
    }
    return params;
  }

  function searchScopeLabel() {
    return el("search-scope").value === "daily" ? `当日 ${dateValue()}` : "总览";
  }

  async function runSearch(options = {}) {
    const silent = options.silent === true;
    const button = el("search-run");
    setBusy(button, true);
    try {
      const data = await api(`/api/search/papers?${searchParams().toString()}`);
      renderResults(data.papers);
      state.pageMeta = data;
      renderPagination(data);
      el("result-count").textContent = `${data.count}/${data.total ?? data.count}`;
      const scope = searchScopeLabel();
      const total = data.total ?? data.count;
      const detail = total
        ? `${scope}: page ${data.page || 1}/${data.total_pages || 1}, showing ${data.count} of ${total} papers.`
        : `${scope}: no matching papers with current filters.`;
      setDetail("search-detail", detail);
      if (!silent) recordOperation(`Search returned ${total} papers (${scope})`, detail);
    } catch (error) {
      setDetail("search-detail", `Search failed:\n${error.message}`);
      el("paper-results").innerHTML = `<p class="empty-state">Search failed: ${escapeHtml(error.message)}</p>`;
      if (!silent) recordOperation(`Search failed: ${error.message}`);
    } finally {
      setBusy(button, false);
    }
  }

  function renderPagination(data) {
    const page = data.page || 1;
    const totalPages = data.total_pages || 1;
    const total = data.total ?? data.count ?? 0;
    el("pagination-label").textContent = `Page ${page} / ${totalPages} · ${total} papers`;
    el("pagination-prev").disabled = !data.has_prev;
    el("pagination-next").disabled = !data.has_next;
  }

  function changeSearchPage(delta) {
    const meta = state.pageMeta || { page: state.searchPage, total_pages: 1 };
    const totalPages = meta.total_pages || 1;
    state.searchPage = Math.min(Math.max((meta.page || state.searchPage) + delta, 1), totalPages);
    runSearch();
  }

  function renderResults(papers) {
    const container = el("paper-results");
    container.innerHTML = "";
    if (!papers.length) {
      container.innerHTML = '<p class="empty-state">No matching papers.</p>';
      return;
    }
    for (const paper of papers) {
      const card = document.createElement("article");
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.className = "paper-card";
      const score = paper.score && paper.score.status === "complete" ? paper.score : null;
      const keywords = Array.isArray(paper.summary_keywords) ? paper.summary_keywords : [];
      const keywordHint = paper.metadata_error
        ? `Metadata: ${paper.metadata_error}`
        : "尚无中文关键词，运行 Summary 后生成。";
      card.innerHTML = `
        <div class="paper-card-head">
          <h3 class="paper-card-title">${renderLatexText(paper.title || paper.arxiv_id)}</h3>
          ${score ? `<span class="score-badge">${escapeHtml(score.score_total)} ${escapeHtml(score.recommended_action)}</span>` : ""}
        </div>
        <div class="paper-meta">
          <span class="tag">${escapeHtml(paper.arxiv_id)}</span>
          <span class="tag">${escapeHtml(paper.metadata_status)}</span>
          <span class="tag">${escapeHtml(paper.latest_date || "-")}</span>
          <a class="source-link" href="${escapeHtml(paperLink(paper))}" target="_blank" rel="noopener" data-source-link>arXiv</a>
        </div>
        <div class="tag-row">
          ${(paper.listing_categories || []).map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("")}
        </div>
        ${keywords.length
          ? `<div class="keyword-row" aria-label="中文关键词">${keywords.map((item) => `<span class="keyword-tag">${escapeHtml(item)}</span>`).join("")}</div>`
          : `<p class="paper-card-hint">${escapeHtml(keywordHint)}</p>`}
      `;
      card.addEventListener("click", () => selectPaper(paper.arxiv_id, card));
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") selectPaper(paper.arxiv_id, card);
      });
      const link = card.querySelector("[data-source-link]");
      if (link) link.addEventListener("click", (event) => event.stopPropagation());
      container.appendChild(card);
    }
    typesetMath(container);
  }

  async function selectPaper(arxivId, card) {
    if (state.selectedCard) state.selectedCard.classList.remove("is-selected");
    state.selectedCard = card;
    state.selectedPaperId = arxivId;
    if (card) card.classList.add("is-selected");
    await loadPaper(arxivId);
  }

  async function loadPaper(arxivId) {
    try {
      const detail = await api(`/api/papers/${encodeURIComponent(arxivId)}`);
      el("paper-id").textContent = arxivId;
      renderPaperDetail(detail);
      renderDiscussions(detail.discussions || []);
    } catch (error) {
      recordOperation(`Paper load failed: ${error.message}`);
    }
  }

  function renderPaperDetail(detail) {
    const paper = detail.paper;
    if (!paper) {
      el("paper-content").innerHTML = '<p class="empty-state">Paper not found.</p>';
      return;
    }
    const summaries = detail.summaries || [];
    const score = detail.score;
    el("paper-content").innerHTML = `
      <div class="paper-hero">
        <h3>${renderLatexText(paper.title || paper.arxiv_id)}</h3>
        ${score ? `<span class="score-badge large">${escapeHtml(score.score_total)} ${escapeHtml(score.recommended_action)}</span>` : ""}
      </div>
      <div class="tag-row compact-tags">
        <span class="tag">${escapeHtml(paper.arxiv_id)}</span>
        <span class="tag">${escapeHtml(paper.metadata_status)}</span>
        <a class="source-link" href="${escapeHtml(paperLink(paper))}" target="_blank" rel="noopener">arXiv original</a>
        ${(paper.categories || []).map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("")}
      </div>
      ${metadataNotice(paper)}
      ${score ? `<div class="section-block score-block"><h4>Score</h4><p>${escapeHtml(score.rationale)}</p></div>` : ""}
      <div class="section-block">
        <h4>Authors</h4>
        <p>${escapeHtml((paper.authors || []).join(", ") || "-")}</p>
      </div>
      <div class="section-block">
        <h4>Abstract</h4>
        <p>${renderLatexText(paper.abstract || "-")}</p>
      </div>
      <div class="section-block">
        <h4>Events</h4>
        <p>${escapeHtml((detail.events || []).map((event) => `${event.date} ${event.event_type} ${event.listing_category}`).join(" | ") || "-")}</p>
      </div>
      <div class="section-block">
        <h4>Summaries</h4>
        ${summaries.length ? summaries.map(renderSummary).join("") : '<p class="empty-state">No summaries.</p>'}
      </div>
    `;
    typesetMath(el("paper-content"));
  }

  function paperLink(paper) {
    return paper.abs_url || `https://arxiv.org/abs/${paper.arxiv_id}`;
  }

  function metadataNotice(paper) {
    if (paper.metadata_status === "complete" && !paper.metadata_error) return "";
    const parts = [`status: ${paper.metadata_status}`];
    if (paper.metadata_attempts) parts.push(`attempts: ${paper.metadata_attempts}`);
    if (paper.metadata_next_run_at) parts.push(`next_run_at: ${paper.metadata_next_run_at}`);
    if (paper.metadata_status === "retryable") parts.push("retryable");
    if (paper.metadata_error) parts.push(`error: ${paper.metadata_error}`);
    return `<div class="section-block metadata-notice"><h4>Metadata</h4><p>${escapeHtml(parts.join(" | "))}</p></div>`;
  }

  function renderSummary(summary) {
    return `
      <div class="summary-section">
        <div class="tag-row">
          <span class="tag">${escapeHtml(summary.template_name || `template ${summary.template_id}`)}</span>
          <span class="tag">${escapeHtml(summary.model)}</span>
          <span class="tag">${escapeHtml(summary.status)}</span>
        </div>
        <pre>${escapeHtml(JSON.stringify(summary.content, null, 2))}</pre>
      </div>
    `;
  }

  function renderDiscussions(messages) {
    el("discussion-count").textContent = String(messages.length);
    const list = el("discussion-list");
    list.innerHTML = "";
    if (!messages.length) {
      list.innerHTML = '<p class="empty-state">No discussion messages.</p>';
      return;
    }
    for (const message of messages) {
      const item = document.createElement("div");
      item.className = "discussion-message";
      item.innerHTML = `
        <strong>${escapeHtml(message.role)}</strong>
        <p>${escapeHtml(message.content)}</p>
        <div class="tag-row">${(message.tags || []).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div>
      `;
      list.appendChild(item);
    }
  }

  async function addDiscussion() {
    if (!state.selectedPaperId) {
      setStatus("Select a paper before adding a message");
      return;
    }
    const content = el("discussion-content").value.trim();
    if (!content) {
      setStatus("Message is empty");
      return;
    }
    const button = el("discussion-add");
    setBusy(button, true);
    try {
      await api(`/api/papers/${encodeURIComponent(state.selectedPaperId)}/discussions`, {
        method: "POST",
        body: JSON.stringify({
          role: el("discussion-role").value,
          content,
          tags: splitList(el("discussion-tags").value),
        }),
      });
      el("discussion-content").value = "";
      await loadPaper(state.selectedPaperId);
    } catch (error) {
      recordOperation(`Discussion failed: ${error.message}`);
    } finally {
      setBusy(button, false);
    }
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function bind() {
    el("date-input").value = todayIso();
    el("date-prev").addEventListener("click", () => changeDateByDays(-1));
    el("date-next").addEventListener("click", () => changeDateByDays(1));
    el("crawl-date-open").addEventListener("click", openDateCrawlDialog);
    el("crawl-date-confirm").addEventListener("click", confirmDateCrawl);
    el("crawl-date-cancel").addEventListener("click", closeDateCrawlDialog);
    el("crawl-date-dismiss").addEventListener("click", closeDateCrawlDialog);
    el("crawl-date-dialog").addEventListener("click", (event) => {
      if (event.target === el("crawl-date-dialog")) closeDateCrawlDialog();
    });
    el("status-refresh").addEventListener("click", () => {
      loadDailyStatus();
      runSearch({ silent: true });
    });
    el("date-input").addEventListener("change", () => {
      state.searchPage = 1;
      refreshSelectedDateView();
    });
    el("crawl-categories").addEventListener("keydown", (event) => {
      if (event.key === "Enter") startDailyAutomation();
    });
    el("template-editor-toggle").addEventListener("click", toggleTemplateEditor);
    el("summary-template-save").addEventListener("click", saveSummaryTemplate);
    el("summary-score-run").addEventListener("click", runSummaryAndScore);
    el("search-run").addEventListener("click", () => {
      state.searchPage = 1;
      runSearch();
    });
    el("search-scope").addEventListener("change", () => {
      state.searchPage = 1;
      runSearch();
    });
    el("pagination-prev").addEventListener("click", () => changeSearchPage(-1));
    el("pagination-next").addEventListener("click", () => changeSearchPage(1));
    el("discussion-add").addEventListener("click", addDiscussion);
    el("search-query").addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        state.searchPage = 1;
        runSearch();
      }
    });
    window.addEventListener("mathjax-ready", () => typesetMath(document.body));
    loadSummaryTemplates();
    refreshSelectedDateView();
    if (!state.automationTimer) {
      state.automationTimer = window.setInterval(() => {
        refreshSelectedDateView();
      }, AUTO_AUTOMATION_INTERVAL_MS);
    }
  }

  return {
    bind,
    runSearch,
    startDailyAutomation,
    runSummaryAndScore,
    loadDailyStatus,
    openDateCrawlDialog,
    confirmDateCrawl,
  };
})();

window.addEventListener("DOMContentLoaded", ArxivDailyWorkbench.bind);
