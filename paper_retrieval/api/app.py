"""HTTP API（可选部署方式）"""

from __future__ import annotations

import base64
import logging
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from paper_retrieval.config import Settings
from paper_retrieval.models import (
    BatchDownloadRequest,
    BatchDownloadResponse,
    DownloadRequest,
    DownloadResult,
    SearchRequest,
    SearchResponse,
)
from paper_retrieval.service import PaperRetrievalService

logger = logging.getLogger(__name__)

settings = Settings()
service = PaperRetrievalService(settings)

app = FastAPI(
    title="Paper Retrieval Service",
    description="无状态文献关键词检索与 PDF 下载微服务",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "paper-retrieval", "stateless": True}


@app.post("/v1/search", response_model=SearchResponse)
async def search_papers(
    request: SearchRequest,
    _: None = Depends(verify_api_key),
) -> SearchResponse:
    try:
        return await service.search(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/download", response_model=DownloadResult)
async def download_metadata(
    request: DownloadRequest,
    _: None = Depends(verify_api_key),
) -> DownloadResult:
    return await service.download(request)


@app.post("/v1/download/pdf")
async def download_pdf_file(
    request: DownloadRequest,
    _: None = Depends(verify_api_key),
) -> Response:
    content, source, error = await service.download_pdf(
        request.doi,
        prefer_oa=request.prefer_oa,
        allow_scihub=request.allow_scihub,
    )
    if not content:
        raise HTTPException(status_code=404, detail=error or "PDF not found")

    filename = f"{request.doi.replace('/', '_')}.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Download-Source": source or "unknown",
    }
    return Response(content=content, media_type="application/pdf", headers=headers)


@app.post("/v1/download/batch", response_model=BatchDownloadResponse)
async def batch_download(
    request: BatchDownloadRequest,
    _: None = Depends(verify_api_key),
) -> BatchDownloadResponse:
    return await service.batch_download(request)


@app.post("/v1/pipeline/search-download", response_model=BatchDownloadResponse)
async def search_and_download(
    request: SearchRequest,
    return_pdf_base64: bool = False,
    prefer_oa: bool = True,
    allow_scihub: bool = True,
    _: None = Depends(verify_api_key),
) -> BatchDownloadResponse:
    return await service.search_and_download(
        query=request.query,
        limit=request.limit,
        prefer_oa=prefer_oa,
        allow_scihub=allow_scihub,
        return_pdf_base64=return_pdf_base64,
    )
