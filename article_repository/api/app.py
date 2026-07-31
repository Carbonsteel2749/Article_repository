"""FastAPI application for the article repository."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from article_repository.api.routes import router
from article_repository.ingestion.full_sync import run_full_sync
from article_repository.storage.repository import LiteratureRepository

app = FastAPI(title="Article Repository", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def bootstrap_initial_data() -> None:
    repo = LiteratureRepository()
    existing = repo.retrieve_literature({}, page=1, page_size=1)
    if existing:
        print(f"数据库已有 {len(existing)}+ 条文献记录，跳过首次全量同步")
        return
    try:
        print("数据库为空，开始首次全量同步...")
        result = run_full_sync(repo=repo, keywords=["自闭症", "肠道菌群"], mode="broad", years_back=20, retmax=50)
        if not result:
            print("警告：首次同步未获取到任何文章，请检查 PubMed API 连接和检索式是否正确")
        else:
            print(f"首次同步完成，共入库 {len(result)} 篇文献")
    except Exception as exc:
        print(f"首次同步失败: {exc}")
        print("请检查网络连接、PubMed API 可用性以及检索式是否正确。可在服务启动后通过前端「同步 PubMed」按钮手动重试。")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("article_repository.api.app:app", host="0.0.0.0", port=8000, reload=False)
