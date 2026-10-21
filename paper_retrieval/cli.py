"""Paper Retrieval CLI 工具"""

import argparse
import asyncio
import os
import sys

from paper_retrieval.config import Settings
from paper_retrieval.download import PdfDownloader
from paper_retrieval.models import SearchRequest
from paper_retrieval.search import OpenAlexSearcher


def parse_args():
    parser = argparse.ArgumentParser(
        prog="paper-retrieval",
        description="Paper Retrieval CLI: Search literature & download PDFs (OA + Sci-Hub fallback with PoW bypass)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. Download single PDF
    p_dl = subparsers.add_parser("download", help="Download PDF by DOI")
    p_dl.add_argument("doi", help="DOI of the paper, e.g., 10.1021/ja044205+")
    p_dl.add_argument("-o", "--output", help="Output PDF file path", default=None)

    # 2. Batch download from file
    p_batch = subparsers.add_parser("batch-download", help="Batch download PDFs from a file with DOIs or titles")
    p_batch.add_argument("file", help="File containing DOIs (one per line)")
    p_batch.add_argument("-d", "--dest", help="Destination folder", default="./downloads")

    # 3. Search papers
    p_search = subparsers.add_parser("search", help="Search papers via OpenAlex")
    p_search.add_argument("query", help="Search keyword / query")
    p_search.add_argument("-l", "--limit", type=int, default=10, help="Number of results")
    p_search.add_argument("-y", "--year-from", type=int, default=None, help="Year from")
    p_search.add_argument("-t", "--year-to", type=int, default=None, help="Year to")

    return parser.parse_args()


async def run_download(doi: str, output: str = None):
    settings = Settings()
    downloader = PdfDownloader(settings)
    print(f"[*] Downloading DOI: {doi}...")
    content, source, error = await downloader.download_pdf(doi)
    if content:
        if not output:
            safe_name = doi.replace("/", "_").replace(":", "_") + ".pdf"
            output = safe_name
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        with open(output, "wb") as f:
            f.write(content)
        print(f"[✓] Successfully downloaded via {source} -> {output} ({len(content)} bytes)")
    else:
        print(f"[✗] Failed: {error}")
        sys.exit(1)


async def run_batch(file_path: str, dest_dir: str):
    if not os.path.exists(file_path):
        print(f"[✗] File not found: {file_path}")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    os.makedirs(dest_dir, exist_ok=True)
    settings = Settings()
    downloader = PdfDownloader(settings)

    print(f"[*] Found {len(lines)} DOIs in {file_path}. Starting batch download into {dest_dir}...")
    for idx, doi in enumerate(lines, 1):
        safe_name = f"{idx:02d}_" + doi.replace("/", "_").replace(":", "_") + ".pdf"
        out_path = os.path.join(dest_dir, safe_name)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            print(f"[{idx}/{len(lines)}] [CACHE] {safe_name}")
            continue

        print(f"[{idx}/{len(lines)}] Fetching: {doi}...")
        content, source, error = await downloader.download_pdf(doi)
        if content:
            with open(out_path, "wb") as f:
                f.write(content)
            print(f"  [✓] OK ({source}, {len(content)} bytes)")
        else:
            print(f"  [✗] Failed: {error}")
        await asyncio.sleep(1)


async def run_search(query: str, limit: int, year_from: int = None, year_to: int = None):
    settings = Settings()
    searcher = OpenAlexSearcher(settings)
    print(f"[*] Searching for '{query}' (limit={limit})...")
    results = await searcher.search(query=query, limit=limit, year_from=year_from, year_to=year_to)
    print(f"[✓] Found {len(results)} items:")
    for idx, r in enumerate(results, 1):
        print(f"\n{idx}. {r.title}")
        print(f"   DOI: {r.doi}")
        print(f"   Journal: {r.venue} ({r.year}) | Citations: {r.cited_by_count}")
        if r.is_oa:
            print(f"   Open Access: Yes ({r.oa_url})")


def main():
    args = parse_args()
    if args.command == "download":
        asyncio.run(run_download(args.doi, args.output))
    elif args.command == "batch-download":
        asyncio.run(run_batch(args.file, args.dest))
    elif args.command == "search":
        asyncio.run(run_search(args.query, args.limit, args.year_from, args.year_to))


if __name__ == "__main__":
    main()
