from collections.abc import Mapping
from typing import Any, Protocol
import json
import os
import re
import urllib.error
import urllib.request


class SummaryParseError(ValueError):
    pass


class LLMClient(Protocol):
    def complete(self, *, model: str, messages: list[dict[str, str]]) -> str:
        pass


FENCED_JSON_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.IGNORECASE | re.DOTALL)


def _value(row: Mapping[str, Any] | Any, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def _json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    loaded = json.loads(value)
    return loaded if isinstance(loaded, list) else []


def enabled_template_fields(template: Mapping[str, Any] | Any) -> list[dict[str, Any]]:
    raw_fields = _json_list(_value(template, "fields_json", "[]"))
    fields = [field for field in raw_fields if field.get("enabled", True)]
    return sorted(fields, key=lambda field: int(field.get("order", 0)))


def build_summary_messages(
    *,
    paper: Mapping[str, Any] | Any,
    template: Mapping[str, Any] | Any,
) -> list[dict[str, str]]:
    fields = enabled_template_fields(template)
    field_lines = [
        f"- {field['key']} ({field.get('label', field['key'])}, {field.get('field_type', 'text')}): {field.get('prompt', '')}"
        for field in fields
    ]
    expected_keys = ", ".join(field["key"] for field in fields)
    authors = ", ".join(_json_list(_value(paper, "authors_json")))
    categories = ", ".join(_json_list(_value(paper, "categories_json")))
    system_prompt = _value(template, "system_prompt", "")
    input_scope = _value(template, "input_scope", "abstract")

    system_message = (
        f"{system_prompt}\n\n"
        "Return only a valid JSON object. "
        f"The JSON object must use these keys exactly: {expected_keys}."
    )
    user_message = "\n".join(
        [
            f"arXiv ID: {_value(paper, 'arxiv_id', '')}",
            f"Title: {_value(paper, 'title', '')}",
            f"Authors: {authors}",
            f"Primary category: {_value(paper, 'primary_category', '')}",
            f"Categories: {categories}",
            f"Abstract: {_value(paper, 'abstract', '') if input_scope == 'abstract' else ''}",
            "",
            "Required JSON fields:",
            *field_lines,
        ]
    )
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]


def parse_summary_response(text: str, *, expected_keys: list[str]) -> dict[str, Any]:
    stripped = text.strip()
    match = FENCED_JSON_RE.match(stripped)
    if match:
        stripped = match.group(1).strip()
    try:
        loaded = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise SummaryParseError("summary response is not valid JSON") from exc
    if not isinstance(loaded, dict):
        raise SummaryParseError("summary response must be a JSON object")
    if not expected_keys:
        return loaded
    return {key: loaded.get(key, "") for key in expected_keys}


class OpenAICompatibleChatClient:
    def __init__(
        self,
        *,
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        temperature: float = 0.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature

    @classmethod
    def from_env(cls) -> "OpenAICompatibleChatClient":
        return cls(
            base_url=os.getenv("ARXIV_DAILY_LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("ARXIV_DAILY_LLM_API_KEY"),
            temperature=float(os.getenv("ARXIV_DAILY_LLM_TEMPERATURE", "0")),
        )

    def complete(self, *, model: str, messages: list[dict[str, str]]) -> str:
        payload = json.dumps(
            {
                "model": model,
                "messages": messages,
                "temperature": self.temperature,
            }
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "arxiv-local-daily/0.1",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM HTTP error {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc
        return response_payload["choices"][0]["message"]["content"]
