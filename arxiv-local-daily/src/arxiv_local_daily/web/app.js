const ArxivDailyWorkbench = (() => {
  const state = {
    selectedPaperId: null,
    selectedCard: null,
    automationTimer: null,
    activeStatusTimer: null,
    searchPage: 1,
    pageSize: 50,
    pageMeta: null,
    archiveScope: "cs",
    searchCategories: null,
  };

  const AUTO_AUTOMATION_INTERVAL_MS = 10 * 60 * 1000;
  const ACTIVE_AUTOMATION_POLL_MS = 2500;

  const CS_CATEGORIES = [
    "cs.AI",
    "cs.AR",
    "cs.CC",
    "cs.CE",
    "cs.CG",
    "cs.CL",
    "cs.CR",
    "cs.CV",
    "cs.CY",
    "cs.DB",
    "cs.DC",
    "cs.DL",
    "cs.DM",
    "cs.DS",
    "cs.ET",
    "cs.FL",
    "cs.GL",
    "cs.GR",
    "cs.GT",
    "cs.HC",
    "cs.IR",
    "cs.IT",
    "cs.LG",
    "cs.LO",
    "cs.MA",
    "cs.MM",
    "cs.MS",
    "cs.NA",
    "cs.NE",
    "cs.NI",
    "cs.OH",
    "cs.OS",
    "cs.PF",
    "cs.PL",
    "cs.RO",
    "cs.SC",
    "cs.SD",
    "cs.SE",
    "cs.SI",
    "cs.SY",
  ];

  const CATEGORY_GROUPS = [
    { id: "cs", label: "计算机科学", categories: CS_CATEGORIES },
    { id: "math", label: "数学", categories: ["math.AC", "math.AG", "math.AP", "math.AT", "math.CA", "math.CO", "math.CT", "math.CV", "math.DG", "math.DS", "math.FA", "math.GM", "math.GN", "math.GR", "math.GT", "math.HO", "math.IT", "math.KT", "math.LO", "math.MG", "math.MP", "math.NA", "math.NT", "math.OA", "math.OC", "math.PR", "math.QA", "math.RA", "math.RT", "math.SG", "math.SP", "math.ST"] },
    { id: "stat", label: "统计学", categories: ["stat.AP", "stat.CO", "stat.ME", "stat.ML", "stat.OT", "stat.TH"] },
    { id: "physics", label: "物理", categories: ["physics.acc-ph", "physics.app-ph", "physics.atm-clus", "physics.atom-ph", "physics.bio-ph", "physics.chem-ph", "physics.class-ph", "physics.comp-ph", "physics.data-an", "physics.ed-ph", "physics.flu-dyn", "physics.gen-ph", "physics.geo-ph", "physics.hist-ph", "physics.ins-det", "physics.med-ph", "physics.optics", "physics.plasm-ph", "physics.pop-ph", "physics.soc-ph", "physics.space-ph"] },
    { id: "astro-ph", label: "天体物理", categories: ["astro-ph.CO", "astro-ph.EP", "astro-ph.GA", "astro-ph.HE", "astro-ph.IM", "astro-ph.SR"] },
    { id: "cond-mat", label: "凝聚态物理", categories: ["cond-mat.dis-nn", "cond-mat.mes-hall", "cond-mat.mtrl-sci", "cond-mat.other", "cond-mat.quant-gas", "cond-mat.soft", "cond-mat.stat-mech", "cond-mat.str-el", "cond-mat.supr-con"] },
    { id: "q-bio", label: "定量生物", categories: ["q-bio.BM", "q-bio.CB", "q-bio.GN", "q-bio.MN", "q-bio.NC", "q-bio.OT", "q-bio.PE", "q-bio.QM", "q-bio.SC", "q-bio.TO"] },
    { id: "q-fin", label: "定量金融", categories: ["q-fin.CP", "q-fin.EC", "q-fin.GN", "q-fin.MF", "q-fin.PM", "q-fin.PR", "q-fin.RM", "q-fin.ST", "q-fin.TR"] },
    { id: "econ", label: "经济学", categories: ["econ.EM", "econ.GN", "econ.TH"] },
    { id: "eess", label: "电气工程与系统科学", categories: ["eess.AS", "eess.IV", "eess.SP", "eess.SY"] },
    { id: "nlin", label: "非线性科学", categories: ["nlin.AO", "nlin.CD", "nlin.CG", "nlin.PS", "nlin.SI"] },
    { id: "quant-ph", label: "量子物理", categories: ["quant-ph"] },
    { id: "math-ph", label: "数学物理", categories: ["math-ph"] },
    { id: "gr-qc", label: "广义相对论与量子宇宙学", categories: ["gr-qc"] },
    { id: "hep", label: "高能物理", categories: ["hep-ex", "hep-lat", "hep-ph", "hep-th"] },
    { id: "nucl", label: "核物理", categories: ["nucl-ex", "nucl-th"] },
  ];

  const AUTOMATION_STEP_LABELS = {
    idle: "空闲",
    queued: "已排队",
    arxiv_date_check: "检查 arXiv 日期",
    preflight: "预检查",
    crawl: "抓取论文",
    crawl_already_complete: "抓取已完成",
    crawl_incomplete: "抓取未完成",
    metadata: "补齐元数据",
    ai: "AI 分析",
    waiting_for_arxiv_update: "等待 arXiv 更新",
    metadata_waiting: "等待元数据",
    no_papers: "无论文",
    complete: "完成",
    failed: "失败",
  };

  const STATUS_LABELS = {
    idle: "空闲",
    queued: "已排队",
    running: "运行中",
    waiting: "等待",
    partial: "部分完成",
    complete: "完成",
    failed: "失败",
    retryable: "可重试",
    pending: "待处理",
    not_started: "未开始",
    unknown: "未知",
  };

  const el = (id) => document.getElementById(id);

  function statusLabel(value) {
    return STATUS_LABELS[value] || value || "-";
  }

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

  function splitList(value) {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function manualCategories() {
    return splitList(el("crawl-categories").value);
  }

  function categoryScopeCategories() {
    const manual = manualCategories();
    if (manual.length) return manual;
    return state.archiveScope === "cs" ? CS_CATEGORIES : [];
  }

  function renderArchiveScope() {
    const manual = manualCategories();
    const isCsScope = state.archiveScope === "cs";
    const status = manual.length
      ? `手动分类覆盖默认范围：${manual.join(", ")}。`
      : isCsScope
        ? `未填写手动分类：抓取、状态和 AI 使用 ${CS_CATEGORIES.length} 个 cs.* 分类。`
        : "未填写手动分类：抓取、状态和 AI 使用全部 arXiv 大组。";
    el("archive-scope-status").textContent = status;
    el("archive-scope-toggle").textContent = isCsScope ? "抓取全部大组" : "恢复只抓取 CS";
  }

  function toggleArchiveScope() {
    state.archiveScope = state.archiveScope === "cs" ? "all" : "cs";
    renderArchiveScope();
    const scopeText = state.archiveScope === "cs" ? "仅计算机科学" : "全部 arXiv 大组";
    recordOperation(`默认范围已切换：${scopeText}`);
    refreshSelectedDateView();
  }

  function allCategoryCodes() {
    return CATEGORY_GROUPS.flatMap((group) => group.categories);
  }

  function selectedCategorySet() {
    if (!(state.searchCategories instanceof Set)) {
      state.searchCategories = new Set(CS_CATEGORIES);
    }
    return state.searchCategories;
  }

  function selectedSearchCategories() {
    const selected = selectedCategorySet();
    const ordered = allCategoryCodes().filter((category) => selected.has(category));
    const extra = [...selected].filter((category) => !ordered.includes(category)).sort();
    return [...ordered, ...extra];
  }

  function setSelectedSearchCategories(categories) {
    state.searchCategories = new Set(categories);
    state.searchPage = 1;
    renderCategoryPicker();
    runSearch();
  }

  function selectedCategoriesLabel() {
    const selected = selectedSearchCategories();
    if (!selected.length) return "全部分类";
    if (selected.length === CS_CATEGORIES.length && CS_CATEGORIES.every((category) => selected.includes(category))) {
      return `计算机科学 (${selected.length})`;
    }
    const fullGroups = CATEGORY_GROUPS.filter((group) => group.categories.every((category) => selected.includes(category)));
    if (fullGroups.length === 1 && fullGroups[0].categories.length === selected.length) {
      return `${fullGroups[0].label} (${selected.length})`;
    }
    return `已选 ${selected.length} 个分类`;
  }

  function categoryGroupSelectionState(group, selected) {
    const count = group.categories.filter((category) => selected.has(category)).length;
    return {
      count,
      checked: count === group.categories.length,
      indeterminate: count > 0 && count < group.categories.length,
    };
  }

  function renderCategoryPicker() {
    const selected = selectedCategorySet();
    const toggle = el("category-picker-toggle");
    toggle.textContent = selectedCategoriesLabel();
    const groupsNode = el("category-picker-groups");
    groupsNode.innerHTML = CATEGORY_GROUPS.map((group) => {
      const groupState = categoryGroupSelectionState(group, selected);
      const categories = group.categories
        .map((category) => `
          <label class="category-option">
            <input type="checkbox" data-category-code="${escapeHtml(category)}" ${selected.has(category) ? "checked" : ""}>
            <span>${escapeHtml(category)}</span>
          </label>
        `)
        .join("");
      return `
        <details class="category-group" ${groupState.count ? "open" : ""}>
          <summary>
            <label class="category-group-check">
              <input type="checkbox" data-category-group="${escapeHtml(group.id)}" ${groupState.checked ? "checked" : ""}>
              <span>${escapeHtml(group.label)}</span>
              <em>${groupState.count}/${group.categories.length}</em>
            </label>
          </summary>
          <div class="category-options">${categories}</div>
        </details>
      `;
    }).join("");
    groupsNode.querySelectorAll("input[data-category-group]").forEach((input) => {
      const group = CATEGORY_GROUPS.find((item) => item.id === input.dataset.categoryGroup);
      const groupState = group ? categoryGroupSelectionState(group, selected) : { indeterminate: false };
      input.indeterminate = groupState.indeterminate;
      input.addEventListener("click", (event) => event.stopPropagation());
      input.addEventListener("change", () => {
        if (!group) return;
        const next = new Set(selectedCategorySet());
        group.categories.forEach((category) => {
          if (input.checked) next.add(category);
          else next.delete(category);
        });
        setSelectedSearchCategories([...next]);
      });
    });
    groupsNode.querySelectorAll("input[data-category-code]").forEach((input) => {
      input.addEventListener("change", () => {
        const next = new Set(selectedCategorySet());
        if (input.checked) next.add(input.dataset.categoryCode);
        else next.delete(input.dataset.categoryCode);
        setSelectedSearchCategories([...next]);
      });
    });
  }

  function toggleCategoryPicker() {
    const picker = el("category-picker");
    const nextHidden = !picker.hidden;
    picker.hidden = nextHidden;
    el("category-picker-toggle").setAttribute("aria-expanded", String(!nextHidden));
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
      const scopedCategories = categoryScopeCategories();
      const body = { date: dateValue() };
      if (scopedCategories.length) body.categories = scopedCategories;
      body.crawl_mode = "auto";
      body.force_crawl = true;
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
      el("automation-state").textContent = statusLabel(result.status);
      startActiveStatusPolling();
      await loadDailyStatus({ silent: true });
      await runSearch({ silent: true });
      if (!silent) recordOperation(`抓取 ${dateValue()} ${statusLabel(result.status)}；后台任务 #${result.automation_run_id}`);
    } catch (error) {
      el("automation-state").textContent = "失败";
      setDetail("automation-note", `自动化失败：${error.message}`);
      if (!silent) recordOperation(`抓取失败：${error.message}`);
    } finally {
      setBusy(button, false);
    }
  }

  function summaryRequestBody() {
    return {
      date: dateValue(),
      categories: CS_CATEGORIES,
    };
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
        ? "LLM API 未配置"
        : `AI 分析 ${triage.completed}/${triage.requested}；失败 ${triage.failed}`;
      setDetail("automation-note", message);
      recordOperation(message);
      await loadDailyStatus({ silent: true });
      await runSearch({ silent: true });
    } catch (error) {
      setDetail("automation-note", `总结/评分失败：${error.message}。`);
      recordOperation(`总结/评分失败：${error.message}`);
    } finally {
      setBusy(button, false);
    }
  }

  function setPaperAiControlsEnabled(enabled) {
    el("paper-ai-run").disabled = !enabled;
    el("paper-prompt-preview").disabled = !enabled;
  }

  function setPaperAiStatus(message) {
    setDetail("paper-ai-status", message);
  }

  async function runSelectedPaperAi() {
    if (!state.selectedPaperId) {
      setPaperAiStatus("请先选择论文，再运行 AI。");
      return;
    }
    const button = el("paper-ai-run");
    setBusy(button, true);
    try {
      const body = { force: true };
      const result = await api(`/api/papers/${encodeURIComponent(state.selectedPaperId)}/ai-triage/run`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      const message = paperAiResultMessage(result);
      setPaperAiStatus(message);
      recordOperation(message);
      await loadDailyStatus({ silent: true });
      await runSearch({ silent: true });
      await loadPaper(state.selectedPaperId);
      setPaperAiStatus(message);
    } catch (error) {
      const message = `单篇 AI 失败：${error.message}`;
      setPaperAiStatus(message);
      recordOperation(message);
    } finally {
      setBusy(button, false);
    }
  }

  function paperAiResultMessage(result) {
    if (result.status === "not_configured") {
      return "AI API 未配置。请创建 config/llm.local.json，或设置 LLM 环境变量。";
    }
    if (result.status === "not_eligible") {
      return "当前论文需要完整元数据和摘要后才能运行 AI。";
    }
    if (result.status === "skipped") {
      return "当前论文在现有 AI 配置下已经有完整总结和评分。";
    }
    if (result.status === "complete") {
      return `${result.arxiv_id} 的 AI 分析已完成。`;
    }
    if (result.status === "failed") {
      return `${result.arxiv_id} 的 AI 分析失败：${result.error || "未知错误"}`;
    }
    return `${result.arxiv_id || state.selectedPaperId} 的 AI 状态：${result.status ? statusLabel(result.status) : "已结束"}。`;
  }

  async function previewSelectedPaperPrompt() {
    if (!state.selectedPaperId) {
      setPaperAiStatus("请先选择论文，再预览提示词。");
      return;
    }
    const button = el("paper-prompt-preview");
    setBusy(button, true);
    try {
      const data = await api("/api/ai/prompt-preview", {
        method: "POST",
        body: JSON.stringify({
          arxiv_id: state.selectedPaperId,
        }),
      });
      renderPromptPreview(data);
      setPaperAiStatus(`${state.selectedPaperId} 的提示词已生成。`);
    } catch (error) {
      const message = `提示词预览失败：${error.message}`;
      setPaperAiStatus(message);
      recordOperation(message);
    } finally {
      setBusy(button, false);
    }
  }

  function renderPromptPreview(data) {
    const header = [
      `论文：${data.paper.arxiv_id} · ${data.paper.title || "-"}`,
      `语言/输入范围：${data.template.language} · ${data.template.input_scope}`,
      `总结字段：${(data.summary_keys || []).join(", ") || "-"}`,
      `评分字段：${(data.score_keys || []).join(", ") || "-"}`,
    ].join("\n");
    const messages = (data.messages || [])
      .map((message) => `[${message.role}]\n${message.content}`)
      .join("\n\n");
    el("prompt-preview-content").textContent = `${header}\n\n${messages}`;
    openPromptPreviewDialog();
  }

  function openPromptPreviewDialog() {
    el("prompt-preview-dialog").hidden = false;
  }

  function closePromptPreviewDialog() {
    el("prompt-preview-dialog").hidden = true;
  }

  function dailyStatusParams() {
    const params = new URLSearchParams();
    const scopedCategories = categoryScopeCategories();
    scopedCategories.forEach((category) => params.append("categories", category));
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
      if (!silent) recordOperation(`每日状态：${dailyStatusText(status)}`);
      return status;
    } catch (error) {
      el("automation-state").textContent = "失败";
      setDetail("automation-note", `每日状态刷新失败：${error.message}`);
      if (!silent) recordOperation(`每日状态刷新失败：${error.message}`);
      return null;
    } finally {
      setBusy(button, false);
    }
  }

  function renderDailyStatus(status) {
    const ai = status.ai || {};
    const aiComplete = Number(ai.complete || 0);
    const aiEligible = Number(ai.eligible || 0);
    el("daily-status-summary").textContent = `论文 ${status.metadata.total}；AI ${aiComplete}/${aiEligible}`;
    setDetail("automation-note", dailyStatusText(status));
    el("automation-state").textContent = statusLabel(status.status);
    el("automation-state").className = `badge status-${status.status}`;
    renderDailyStatusRows(status);
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

  function renderDailyStatusRows(status) {
    renderAutomationStatus(status.automation || {});

    const papers = paperStageStatus(status);
    updateStatusRow({
      stateId: "paper-status-state",
      countId: "paper-status-count",
      detailId: "paper-status-detail",
      ...papers,
    });

    const metadata = metadataStageStatus(status);
    updateStatusRow({
      stateId: "metadata-status-state",
      countId: "metadata-status-count",
      detailId: "metadata-status-detail",
      ...metadata,
    });

    const ai = aiStageStatus(status);
    updateStatusRow({
      stateId: "ai-status-state",
      countId: "ai-status-count",
      detailId: "ai-status-detail",
      ...ai,
    });
  }

  function updateStatusRow({ stateId, countId, detailId, state, count, detail }) {
    const stateNode = el(stateId);
    stateNode.textContent = statusLabel(state);
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
      ? `步骤：${stepLabel}${automation.updated_at ? `；更新于 ${automation.updated_at}` : ""}。`
      : "暂无后台自动化任务。";
    if (automation.error) detail = `${detail} 错误：${automation.error}`;
    updateStatusRow({
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
    const scopedTotal = Number(status.metadata.total || 0);
    const visibleComplete = scopedTotal || parsed;
    const total = scopedTotal || expected || preflightTotal || parsed;
    const state = paperStageState(status, visibleComplete, total);
    const count = total > 0 ? `${Math.min(visibleComplete, total)}/${total}` : "-";
    let detail = "尚未开始论文抓取。";
    if (status.automation?.status === "queued" || status.automation?.current_step === "crawl") {
      detail = `后台正在${AUTOMATION_STEP_LABELS[status.automation.current_step] || statusLabel(status.automation.status)}。`;
    } else if (status.automation?.current_step === "crawl_already_complete") {
      detail = "后台已跳过抓取：最新抓取审计已经完成。";
    } else if (status.automation?.current_step === "preflight") {
      detail = "后台正在抓取前核对 listing 数量。";
    } else if (status.automation?.current_step === "crawl_incomplete") {
      detail = `后台在抓取未完成后停止：${status.automation.error || "抓取没有完成"}。`;
    } else if (status.automation?.status === "failed") {
      detail = `后台失败：${status.automation.error || "未知错误"}。`;
    } else if (status.automation?.status === "waiting") {
      detail = status.automation.error || "后台正在等待外部条件。";
    } else if (status.automation?.current_step === "no_papers") {
      detail = "后台已完成；当前日期在本地抓取中没有论文。";
    } else if (status.crawl.status === "waiting") {
      detail = "正在等待 arXiv 发布请求日期的 listing。";
    } else if (status.preflight?.status === "complete") {
      detail = scopedTotal
        ? `当前范围有 ${scopedTotal} 篇论文；预检查证据 ${preflightEvidenceUrl()}。`
        : `预检查完成；证据 ${preflightEvidenceUrl()}。`;
    } else if (status.preflight?.status && status.preflight.status !== "not_started") {
      detail = `预检查${statusLabel(status.preflight.status)}；证据 ${preflightEvidenceUrl()}。`;
    } else if (parsed || expected) {
      detail = `当前日期抓取状态：${statusLabel(status.crawl.status || "unknown")}。`;
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
    if (failed) detailParts.push(`${failed} 个失败`);
    if (retryable) detailParts.push(`${retryable} 个可重试`);
    const detail = total
      ? `${complete} 条元数据已完成${detailParts.length ? `；${detailParts.join("；")}` : ""}。`
      : "暂无元数据候选论文。";
    return { state, count: total > 0 ? `${complete}/${total}` : "-", detail };
  }

  function aiStageStatus(status) {
    const ai = status.ai || {};
    const fallbackTotal = Math.max(Number(status.summary.eligible || 0), Number(status.score.eligible || 0));
    const fallbackComplete = Math.min(Number(status.summary.complete || 0), Number(status.score.complete || 0));
    const total = Number(ai.eligible ?? fallbackTotal);
    const complete = Number(ai.complete ?? fallbackComplete);
    const failed = Number(ai.failed ?? 0);
    let state = "running";
    if (!total) state = status.summary.template_missing ? "waiting" : "idle";
    else if (complete === total) state = "complete";
    else if (failed || Number(status.summary.failed || 0) || Number(status.score.failed || 0)) state = "failed";
    else if (status.summary.template_missing) state = "waiting";
    const failures = failed || Number(status.summary.failed || 0) + Number(status.score.failed || 0);
    let detail = total
      ? `${complete}/${total} 篇论文已有总结和评分。`
      : "暂无 AI 候选论文。";
    if (status.summary.template_missing) detail = `${detail} 模版缺失。`;
    if (failures) detail = `${detail} ${failures} 个失败。`;
    return { state, count: total > 0 ? `${complete}/${total}` : "-", detail };
  }

  function metadataCoverageText(status, options = {}) {
    if (options.compact) return `${status.metadata.complete}/${status.metadata.total}`;
    const failed = status.metadata.failed ? `；失败 ${status.metadata.failed}` : "";
    return `${status.metadata.complete}/${status.metadata.total} 完成${failed}`;
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
      return `预检查未开始（${preflightEvidenceUrl()}）。`;
    }
    const sourcePart = `${preflight.source_count || 0}/${preflight.category_count || 0} 个分类`;
    const paperPart = `${status.preflight.distinct_paper_count || 0} 篇去重论文`;
    const errorPart = preflight.status === "complete"
      ? "声明数量全部匹配"
      : `错误 ${JSON.stringify(preflight.error_counts || {})}`;
    return `预检查${statusLabel(preflight.status)}：${paperPart}，${sourcePart}，${errorPart}。证据：${preflightEvidenceUrl()}。`;
  }

  function dailyStatusText(status) {
    const ai = status.ai || {};
    const aiComplete = Number(ai.complete || 0);
    const aiEligible = Number(ai.eligible || 0);
    const blockers = status.blockers && status.blockers.length
      ? `阻塞项：${status.blockers.join(", ")}。`
      : "无阻塞项。";
    return `论文 ${status.metadata.total}；元数据 ${metadataCoverageText(status)}；AI ${aiComplete}/${aiEligible}。${preflightStatusText(status)} ${blockers}`;
  }

  function searchParams() {
    const params = new URLSearchParams();
    const pairs = [
      ["q", el("search-query").value.trim()],
      ["sort", el("search-sort").value],
    ];
    if (el("search-scope").value === "daily") {
      params.set("date", dateValue());
    }
    params.set("page", String(state.searchPage));
    params.set("page_size", String(state.pageSize));
    selectedSearchCategories().forEach((category) => params.append("category", category));
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
        ? `${scope}：第 ${data.page || 1}/${data.total_pages || 1} 页，显示 ${data.count}/${total} 篇论文。`
        : `${scope}：当前筛选条件下没有匹配论文。`;
      setDetail("search-detail", detail);
      if (!silent) recordOperation(`搜索返回 ${total} 篇论文（${scope}）`, detail);
    } catch (error) {
      setDetail("search-detail", `搜索失败：\n${error.message}`);
      el("paper-results").innerHTML = `<p class="empty-state">搜索失败：${escapeHtml(error.message)}</p>`;
      if (!silent) recordOperation(`搜索失败：${error.message}`);
    } finally {
      setBusy(button, false);
    }
  }

  function renderPagination(data) {
    const page = data.page || 1;
    const totalPages = data.total_pages || 1;
    const total = data.total ?? data.count ?? 0;
    el("pagination-label").textContent = `第 ${page} / ${totalPages} 页 · ${total} 篇`;
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
      container.innerHTML = '<p class="empty-state">没有匹配论文。</p>';
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
        ? `元数据：${paper.metadata_error}`
        : "尚无中文关键词，运行 AI 总结后生成。";
      card.innerHTML = `
        <div class="paper-card-head">
          <h3 class="paper-card-title">${renderLatexText(paper.title || paper.arxiv_id)}</h3>
          ${score ? `<span class="score-badge">${escapeHtml(score.score_total)} ${escapeHtml(score.recommended_action)}</span>` : ""}
        </div>
        <div class="paper-meta">
          <span class="tag">${escapeHtml(paper.arxiv_id)}</span>
          <span class="tag">${escapeHtml(statusLabel(paper.metadata_status))}</span>
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
    setPaperAiControlsEnabled(true);
    setPaperAiStatus(`${arxivId} 已选择，可运行 AI。`);
    await loadPaper(arxivId);
  }

  async function loadPaper(arxivId) {
    try {
      const detail = await api(`/api/papers/${encodeURIComponent(arxivId)}`);
      el("paper-id").textContent = arxivId;
      renderPaperDetail(detail);
      renderDiscussions(detail.discussions || []);
    } catch (error) {
      recordOperation(`论文加载失败：${error.message}`);
    }
  }

  function renderPaperDetail(detail) {
    const paper = detail.paper;
    if (!paper) {
      el("paper-content").innerHTML = '<p class="empty-state">未找到论文。</p>';
      setPaperAiControlsEnabled(false);
      setPaperAiStatus("未找到论文。");
      return;
    }
    const summaries = detail.summaries || [];
    const score = detail.score;
    setPaperAiControlsEnabled(true);
    setPaperAiStatus(score ? `最新评分 ${score.score_total} ${score.recommended_action}。` : "可以预览提示词或运行 AI。");
    el("paper-content").innerHTML = `
      <div class="paper-hero">
        <h3>${renderLatexText(paper.title || paper.arxiv_id)}</h3>
        ${score ? `<span class="score-badge large">${escapeHtml(score.score_total)} ${escapeHtml(score.recommended_action)}</span>` : ""}
      </div>
      <div class="tag-row compact-tags">
        <span class="tag">${escapeHtml(paper.arxiv_id)}</span>
        <span class="tag">${escapeHtml(statusLabel(paper.metadata_status))}</span>
        <a class="source-link" href="${escapeHtml(paperLink(paper))}" target="_blank" rel="noopener">arXiv 原文</a>
        ${(paper.categories || []).map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("")}
      </div>
      ${metadataNotice(paper)}
      ${score ? `<div class="section-block score-block"><h4>评分</h4><p>${escapeHtml(score.rationale)}</p></div>` : ""}
      <div class="section-block">
        <h4>作者</h4>
        <p>${escapeHtml((paper.authors || []).join(", ") || "-")}</p>
      </div>
      <div class="section-block">
        <h4>摘要</h4>
        <p>${renderLatexText(paper.abstract || "-")}</p>
      </div>
      <div class="section-block">
        <h4>事件</h4>
        <p>${escapeHtml((detail.events || []).map((event) => `${event.date} ${event.event_type} ${event.listing_category}`).join(" | ") || "-")}</p>
      </div>
      <div class="section-block">
        <h4>总结</h4>
        ${summaries.length ? summaries.map(renderSummary).join("") : '<p class="empty-state">暂无总结。</p>'}
      </div>
    `;
    typesetMath(el("paper-content"));
  }

  function paperLink(paper) {
    return paper.abs_url || `https://arxiv.org/abs/${paper.arxiv_id}`;
  }

  function metadataNotice(paper) {
    if (paper.metadata_status === "complete" && !paper.metadata_error) return "";
    const parts = [`状态：${statusLabel(paper.metadata_status)}`];
    if (paper.metadata_attempts) parts.push(`尝试次数：${paper.metadata_attempts}`);
    if (paper.metadata_next_run_at) parts.push(`下次运行：${paper.metadata_next_run_at}`);
    if (paper.metadata_status === "retryable") parts.push("可重试");
    if (paper.metadata_error) parts.push(`错误：${paper.metadata_error}`);
    return `<div class="section-block metadata-notice"><h4>元数据</h4><p>${escapeHtml(parts.join(" | "))}</p></div>`;
  }

  function renderSummary(summary) {
    return `
      <div class="summary-section">
        <div class="tag-row">
          <span class="tag">${escapeHtml(statusLabel(summary.status))}</span>
        </div>
        <div class="summary-content">${renderSummaryContent(summary.content || {})}</div>
      </div>
    `;
  }

  function renderSummaryContent(content) {
    const entries = Object.entries(content || {});
    if (!entries.length) return '<p class="empty-state">空总结。</p>';
    return entries.map(([key, value]) => renderSummaryField(key, value)).join("");
  }

  function renderSummaryField(key, value) {
    return `
      <section class="summary-field">
        <h5>${escapeHtml(key)}</h5>
        ${renderSummaryValue(value)}
      </section>
    `;
  }

  function renderSummaryValue(value) {
    if (Array.isArray(value)) {
      if (!value.length) return '<p class="empty-state">-</p>';
      return `<ul>${value.map((item) => `<li>${renderSummaryValueInline(item)}</li>`).join("")}</ul>`;
    }
    if (value && typeof value === "object") {
      return `<pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
    }
    return `<p>${renderSummaryValueInline(value)}</p>`;
  }

  function renderSummaryValueInline(value) {
    return renderLatexText(value ?? "-");
  }

  function renderDiscussions(messages) {
    el("discussion-count").textContent = String(messages.length);
    const list = el("discussion-list");
    list.innerHTML = "";
    if (!messages.length) {
      list.innerHTML = '<p class="empty-state">暂无讨论消息。</p>';
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
      setStatus("请先选择论文，再添加消息");
      return;
    }
    const content = el("discussion-content").value.trim();
    if (!content) {
      setStatus("消息为空");
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
      recordOperation(`讨论保存失败：${error.message}`);
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
    el("prompt-preview-close").addEventListener("click", closePromptPreviewDialog);
    el("prompt-preview-dismiss").addEventListener("click", closePromptPreviewDialog);
    el("prompt-preview-dialog").addEventListener("click", (event) => {
      if (event.target === el("prompt-preview-dialog")) closePromptPreviewDialog();
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
    el("crawl-categories").addEventListener("input", renderArchiveScope);
    el("archive-scope-toggle").addEventListener("click", toggleArchiveScope);
    el("summary-score-run").addEventListener("click", runSummaryAndScore);
    el("paper-ai-run").addEventListener("click", runSelectedPaperAi);
    el("paper-prompt-preview").addEventListener("click", previewSelectedPaperPrompt);
    el("category-picker-toggle").addEventListener("click", toggleCategoryPicker);
    el("category-select-cs").addEventListener("click", () => setSelectedSearchCategories(CS_CATEGORIES));
    el("category-select-all").addEventListener("click", () => setSelectedSearchCategories(allCategoryCodes()));
    el("category-clear").addEventListener("click", () => setSelectedSearchCategories([]));
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
    renderArchiveScope();
    renderCategoryPicker();
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
    runSelectedPaperAi,
    previewSelectedPaperPrompt,
    renderPromptPreview,
    loadDailyStatus,
    openDateCrawlDialog,
    confirmDateCrawl,
  };
})();

window.addEventListener("DOMContentLoaded", ArxivDailyWorkbench.bind);
