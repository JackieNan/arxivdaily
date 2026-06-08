from pydantic import BaseModel, Field


class ParsedDailyEvent(BaseModel):
    arxiv_id: str
    event_type: str
    listing_category: str
    primary_category: str | None = None
    title: str | None = None
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


class CrawlSourceInput(BaseModel):
    category: str
    event_section: str = "all"
    url: str
    status: str
    http_status: int | None = None
    html: str | None = None
    error: str | None = None
    retry_count: int = 0
    expected_count: int | None = None
    missing_count: int = 0


class PaperVersionInput(BaseModel):
    version: str
    updated_at: str | None = None
    comment: str | None = None
    source_hash: str | None = None


class PaperMetadata(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    primary_category: str | None = None
    categories: list[str] = Field(default_factory=list)
    abs_url: str | None = None
    pdf_url: str | None = None
    published_at: str | None = None
    updated_at: str | None = None
    versions: list[PaperVersionInput] = Field(default_factory=list)


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


class PaperDiscussionInput(BaseModel):
    role: str
    content: str
    tags: list[str] = Field(default_factory=list)
