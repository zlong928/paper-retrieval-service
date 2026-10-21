#!/usr/bin/env python3
"""启动 HTTP 服务: python -m paper_retrieval.main"""

import uvicorn

from paper_retrieval.config import Settings


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "paper_retrieval.api.app:app",
        host="0.0.0.0",
        port=settings.paper_retrieval_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
