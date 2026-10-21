"""Unpaywall + Sci-Hub + OpenAlex PDF 下载（无状态）"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import re
from typing import Literal, Optional

import aiohttp
from bs4 import BeautifulSoup

from paper_retrieval.config import Settings
from paper_retrieval.search import normalize_doi

logger = logging.getLogger(__name__)

DownloadSource = Literal["unpaywall", "scihub", "openalex"]


class PdfDownloader:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()

    def _headers(self) -> dict[str, str]:
        return {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

    def _timeout(self) -> aiohttp.ClientTimeout:
        return aiohttp.ClientTimeout(
            total=self.settings.request_timeout,
            connect=self.settings.connect_timeout,
            sock_read=30,
        )

    @staticmethod
    def _is_pdf(content: bytes) -> bool:
        return len(content) >= 4 and (content[:4] == b"%PDF" or b"%PDF" in content[:1024])

    @staticmethod
    def _extract_pdf(content: bytes) -> bytes:
        if content[:4] == b"%PDF":
            return content
        idx = content.find(b"%PDF")
        if idx != -1:
            return content[idx:]
        return content

    async def download_from_unpaywall(
        self,
        session: aiohttp.ClientSession,
        doi: str,
    ) -> Optional[bytes]:
        url = f"{self.settings.unpaywall_api}/{doi}?email={self.settings.unpaywall_email}"
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                if not data.get("is_oa"):
                    return None
                best_oa = data.get("best_oa_location") or {}
                pdf_url = best_oa.get("url_for_pdf") or best_oa.get("url")
                if not pdf_url:
                    return None
                async with session.get(pdf_url, allow_redirects=True) as pdf_response:
                    if pdf_response.status != 200:
                        return None
                    content = await pdf_response.read()
                    if self._is_pdf(content):
                        logger.info("Unpaywall OK: doi=%s size=%s", doi, len(content))
                        return self._extract_pdf(content)
        except Exception as exc:
            logger.warning("Unpaywall failed: doi=%s error=%s", doi, exc)
        return None

    async def download_from_openalex(
        self,
        session: aiohttp.ClientSession,
        doi: str,
    ) -> Optional[bytes]:
        url = f"{self.settings.openalex_works_api}/https://doi.org/{doi}"
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                oa_info = data.get("open_access") or {}
                pdf_url = oa_info.get("oa_url")
                if not pdf_url:
                    best_loc = data.get("best_oa_location") or {}
                    pdf_url = best_loc.get("pdf_url") or best_loc.get("landing_page_url")
                if not pdf_url:
                    return None
                async with session.get(pdf_url, allow_redirects=True) as pdf_response:
                    if pdf_response.status != 200:
                        return None
                    content = await pdf_response.read()
                    if self._is_pdf(content):
                        logger.info("OpenAlex OK: doi=%s size=%s", doi, len(content))
                        return self._extract_pdf(content)
        except Exception as exc:
            logger.warning("OpenAlex failed: doi=%s error=%s", doi, exc)
        return None

    async def _solve_altcha(self, session: aiohttp.ClientSession, html: str, domain: str) -> bool:
        m_chal = re.search(r'challengeurl\s*=\s*[\'"]([^\'"]+)[\'"]', html)
        if not m_chal:
            return False
        chal_path = m_chal.group(1)
        chal_url = domain.rstrip('/') + chal_path if chal_path.startswith('/') else chal_path
        chal_id = chal_path.split('/')[-1]

        try:
            async with session.get(chal_url) as r:
                if r.status != 200:
                    return False
                chal = await r.json()

            salt = chal['salt']
            target = chal['challenge']
            max_n = chal.get('maxNumber', 2000000)
            sol = None
            for n in range(max_n + 1):
                if hashlib.sha256((salt + str(n)).encode('utf-8')).hexdigest() == target:
                    sol = n
                    break
            if sol is None:
                return False

            payload = {
                'algorithm': chal['algorithm'],
                'challenge': chal['challenge'],
                'number': sol,
                'salt': chal['salt'],
                'signature': chal['signature']
            }
            b64 = base64.b64encode(json.dumps(payload).encode('utf-8')).decode('utf-8')
            sol_url = f"{domain.rstrip('/')}/captcha/solution/{chal_id}"
            async with session.post(sol_url, json={'captcha': b64}) as r_sol:
                if r_sol.status == 200:
                    res = await r_sol.json()
                    return res.get('success', False)
        except Exception as e:
            logger.warning("Altcha solve exception on %s: %s", domain, e)
        return False

    def _extract_scihub_pdf_url(self, html: str, domain: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        meta = soup.find("meta", {"name": "citation_pdf_url"})
        if meta and meta.get("content"):
            src = meta["content"]
            return src if src.startswith("http") else f"{domain.rstrip('/')}/{src.lstrip('/')}"

        m_loc = re.search(r"onclick=[\'\"]location\.href=['\"]([^'\"]+\.pdf[^'\"]*)['\"]", html, re.I)
        if m_loc:
            src = m_loc.group(1).replace(r"\/", "/")
            return src if src.startswith("http") else f"{domain.rstrip('/')}/{src.lstrip('/')}"

        if soup.embed and soup.embed.get("src"):
            src = soup.embed["src"]
            return src if src.startswith("http") else f"https:{src}" if src.startswith("//") else f"{domain.rstrip('/')}/{src.lstrip('/')}"

        if soup.iframe and soup.iframe.get("src"):
            src = soup.iframe["src"]
            return src if src.startswith("http") else f"https:{src}" if src.startswith("//") else f"{domain.rstrip('/')}/{src.lstrip('/')}"

        obj = soup.find("object")
        if obj and obj.get("data"):
            src = obj["data"].split('#')[0]
            return src if src.startswith("http") else f"https:{src}" if src.startswith("//") else f"{domain.rstrip('/')}/{src.lstrip('/')}"

        btn = soup.find("div", class_="download")
        if btn and btn.find("a") and btn.find("a").get("href"):
            src = btn.find("a")["href"]
            return src if src.startswith("http") else f"https:{src}" if src.startswith("//") else f"{domain.rstrip('/')}/{src.lstrip('/')}"

        return None

    async def download_from_scihub(
        self,
        session: aiohttp.ClientSession,
        doi: str,
    ) -> Optional[bytes]:
        import urllib.parse
        quoted_doi = urllib.parse.quote(doi, safe='/')
        for domain in self.settings.scihub_domains:
            try:
                url = f"{domain}{quoted_doi}"
                async with session.get(url) as response:
                    if response.status != 200:
                        continue
                    html = await response.text()

                    if "altcha-widget" in html:
                        logger.info("Solving Altcha on %s for %s", domain, doi)
                        if await self._solve_altcha(session, html, domain):
                            async with session.get(url) as resp2:
                                if resp2.status == 200:
                                    html = await resp2.text()

                    download_url = self._extract_scihub_pdf_url(html, domain)
                    if not download_url:
                        continue

                    async with session.get(download_url, allow_redirects=True) as pdf_response:
                        if pdf_response.status != 200:
                            continue
                        content = await pdf_response.read()
                        if self._is_pdf(content):
                            logger.info("Sci-Hub OK: doi=%s size=%s (source=%s)", doi, len(content), domain)
                            return self._extract_pdf(content)
            except asyncio.TimeoutError:
                logger.warning("Sci-Hub timeout: domain=%s doi=%s", domain, doi)
            except Exception as exc:
                logger.warning("Sci-Hub failed: domain=%s doi=%s error=%s", domain, doi, exc)
        return None

    async def download_pdf(
        self,
        doi: str,
        *,
        prefer_oa: bool = True,
        allow_scihub: bool = True,
    ) -> tuple[Optional[bytes], Optional[DownloadSource], Optional[str]]:
        """
        按 DOI 下载 PDF。

        Returns:
            (pdf_bytes, source, error_message)
        """
        normalized = normalize_doi(doi)
        if not normalized:
            return None, None, "无效 DOI"

        timeout = self._timeout()
        connector = aiohttp.TCPConnector(limit_per_host=5, ssl=False)
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=self._headers(),
            connector=connector,
        ) as session:
            if prefer_oa:
                content = await self.download_from_unpaywall(session, normalized)
                if content:
                    return content, "unpaywall", None

                content = await self.download_from_openalex(session, normalized)
                if content:
                    return content, "openalex", None

            if allow_scihub:
                content = await self.download_from_scihub(session, normalized)
                if content:
                    return content, "scihub", None

        return None, None, "无法下载 PDF（已尝试 Unpaywall, OpenAlex 与 Sci-Hub）"
