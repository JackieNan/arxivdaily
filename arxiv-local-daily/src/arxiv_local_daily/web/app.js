const ArxivDailyWorkbench = (() => {
  const state = {
    selectedPaperId: null,
    selectedCard: null,
    lastAudit: null,
    templates: [],
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
    setDetail("operation-log", detail ? `${message}\n${detail}` : message);
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

  function formatJson(value) {
    return JSON.stringify(value, null, 2);
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
        setDetail(
          "summary-template-help",
          `Template ${defaultTemplate.name} v${defaultTemplate.version} ready.`
        );
      } else {
        setDetail("summary-template-help", "Create a template before running summaries.");
      }
    } catch (error) {
      setDetail("summary-template-help", `Template load failed: ${error.message}`);
    }
  }

  async function createDefaultTemplate() {
    const button = el("summary-template-create");
    setBusy(button, true);
    try {
      const result = await api("/api/summary-templates", {
        method: "POST",
        body: JSON.stringify(DEFAULT_SUMMARY_TEMPLATE),
      });
      el("summary-template").value = DEFAULT_SUMMARY_TEMPLATE.name;
      setDetail(
        "summary-template-help",
        `Template ${DEFAULT_SUMMARY_TEMPLATE.name} v${result.version} ready.`
      );
      setDetail("settings-detail", formatJson(result));
      recordOperation(`Created summary template ${DEFAULT_SUMMARY_TEMPLATE.name}`, formatJson(result));
      await loadSummaryTemplates();
    } catch (error) {
      setDetail("summary-template-help", `Template create failed: ${error.message}`);
      setDetail("settings-detail", `Template create failed:\n${error.message}`);
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

  async function runCrawl() {
    const button = el("crawl-run");
    setBusy(button, true);
    try {
      const categories = splitList(el("crawl-categories").value);
      const body = { date: dateValue() };
      if (categories.length) body.categories = categories;
      const result = await api("/api/crawl/run", {
        method: "POST",
        body: JSON.stringify(body),
      });
      el("crawl-state").textContent = `run ${result.run_id}`;
      const suffix = result.metadata_enrich ? "; metadata enrich queued" : "";
      recordOperation(`Crawl run ${result.run_id} created${suffix}`, formatJson(result));
      await runAudit();
      await runSearch();
    } catch (error) {
      recordOperation(`Crawl failed: ${error.message}`);
      el("crawl-state").textContent = "failed";
    } finally {
      setBusy(button, false);
    }
  }

  async function runAudit() {
    const button = el("crawl-audit");
    setBusy(button, true);
    try {
      const report = await api(`/api/crawl/completeness/${encodeURIComponent(dateValue())}`);
      state.lastAudit = report;
      renderAudit(report);
      recordOperation(`Audit status: ${report.status}`, formatJson(report));
    } catch (error) {
      recordOperation(`Audit failed: ${error.message}`);
    } finally {
      setBusy(button, false);
    }
  }

  function renderAudit(report) {
    const cells = el("audit-summary").querySelectorAll("strong");
    cells[0].textContent = report.status;
    cells[0].className = `status-${report.status}`;
    cells[1].textContent = `${report.complete_category_count}/${report.expected_category_count}`;
    cells[2].textContent = String(report.retry_categories.length);
    el("crawl-state").textContent = report.status;
  }

  async function retryCrawl() {
    const button = el("crawl-retry");
    setBusy(button, true);
    try {
      const expected = splitList(el("crawl-categories").value);
      const body = { date: dateValue() };
      if (expected.length) body.expected_categories = expected;
      const result = await api("/api/crawl/retry-failed", {
        method: "POST",
        body: JSON.stringify(body),
      });
      recordOperation(`Retried ${result.retried} categories`, formatJson(result));
      await runAudit();
      await runSearch();
    } catch (error) {
      recordOperation(`Retry failed: ${error.message}`);
    } finally {
      setBusy(button, false);
    }
  }

  async function runSummary() {
    const button = el("summary-run");
    setBusy(button, true);
    try {
      const templateName = el("summary-template").value.trim();
      const body = {
        date: dateValue(),
        model: el("summary-model").value.trim() || "local",
      };
      if (templateName) body.template_name = templateName;
      const result = await api("/api/summaries/run", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setDetail("settings-detail", formatJson(result));
      recordOperation(`Summaries completed ${result.completed} of ${result.requested}`, formatJson(result));
      await runSearch({ silent: true });
    } catch (error) {
      const templateHint = error.message === "summary template not found"
        ? "\nCreate a default template or import your own template first."
        : "";
      setDetail("settings-detail", `Summary failed:\n${error.message}${templateHint}`);
      recordOperation(`Summary failed: ${error.message}`);
    } finally {
      setBusy(button, false);
    }
  }

  async function runScore() {
    const button = el("score-run");
    setBusy(button, true);
    try {
      const result = await api("/api/scores/run", {
        method: "POST",
        body: JSON.stringify({
          date: dateValue(),
          model: el("summary-model").value.trim() || "local",
        }),
      });
      setDetail("settings-detail", formatJson(result));
      recordOperation(`Scores completed ${result.completed} of ${result.requested}`, formatJson(result));
      await runSearch({ silent: true });
    } catch (error) {
      setDetail("settings-detail", `Score failed:\n${error.message}`);
      recordOperation(`Score failed: ${error.message}`);
    } finally {
      setBusy(button, false);
    }
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
    for (const [key, value] of pairs) {
      if (value) params.set(key, value);
    }
    return params;
  }

  function searchScopeLabel() {
    return el("search-scope").value === "daily" ? `当日 ${dateValue()}` : "总揽";
  }

  async function runSearch(options = {}) {
    const silent = options.silent === true;
    const button = el("search-run");
    setBusy(button, true);
    try {
      const data = await api(`/api/search/papers?${searchParams().toString()}`);
      renderResults(data.papers);
      el("result-count").textContent = String(data.count);
      const scope = searchScopeLabel();
      const detail = data.count
        ? `${scope}: showing ${data.count} papers.`
        : `${scope}: no matching papers with current filters.`;
      setDetail("search-detail", detail);
      if (!silent) recordOperation(`Search returned ${data.count} papers (${scope})`, detail);
    } catch (error) {
      setDetail("search-detail", `Search failed:\n${error.message}`);
      el("paper-results").innerHTML = `<p class="empty-state">Search failed: ${escapeHtml(error.message)}</p>`;
      if (!silent) recordOperation(`Search failed: ${error.message}`);
    } finally {
      setBusy(button, false);
    }
  }

  function renderResults(papers) {
    const container = el("paper-results");
    container.innerHTML = "";
    if (!papers.length) {
      container.innerHTML = '<p class="empty-state">No matching papers.</p>';
      return;
    }
    for (const paper of papers) {
      const card = document.createElement("button");
      card.type = "button";
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
        </div>
        <div class="tag-row">
          ${(paper.listing_categories || []).map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("")}
        </div>
        ${keywords.length
          ? `<div class="keyword-row" aria-label="中文关键词">${keywords.map((item) => `<span class="keyword-tag">${escapeHtml(item)}</span>`).join("")}</div>`
          : `<p class="paper-card-hint">${escapeHtml(keywordHint)}</p>`}
      `;
      card.addEventListener("click", () => selectPaper(paper.arxiv_id, card));
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
      recordOperation(`Loaded ${arxivId}`);
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
    el("crawl-run").addEventListener("click", runCrawl);
    el("crawl-audit").addEventListener("click", runAudit);
    el("crawl-retry").addEventListener("click", retryCrawl);
    el("summary-template-create").addEventListener("click", createDefaultTemplate);
    el("summary-run").addEventListener("click", runSummary);
    el("score-run").addEventListener("click", runScore);
    el("search-run").addEventListener("click", runSearch);
    el("search-scope").addEventListener("change", runSearch);
    el("discussion-add").addEventListener("click", addDiscussion);
    el("search-query").addEventListener("keydown", (event) => {
      if (event.key === "Enter") runSearch();
    });
    window.addEventListener("mathjax-ready", () => typesetMath(document.body));
    loadSummaryTemplates();
    runAudit();
    runSearch();
  }

  return { bind, runSearch, runAudit, runScore };
})();

window.addEventListener("DOMContentLoaded", ArxivDailyWorkbench.bind);
