from pydantic import BaseModel, Field


class ParsedDailyEvent(BaseModel):
    arxiv_id: str
    event_type: str
    listing_category: str
    primary_category: str | None = None
    source_url: str


class CrawlSourceResult(BaseModel):
    category: str
    event_section: str
    url: str
    status: str
    http_status: int | None = None
    parsed_count: int = 0
    error: str | None = None
    retry_count: int = 0


class SummaryTemplateField(BaseModel):
    key: str
    label: str
    order: int
    prompt: str
    field_type: str
    enabled: bool = True


class SummaryTemplateInput(BaseModel):
    name: str
    language: str = "Chinese"
    fields: list[SummaryTemplateField] = Field(default_factory=list)
    system_prompt: str
    input_scope: str = "abstract"
    is_default: bool = False
