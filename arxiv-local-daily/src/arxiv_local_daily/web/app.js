const ArxivDailyWorkbench = (() => {
  const state = {
    selectedPaperId: null,
    selectedCard: null,
    lastAudit: null,
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
      recordOperation(`Crawl run ${result.run_id} created`, formatJson(result));
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

  async function runMetadata() {
    const button = el("metadata-run");
    setBusy(button, true);
    try {
      const result = await api("/api/metadata/run", {
        method: "POST",
        body: JSON.stringify({
          date: dateValue(),
          limit: Number(el("metadata-limit").value || 100),
        }),
      });
      el("enrich-state").textContent = `${result.updated}/${result.requested}`;
      setDetail("enrich-detail", formatJson(result));
      recordOperation(`Metadata updated ${result.updated} of ${result.requested}`, formatJson(result));
      await runSearch();
    } catch (error) {
      setDetail("enrich-detail", `Metadata failed:\n${error.message}`);
      recordOperation(`Metadata failed: ${error.message}`);
      el("enrich-state").textContent = "failed";
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
        limit: Number(el("summary-limit").value || 20),
      };
      if (templateName) body.template_name = templateName;
      const result = await api("/api/summaries/run", {
        method: "POST",
        body: JSON.stringify(body),
      });
      el("enrich-state").textContent = `${result.completed}/${result.requested}`;
      setDetail("enrich-detail", formatJson(result));
      recordOperation(`Summaries completed ${result.completed} of ${result.requested}`, formatJson(result));
      await runSearch();
    } catch (error) {
      setDetail("enrich-detail", `Summary failed:\n${error.message}`);
      recordOperation(`Summary failed: ${error.message}`);
      el("enrich-state").textContent = "failed";
    } finally {
      setBusy(button, false);
    }
  }

  function searchParams() {
    const params = new URLSearchParams();
    const pairs = [
      ["q", el("search-query").value.trim()],
      ["date", dateValue()],
      ["category", el("search-category").value.trim()],
      ["event_type", el("search-event").value],
      ["metadata_status", el("search-metadata").value],
      ["summary_status", el("search-summary").value],
    ];
    for (const [key, value] of pairs) {
      if (value) params.set(key, value);
    }
    params.set("limit", "50");
    return params;
  }

  async function runSearch() {
    const button = el("search-run");
    setBusy(button, true);
    try {
      const data = await api(`/api/search/papers?${searchParams().toString()}`);
      renderResults(data.papers);
      el("result-count").textContent = String(data.count);
      const detail = data.count
        ? `Showing ${data.count} papers for ${dateValue()}.`
        : `No matching papers for ${dateValue()} with current filters.`;
      setDetail("search-detail", detail);
      recordOperation(`Search returned ${data.count} papers`, detail);
    } catch (error) {
      setDetail("search-detail", `Search failed:\n${error.message}`);
      el("paper-results").innerHTML = `<p class="empty-state">Search failed: ${escapeHtml(error.message)}</p>`;
      recordOperation(`Search failed: ${error.message}`);
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
      card.innerHTML = `
        <h3>${escapeHtml(paper.title || paper.arxiv_id)}</h3>
        <div class="paper-meta">
          <span class="tag">${escapeHtml(paper.arxiv_id)}</span>
          <span class="tag">${escapeHtml(paper.metadata_status)}</span>
          <span class="tag">${escapeHtml(paper.latest_date || "-")}</span>
        </div>
        <div class="tag-row">
          ${(paper.listing_categories || []).map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("")}
        </div>
      `;
      card.addEventListener("click", () => selectPaper(paper.arxiv_id, card));
      container.appendChild(card);
    }
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
    el("paper-content").innerHTML = `
      <h3>${escapeHtml(paper.title || paper.arxiv_id)}</h3>
      <div class="tag-row">
        <span class="tag">${escapeHtml(paper.metadata_status)}</span>
        ${(paper.categories || []).map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("")}
      </div>
      <div class="section-block">
        <h4>Authors</h4>
        <p>${escapeHtml((paper.authors || []).join(", ") || "-")}</p>
      </div>
      <div class="section-block">
        <h4>Abstract</h4>
        <p>${escapeHtml(paper.abstract || "-")}</p>
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
    el("metadata-run").addEventListener("click", runMetadata);
    el("summary-run").addEventListener("click", runSummary);
    el("search-run").addEventListener("click", runSearch);
    el("discussion-add").addEventListener("click", addDiscussion);
    el("search-query").addEventListener("keydown", (event) => {
      if (event.key === "Enter") runSearch();
    });
    runAudit();
    runSearch();
  }

  return { bind, runSearch, runAudit };
})();

window.addEventListener("DOMContentLoaded", ArxivDailyWorkbench.bind);
