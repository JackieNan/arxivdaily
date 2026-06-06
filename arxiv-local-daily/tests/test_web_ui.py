from fastapi.testclient import TestClient

from arxiv_local_daily.api import create_app


def test_root_serves_web_workbench(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "web.sqlite3"))

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "arXiv Daily Workbench" in response.text
    assert 'id="automation-panel"' in response.text
    assert 'id="date-prev"' in response.text
    assert 'id="date-next"' in response.text
    assert 'id="pipeline-status"' in response.text
    assert 'id="automation-status-state"' in response.text
    assert 'id="automation-status-count"' in response.text
    assert 'id="automation-status-detail"' in response.text
    assert 'id="paper-status-state"' in response.text
    assert 'id="paper-status-count"' in response.text
    assert 'id="paper-status-detail"' in response.text
    assert 'id="metadata-status-state"' in response.text
    assert 'id="metadata-status-count"' in response.text
    assert 'id="metadata-status-detail"' in response.text
    assert 'id="ai-status-state"' in response.text
    assert 'id="ai-status-count"' in response.text
    assert 'id="ai-status-detail"' in response.text
    assert 'id="automation-progress"' not in response.text
    assert 'id="paper-progress-fill"' not in response.text
    assert 'id="top-actions"' in response.text
    assert 'id="settings-panel"' in response.text
    assert 'id="crawl-panel"' not in response.text
    assert 'id="daily-panel"' not in response.text
    assert 'id="search-panel"' in response.text
    assert 'id="right-rail"' in response.text
    assert 'id="paper-detail"' in response.text
    assert 'id="discussion-panel"' in response.text
    assert 'id="search-detail"' in response.text
    assert 'id="operation-log"' in response.text
    assert 'id="template-editor-toggle"' in response.text
    assert 'id="template-editor"' in response.text
    assert 'id="summary-template-save"' in response.text
    assert 'id="summary-template-help"' in response.text
    assert 'id="summary-score-run"' in response.text
    assert 'id="ai-config-status"' in response.text
    assert 'id="paper-ai-run"' in response.text
    assert 'id="paper-prompt-preview"' in response.text
    assert 'id="paper-ai-status"' in response.text
    assert 'id="prompt-preview-dialog"' in response.text
    assert 'id="prompt-preview-content"' in response.text
    assert 'id="archive-scope-panel"' in response.text
    assert 'id="archive-scope-toggle"' in response.text
    assert 'id="archive-scope-status"' in response.text
    assert "Default scope: Computer Science" in response.text
    assert 'id="crawl-date-open"' in response.text
    assert "抓取指定日期" in response.text
    assert 'id="status-refresh"' in response.text
    assert "刷新状态" in response.text
    assert 'id="crawl-date-dialog"' in response.text
    assert 'id="crawl-date-target"' in response.text
    assert 'id="crawl-date-confirm"' in response.text
    assert "开始抓取" in response.text
    assert 'id="automation-refresh"' not in response.text
    assert "Refresh Status" not in response.text
    assert 'id="automation-summary"' in response.text
    assert 'id="automation-note"' in response.text
    assert "then runs AI summary and score" in response.text
    assert '<option value="historical">historical</option>' in response.text
    assert 'id="crawl-run"' not in response.text
    assert 'id="crawl-audit"' not in response.text
    assert 'id="crawl-retry"' not in response.text
    assert 'id="summary-run"' not in response.text
    assert 'id="score-run"' not in response.text
    assert 'id="daily-status-run"' not in response.text
    assert 'id="daily-pipeline-run"' not in response.text
    assert 'id="daily-detail"' not in response.text
    assert 'id="settings-detail"' not in response.text
    assert 'id="search-sort"' in response.text
    assert 'id="pagination-prev"' in response.text
    assert 'id="pagination-next"' in response.text
    assert 'id="pagination-label"' in response.text
    assert 'id="search-scope"' in response.text
    assert '<option value="daily" selected>当日</option>' in response.text
    assert '<option value="overview">总览</option>' in response.text
    assert "MathJax" in response.text
    assert "tex-chtml.js" in response.text
    assert "Settings" in response.text
    assert "Enrich" not in response.text
    assert 'id="left-rail"' not in response.text
    assert "Summary limit" not in response.text
    assert "Score limit" not in response.text


