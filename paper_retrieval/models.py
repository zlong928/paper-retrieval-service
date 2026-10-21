"""请求/响应模型（纯数据，无数据库字段）"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class PaperRecord(BaseModel):
    openalex_id: Optional[str] = None
    doi: Optional[str] = None
    title: str
    authors: Optional[str] = None
    journal: Optional[str] = None
    publish_year: Optional[int] = None
    cited_by_count: Optional[int] = None
    abstract: Optional[str] = None
    landing_page_url: Optional[str] = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="检索关键词")
    limit: int = Field(default=50, ge=1, le=200)
    year_from: Optional[int] = Field(default=None, ge=1900, le=2100)
    year_to: Optional[int] = Field(default=None, ge=1900, le=2100)
    sort: Literal["relevance", "cited_by_count"] = "relevance"


class SearchResponse(BaseModel):
    query: str
    total_found: int
    with_doi_count: int
    no_doi_count: int
    results: list[PaperRecord]


class DownloadRequest(BaseModel):
    doi: str = Field(..., min_length=3)
    title: Optional[str] = None
    prefer_oa: bool = True
    allow_scihub: bool = True


class DownloadResult(BaseModel):
    doi: str
    success: bool
    source: Optional[Literal["unpaywall", "scihub"]] = None
    pdf_size: Optional[int] = None
    error: Optional[str] = None
    title: Optional[str] = None


class BatchDownloadRequest(BaseModel):
    items: list[DownloadRequest] = Field(..., min_length=1, max_length=50)
    return_pdf_base64: bool = False


class BatchDownloadItem(DownloadResult):
    pdf_base64: Optional[str] = None


class BatchDownloadResponse(BaseModel):
    total: int
    success_count: int
    failed_count: int
    results: list[BatchDownloadItem]
