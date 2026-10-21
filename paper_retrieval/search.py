"""OpenAlex 关键词检索（无状态）"""

from __future__ import annotations

import logging
from typing import Any, Optional

import aiohttp

from paper_retrieval.config import Settings
from paper_retrieval.models import PaperRecord

logger = logging.getLogger(__name__)


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    value = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if value.lower().startswith(prefix):
            value = value[len(prefix):]
    return value.strip().lower() or None


def reconstruct_abstract(inverted_index: Optional[dict[str, list[int]]]) -> Optional[str]:
    if not inverted_index:
        return None
    positions: dict[int, str] = {}
    for word, idxs in inverted_index.items():
        for idx in idxs:
            positions[idx] = word
    if not positions:
        return None
    return " ".join(positions[i] for i in sorted(positions))


def format_authors(authorships: list[dict[str, Any]]) -> Optional[str]:
    names: list[str] = []
    for authorship in authorships[:10]:
        author = authorship.get("author") or {}
        display_name = author.get("display_name")
        if display_name:
            names.append(display_name)
    if not names:
        return None
    suffix = ", et al." if len(authorships) > 10 else ""
    return ", ".join(names) + suffix


def parse_openalex_work(work: dict[str, Any]) -> PaperRecord:
    doi = normalize_doi(work.get("doi"))
    title = (work.get("title") or work.get("display_name") or "").strip()
    authorships = work.get("authorships") or []
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    journal = source.get("display_name")
    openalex_id = work.get("id")
    if openalex_id and openalex_id.startswith("https://openalex.org/"):
        openalex_id = openalex_id.rsplit("/", 1)[-1]

    return PaperRecord(
        openalex_id=openalex_id,
        doi=doi,
        title=title or "Untitled",
        authors=format_authors(authorships),
        journal=journal,
        publish_year=work.get("publication_year"),
        cited_by_count=work.get("cited_by_count"),
        abstract=reconstruct_abstract(work.get("abstract_inverted_index")),
        landing_page_url=primary_location.get("landing_page_url"),
    )


class OpenAlexSearcher:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()

    def _headers(self) -> dict[str, str]:
        mailto = self.settings.openalex_mailto
        return {
            "User-Agent": f"PaperRetrievalService/1.0 (mailto:{mailto})",
            "Accept": "application/json",
        }

    async def search(
        self,
        query: str,
        limit: int = 50,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        sort: str = "relevance",
    ) -> list[PaperRecord]:
        query = (query or "").strip()
        if len(query) < 2:
            raise ValueError("搜索关键词至少需要 2 个字符")

        limit = max(1, min(limit, self.settings.max_search_limit))
        filters = ["has_doi:true", "type:article|review"]
        if year_from is not None:
            filters.append(f"from_publication_date:{year_from}-01-01")
        if year_to is not None:
            filters.append(f"to_publication_date:{year_to}-12-31")

        params: dict[str, Any] = {
            "search": query,
            "filter": ",".join(filters),
            "per-page": limit,
            "mailto": self.settings.openalex_mailto,
        }
        if sort == "cited_by_count":
            params["sort"] = "cited_by_count:desc"

        timeout = aiohttp.ClientTimeout(
            total=30,
            connect=self.settings.connect_timeout,
        )
        async with aiohttp.ClientSession(timeout=timeout, headers=self._headers()) as session:
            async with session.get(self.settings.openalex_works_api, params=params) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.warning("OpenAlex failed: status=%s body=%s", response.status, text[:300])
                    raise ValueError(f"文献检索失败 (OpenAlex HTTP {response.status})")
                data = await response.json()

        works = data.get("results") or []
        results = [parse_openalex_work(work) for work in works]
        return [item for item in results if item.title]
