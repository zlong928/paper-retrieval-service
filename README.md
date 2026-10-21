# Paper Retrieval Service

无状态学术文献 **关键词检索 + PDF 全文下载** 独立套件，可作为 **CLI 命令行工具**、**Python 库** 或 **HTTP 微服务** 运行。

- **无数据库、无 Redis、无任务队列**
- **原生支持 Altcha PoW（工作量证明）反爬自动破解**（突破 Sci-Hub 验证码拦截）
- **自动转义特殊字符 DOI**（如结尾包含 `+`、`/` 等特殊符号的文献）
- **三级下载链路**：Unpaywall (OA) ➔ OpenAlex (OA) ➔ Sci-Hub 多镜像动态轮询
- 每次请求独立处理，无状态连接，开箱即用

---

## 目录结构

```
paper-retrieval-service/
├── paper_retrieval/          # 核心源码
│   ├── cli.py                # 命令行 CLI 入口
│   ├── config.py             # 环境变量与镜像配置
│   ├── download.py           # Unpaywall + OpenAlex + Sci-Hub (带 Altcha PoW 破解)
│   ├── models.py             # Pydantic 数据模型
│   ├── search.py             # OpenAlex 检索与 DOI 规范化
│   ├── service.py            # 统一门面 PaperRetrievalService
│   ├── main.py               # HTTP 服务启动入口
│   └── api/app.py            # FastAPI 路由定义
├── examples/                 # 调用示例 (Python / cURL)
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── .env.example
```

---

## 能力说明

| 模块 | 数据源 / 技术 | 说明 |
|------|--------|------|
| **关键词检索** | OpenAlex API | 返回 DOI、标题、作者、期刊/会议、被引数、摘要、OA 状态等 |
| **首选下载 (OA)** | Unpaywall & OpenAlex | 优先下载官方金色/绿色开放获取（CC-BY 等）PDF，速度最快 |
| **兜底下载 (镜像)** | Sci-Hub 多镜像路由 | 支持 `sci-hub.ee`, `sci-hub.ren`, `sci-hub.st`, `sci-hub.ru` 等 |
| **验证码绕过** | Altcha PoW 密码学求解器 | 自动捕获 challenge，并在内存中并发暴力破解 SHA-256 获取 Session Cookie |
| **特殊 DOI 转义** | URL Safe Suffix Quoting | 避免如 `10.1021/ja044205+` 等特殊 DOI 在 HTTP 传输中被误解码为空格导致 404 |

---

## 快速上手

### 1. 安装依赖

```bash
git clone https://github.com/zlong928/paper-retrieval-service.git
cd paper-retrieval-service

# 推荐使用 uv 或 pip 安装
pip install -r requirements.txt
# 或者以开发模式安装 CLI
pip install -e .
```

---

### 2. 作为 CLI 命令行工具使用

```bash
# 下载单篇文献（指定 DOI，自动绕过反爬并保存）
python -m paper_retrieval.cli download "10.1021/ja044205+" -o paper.pdf

# 批量下载（从文本文件中按行读取 DOI）
python -m paper_retrieval.cli batch-download dois.txt -d ./downloads

# 关键词文献检索
python -m paper_retrieval.cli search "antimicrobial peptides" -l 5
```

---

### 3. 作为 Python 库（嵌入其他项目）

```python
import asyncio
from paper_retrieval import PaperRetrievalService
from paper_retrieval.models import SearchRequest

async def main():
    service = PaperRetrievalService()

    # 1. 关键词检索
    res = await service.search(SearchRequest(query="amphiphilic polymethacrylate", limit=5))
    for item in res.results:
        print(f"[{item.year}] {item.title} (DOI: {item.doi})")

    # 2. 按 DOI 下载 PDF（返回 bytes）
    pdf_bytes, source, error = await service.download_pdf("10.1021/ja044205+")
    if pdf_bytes:
        with open("paper.pdf", "wb") as f:
            f.write(pdf_bytes)
        print(f"下载成功！来源: {source}, 大小: {len(pdf_bytes)} 字节")
    else:
        print(f"下载失败: {error}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 4. 作为 HTTP 微服务部署

#### 本地启动
```bash
cp .env.example .env
python -m paper_retrieval.main
```
服务默认监听 `http://0.0.0.0:8080`，API 文档位于 `http://localhost:8080/docs`。

#### Docker Compose 启动
```bash
docker compose up -d --build
```

#### API 端点
- `POST /v1/search`：关键词检索文献元数据
- `POST /v1/download/pdf`：按 DOI 直接返回 PDF 文件流
- `POST /v1/download/batch`：批量下载
- `POST /v1/pipeline/search-download`：检索并自动打包下载

---

## 许可证

[MIT License](LICENSE)
