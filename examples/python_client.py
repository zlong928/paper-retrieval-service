#!/usr/bin/env python3
"""Python 库调用示例"""

import asyncio
import base64

from paper_retrieval.models import BatchDownloadRequest, DownloadRequest, SearchRequest
from paper_retrieval.service import PaperRetrievalService


async def main() -> None:
    service = PaperRetrievalService()

    # 1. 关键词检索
    search = await service.search(
        SearchRequest(query="aqueous two phase system PEG", limit=5)
    )
    print(f"检索到 {search.total_found} 篇，有 DOI: {search.with_doi_count}")
    for paper in search.results[:3]:
        print(f"  - [{paper.publish_year}] {paper.title[:60]}... DOI={paper.doi}")

    if not search.results or not search.results[0].doi:
        return

    # 2. 单篇下载
    doi = search.results[0].doi
    pdf_bytes, source, error = await service.download_pdf(doi)
    if pdf_bytes:
        out = f"example_{doi.replace('/', '_')}.pdf"
        with open(out, "wb") as f:
            f.write(pdf_bytes)
        print(f"下载成功: source={source}, size={len(pdf_bytes)}, saved={out}")
    else:
        print(f"下载失败: {error}")

    # 3. 批量下载（返回 base64，便于 JSON 传输）
    dois = [p.doi for p in search.results if p.doi][:3]
    batch = await service.batch_download(
        BatchDownloadRequest(
            items=[DownloadRequest(doi=d) for d in dois],
            return_pdf_base64=True,
        )
    )
    print(f"批量: {batch.success_count}/{batch.total} 成功")
    for item in batch.results:
        if item.success and item.pdf_base64:
            raw = base64.b64decode(item.pdf_base64)
            print(f"  {item.doi}: {item.source}, {len(raw)} bytes")


if __name__ == "__main__":
    asyncio.run(main())
