"""
Paper Retrieval Service — 无状态文献检索与 PDF 下载

可被其他系统以 Python 库或 HTTP 微服务方式集成。
"""

from paper_retrieval.config import Settings
from paper_retrieval.models import (
    BatchDownloadRequest,
    BatchDownloadResponse,
    DownloadRequest,
    DownloadResult,
    PaperRecord,
    SearchRequest,
    SearchResponse,
)
from paper_retrieval.service import PaperRetrievalService

__all__ = [
    "Settings",
    "PaperRetrievalService",
    "PaperRecord",
    "SearchRequest",
    "SearchResponse",
    "DownloadRequest",
    "DownloadResult",
    "BatchDownloadRequest",
    "BatchDownloadResponse",
]

__version__ = "1.0.0"