def test_static_web_assets_are_served(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "web.sqlite3"))

    js_response = client.get("/static/app.js")
    css_response = client.get("/static/styles.css")

    assert js_response.status_code == 200
    assert "ArxivDailyWorkbench" in js_response.text
    assert "readErrorMessage" in js_response.text
    assert "DEFAULT_SUMMARY_TEMPLATE" in js_response.text
    assert "loadSummaryTemplates" in js_response.text
    assert "toggleTemplateEditor" in js_response.text
    assert "saveSummaryTemplate" in js_response.text
    assert "readTemplateEditorFields" in js_response.text
    assert "runSummaryAndScore" in js_response.text
    assert "retryable" in js_response.text
    assert "next_run_at" in js_response.text
    assert "loadDailyStatus" in js_response.text
    assert "startDailyAutomation" in js_response.text
    assert "AUTO_AUTOMATION_INTERVAL_MS" in js_response.text
    assert "ACTIVE_AUTOMATION_POLL_MS" in js_response.text
    assert "window.setInterval" in js_response.text
    assert "state.automationTimer" in js_response.text
    assert "state.activeStatusTimer" in js_response.text
    assert "startActiveStatusPolling" in js_response.text
    assert "stopActiveStatusPolling" in js_response.text
    assert "syncActiveStatusPolling" in js_response.text
    assert "refreshSelectedDateView" in js_response.text
    assert "startDailyAutomation({ silent: true })" not in js_response.text
    assert "openDateCrawlDialog" in js_response.text
    assert "confirmDateCrawl" in js_response.text
    assert 'el("crawl-date-open").addEventListener("click", openDateCrawlDialog);' in js_response.text
    assert 'startDailyAutomation({ button: el("crawl-date-confirm") })' in js_response.text
    assert 'el("status-refresh")' in js_response.text
    assert "/api/daily/automation/start" in js_response.text
    assert "/api/daily/status/" in js_response.text
    assert "/api/preflight/" in js_response.text
    assert "/api/ai-triage/run" in js_response.text
    assert "/api/ai/config" in js_response.text
    assert "/api/ai/prompt-preview" in js_response.text
    assert '/ai-triage/run"' in js_response.text
    assert "loadAiConfig" in js_response.text
    assert "runSelectedPaperAi" in js_response.text
    assert "previewSelectedPaperPrompt" in js_response.text
    assert "renderPromptPreview" in js_response.text
    assert "renderSummaryContent" in js_response.text
    assert "CS_CATEGORIES" in js_response.text
    assert "state.archiveScope" in js_response.text
    assert "categoryScopeCategories" in js_response.text
    assert "body.categories = scopedCategories" in js_response.text
    assert 'el("archive-scope-toggle")' in js_response.text
    assert '"cs.AI"' in js_response.text
    assert '"cs.LG"' in js_response.text
    assert "/api/summaries/run" not in js_response.text
    assert "/api/scores/run" not in js_response.text
    assert "body.template_name = templateName" in js_response.text
    assert 'body.model = el("summary-model").value.trim() || "local";' in js_response.text
    assert 'body.crawl_mode = "auto";' in js_response.text
    assert "body.force_crawl = true" in js_response.text
    assert "shiftIsoDate" in js_response.text
    assert 'new Date(Date.UTC(year, month - 1, day + delta))' in js_response.text
    assert 'new Date(`${dateValue()}T00:00:00`)' not in js_response.text
    assert "changeDateByDays" in js_response.text
    assert 'el("date-prev")' in js_response.text
    assert 'el("date-next")' in js_response.text
    assert 'params.set("page", String(state.searchPage));' in js_response.text
    assert 'params.set("page_size", String(state.pageSize));' in js_response.text
    assert "renderPagination" in js_response.text
    assert "renderPipelineStatus" in js_response.text
    assert "renderStageStatus" in js_response.text
    assert "renderAutomationStatus" in js_response.text
    assert "AUTOMATION_STEP_LABELS" in js_response.text
    assert "crawl_incomplete" in js_response.text
    assert "result.automation_run_id" in js_response.text
    assert "status.automation" in js_response.text
    assert "preflightPaperTotal" in js_response.text
    assert "preflightStatusText" in js_response.text
    assert "paperStageStatus" in js_response.text
    assert "metadataStageStatus" in js_response.text
    assert "aiStageStatus" in js_response.text
    assert "renderPipelineProgress" not in js_response.text
    assert "renderProgressBar" not in js_response.text
    assert "metadataProgressCounts" not in js_response.text
    assert "aiProgressCounts" not in js_response.text
    assert "renderPaperCrawlProgress" not in js_response.text
    assert "renderAutomationProgress" not in js_response.text
    assert "metadataProgressState" not in js_response.text
    assert "aiProgressState" not in js_response.text
    assert "status.crawl.expected_paper_count" in js_response.text
    assert "status.preflight.distinct_paper_count" in js_response.text
    assert '"paper-status-state"' in js_response.text
    assert '"automation-status-state"' in js_response.text
    assert '"metadata-status-state"' in js_response.text
    assert '"ai-status-state"' in js_response.text
    assert "fill.style.width" not in js_response.text
    assert "paperLink" in js_response.text
    assert 'el("automation-refresh")' not in js_response.text
    assert 'el("crawl-run")' not in js_response.text
    assert 'el("daily-status-run")' not in js_response.text
    assert 'setDetail("daily-detail"' not in js_response.text
    assert 'setDetail("settings-detail"' not in js_response.text
    assert "status.metadata.failed" in js_response.text
    assert "status.crawl.complete_category_count" in js_response.text
    assert 'setDetail("operation-log", message);' in js_response.text
    assert 'detail ? `${message}\\n${detail}` : message' not in js_response.text
    assert "score-badge" in js_response.text
    assert "typesetMath" in js_response.text
    assert "renderLatexText" in js_response.text
    assert "math-fallback" in js_response.text
    assert "summary_keywords" in js_response.text
    assert "关键词" in js_response.text
    assert 'el("search-scope").value === "daily"' in js_response.text
    assert 'params.set("date", dateValue())' in js_response.text
    assert "总览" in js_response.text
    assert "Loaded ${arxivId}" not in js_response.text
    assert "Apple Chancery" not in css_response.text
    assert "Brush Script" not in css_response.text
    assert "Cambria Math" not in css_response.text
    assert 'font-family: Georgia, "Times New Roman", serif;' in css_response.text
    assert "font-style: normal;" in css_response.text
    assert '.math-hat::before' not in css_response.text
    assert 'paper.abstract || "No abstract yet."' not in js_response.text
    assert 'params.set("limit", "50")' not in js_response.text
    assert css_response.status_code == 200
    assert ".app-shell" in css_response.text
    assert ".operation-detail" in css_response.text
    assert ".workspace-grid" in css_response.text
    assert ".paper-card-title" in css_response.text
    assert ".right-rail" in css_response.text
    assert ".math-fallback" in css_response.text
    assert ".keyword-tag" in css_response.text
    assert "grid-template-columns: minmax(320px, 0.72fr) minmax(520px, 1.28fr);" in css_response.text
    assert "grid-template-columns: repeat(2, minmax(132px, 1fr));" in css_response.text
    assert ".top-actions .panel" in css_response.text
    assert ".top-actions button" in css_response.text
    assert ".automation-grid" in css_response.text
    assert ".automation-actions" in css_response.text
    assert ".compact-button" in css_response.text
    assert ".automation-summary" in css_response.text
    assert ".pipeline-status" in css_response.text
    assert ".stage-status" in css_response.text
    assert ".stage-badge" in css_response.text
    assert ".stage-count" in css_response.text
    assert ".stage-detail" in css_response.text
    assert ".automation-progress" not in css_response.text
    assert ".progress-track" not in css_response.text
    assert ".progress-row" not in css_response.text
    assert ".progress-fill" not in css_response.text
    assert ".progress-label" not in css_response.text
    assert ".progress-segment" not in css_response.text
    assert ".pagination-controls" in css_response.text
    assert ".source-link" in css_response.text
    assert ".template-editor" in css_response.text
    assert ".template-field-row" in css_response.text
    assert ".summary-score-grid" in css_response.text
    assert ".ai-config-card" in css_response.text
    assert ".ai-action-row" in css_response.text
    assert ".prompt-preview-content" in css_response.text
    assert ".summary-content" in css_response.text
    assert ".archive-scope-panel" in css_response.text
    assert ".archive-scope-actions" in css_response.text
    assert ".modal-backdrop" in css_response.text
    assert ".modal-panel" in css_response.text
    assert ".modal-actions" in css_response.text
    assert "#template-editor-toggle" in css_response.text
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in css_response.text
    assert "grid-column: 1 / -1;" in css_response.text
    assert "minmax(150px, 1fr) minmax(92px" not in css_response.text
    assert ".operation-log" in css_response.text
    assert "white-space: nowrap;" in css_response.text
    assert "max-height: 40px;" in css_response.text
    assert "@media (max-width: 420px)" in css_response.text
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in css_response.text
