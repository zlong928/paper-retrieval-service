"""统一门面：检索 + 下载，完全无状态"""

from __future__ import annotations

import asyncio
import base64
from typing import Optional

from paper_retrieval.config import Settings
from paper_retrieval.download import PdfDownloader
from paper_retrieval.models import (
    BatchDownloadItem,
    BatchDownloadRequest,
    BatchDownloadResponse,
    DownloadRequest,
    DownloadResult,
    SearchRequest,
    SearchResponse,
)
from paper_retrieval.search import OpenAlexSearcher


class PaperRetrievalService:
    """
    无状态文献检索与下载服务。

    用法（Python 库）::

        service = PaperRetrievalService()
        search = await service.search(SearchRequest(query="ATPS PEG dextran", limit=10))
        pdf, source, err = await service.download_pdf("10.1038/nature12373")
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self._searcher = OpenAlexSearcher(self.settings)
        self._downloader = PdfDownloader(self.settings)

    async def search(self, request: SearchRequest) -> SearchResponse:
        results = await self._searcher.search(
            query=request.query,
            limit=request.limit,
            year_from=request.year_from,
            year_to=request.year_to,
            sort=request.sort,
        )
        with_doi = sum(1 for item in results if item.doi)
        return SearchResponse(
            query=request.query,
            total_found=len(results),
            with_doi_count=with_doi,
            no_doi_count=len(results) - with_doi,
            results=results,
        )

    async def download_pdf(
        self,
        doi: str,
        *,
        prefer_oa: bool = True,
        allow_scihub: bool = True,
    ) -> tuple[Optional[bytes], Optional[str], Optional[str]]:
        return await self._downloader.download_pdf(
            doi,
            prefer_oa=prefer_oa,
            allow_scihub=allow_scihub,
        )

    async def download(self, request: DownloadRequest) -> DownloadResult:
        content, source, error = await self.download_pdf(
            request.doi,
            prefer_oa=request.prefer_oa,
            allow_scihub=request.allow_scihub,
        )
        return DownloadResult(
            doi=request.doi,
            success=content is not None,
            source=source,
            pdf_size=len(content) if content else None,
            error=error,
            title=request.title,
        )

    async def batch_download(self, request: BatchDownloadRequest) -> BatchDownloadResponse:
        semaphore = asyncio.Semaphore(self.settings.max_concurrency)

        async def _one(item: DownloadRequest) -> BatchDownloadItem:
            async with semaphore:
                content, source, error = await self.download_pdf(
                    item.doi,
                    prefer_oa=item.prefer_oa,
                    allow_scihub=item.allow_scihub,
                )
                pdf_b64 = None
                if request.return_pdf_base64 and content:
                    pdf_b64 = base64.b64encode(content).decode("ascii")
                return BatchDownloadItem(
                    doi=item.doi,
                    success=content is not None,
                    source=source,
                    pdf_size=len(content) if content else None,
                    error=error,
                    title=item.title,
                    pdf_base64=pdf_b64,
                )

        results = await asyncio.gather(*[_one(item) for item in request.items])
        success_count = sum(1 for r in results if r.success)
        return BatchDownloadResponse(
            total=len(results),
            success_count=success_count,
            failed_count=len(results) - success_count,
            results=list(results),
        )

    async def search_and_download(
        self,
        query: str,
        limit: int = 10,
        *,
        prefer_oa: bool = True,
        allow_scihub: bool = True,
        return_pdf_base64: bool = False,
    ) -> BatchDownloadResponse:
        """检索后立即批量下载（便捷方法）"""
        search = await self.search(SearchRequest(query=query, limit=limit))
        items = [
            DownloadRequest(doi=r.doi, title=r.title, prefer_oa=prefer_oa, allow_scihub=allow_scihub)
            for r in search.results
            if r.doi
        ]
        if not items:
            return BatchDownloadResponse(total=0, success_count=0, failed_count=0, results=[])
        return await self.batch_download(
            BatchDownloadRequest(items=items, return_pdf_base64=return_pdf_base64)
        )
