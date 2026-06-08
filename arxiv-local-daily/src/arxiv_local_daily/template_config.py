from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from arxiv_local_daily.models import SummaryTemplateField, SummaryTemplateInput

SINGLE_SUMMARY_TEMPLATE_NAME = "single_summary_template"
DEFAULT_SUMMARY_TEMPLATE_CONFIG_PATH = Path("config/summary_template.local.json")


def default_summary_template() -> SummaryTemplateInput:
    return SummaryTemplateInput(
        name=SINGLE_SUMMARY_TEMPLATE_NAME,
        language="Chinese",
        system_prompt="你是本地 arXiv 论文阅读数据库的中文研究助理。请用简洁中文总结论文，只返回 JSON。",
        input_scope="abstract",
        is_default=True,
        fields=[
            SummaryTemplateField(
                key="keywords",
                label="关键词",
                order=1,
                prompt="提炼 5-8 个中文关键词。保留必要英文术语、模型名和 LaTeX 符号。",
                field_type="keywords",
            ),
            SummaryTemplateField(
                key="tldr",
                label="一句话结论",
                order=2,
                prompt="用一句中文概括论文的核心贡献。",
                field_type="short_sentence",
            ),
            SummaryTemplateField(
                key="method",
                label="核心方法",
                order=3,
                prompt="用 2-3 个中文要点解释核心方法。",
                field_type="bullets",
            ),
            SummaryTemplateField(
                key="value",
                label="阅读价值",
                order=4,
                prompt="用中文说明为什么这篇论文值得阅读或暂时跳过。",
                field_type="bullets",
            ),
            SummaryTemplateField(
                key="limits",
                label="局限",
                order=5,
                prompt="用中文列出明显局限、缺失证据或需要进一步确认的点。",
                field_type="bullets",
            ),
        ],
    )


def summary_template_config_path() -> Path:
    return Path(os.getenv("ARXIV_DAILY_SUMMARY_TEMPLATE_CONFIG", str(DEFAULT_SUMMARY_TEMPLATE_CONFIG_PATH)))


def load_single_summary_template(path: Path | None = None) -> SummaryTemplateInput:
    config_path = path or summary_template_config_path()
    if not config_path.exists():
        return default_summary_template()
    payload = json.loads(config_path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("summary template config file must contain a JSON object")
    values: dict[str, Any] = {
        **payload,
        "name": SINGLE_SUMMARY_TEMPLATE_NAME,
        "is_default": True,
    }
    return SummaryTemplateInput.model_validate(values)


def summary_template_config_status() -> dict[str, Any]:
    path = summary_template_config_path()
    return {
        "config_path": str(path),
        "config_file_present": path.exists(),
        "template_name": SINGLE_SUMMARY_TEMPLATE_NAME,
    }
