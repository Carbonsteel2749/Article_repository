"""Full historical metadata synchronization workflow."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict

from article_repository.classification.tagger import MockTagger
from article_repository.ingestion.sources.pubmed import fetch_pubmed_articles, save_pubmed_articles


def _apply_tags_to_articles(repo, articles: List[Dict]) -> None:
    tagger = MockTagger()
    for article in articles:
        doi = article.get("doi", "")
        if not doi:
            continue
        try:
            existing = repo.store.get_by_doi(doi) or {}
            tags = tagger.tag(article.get("title", ""), article.get("abstract", ""))
            existing.update({
                "doi": doi,
                "title": article.get("title", ""),
                "abstract": article.get("abstract", ""),
                "authors": article.get("authors", []),
                "publish_time": article.get("publish_time"),
                "journal": article.get("journal"),
                "journal_division": article.get("journal_division"),
                "citation_count": article.get("citation_count", 0),
                "keywords": article.get("keywords", []),
                "llm_tags": tags.to_dict(),
                "source": article.get("source", "PubMed"),
            })
            from article_repository.storage.metadata_store import LiteratureMetadata
            repo.store.insert_one_meta(LiteratureMetadata(**existing))
        except Exception as exc:
            print(f"自动打标签失败 ({doi}): {exc}")


def run_full_sync(
    repo=None,
    keywords: Optional[List[str]] = None,
    mode: str = "broad",
    years_back: int = 20,
    retmax: int = 50,
) -> List[Dict]:
    """首次全量同步：抓取 PubMed 全部历史结果，持久化到数据库，并为文献打标签。

    Args:
        repo: LiteratureRepository 实例
        keywords: 搜索关键词列表
        mode: 检索模式
        years_back: 往前回溯的年数
        retmax: 最大返回数量

    Returns:
        抓取到的文献列表
    """
    if keywords is None:
        keywords = ["自闭症", "肠道菌群"]

    articles = fetch_pubmed_articles(
        keywords=keywords,
        mode=mode,
        years_back=years_back,
        retmax=retmax,
    )
    if repo is None:
        from article_repository.storage.repository import LiteratureRepository

        repo = LiteratureRepository()
    saved_count = save_pubmed_articles(repo, articles, incremental=False)
    _apply_tags_to_articles(repo, articles)

    # 记录本次全量同步
    repo.record_sync(
        sync_type="full",
        articles_fetched=len(articles),
        articles_saved=saved_count,
        keywords=",".join(keywords) if keywords else "",
        message=f"全量同步完成，回溯 {years_back} 年",
    )

    print(f"PubMed 首次全量同步完成，共抓取并保存 {saved_count} 篇文献")
    return articles


def run_incremental_sync(
    repo=None,
    keywords: Optional[List[str]] = None,
    mode: str = "broad",
    years_back: int = 0,
    retmax: int = 20,
) -> List[Dict]:
    """增量同步：仅拉取上次同步之后新发表的文章，写入数据库并打标签。

    与 run_full_sync 的关键区别：
      - 读取 sync_tracking 表获取上次同步时间
      - 仅拉取 last_sync_date 之后发表的文章
      - 若从未同步过，自动回退到全量同步

    Args:
        repo: LiteratureRepository 实例
        keywords: 搜索关键词列表
        mode: 检索模式（增量时始终使用 broad 最大化召回）
        years_back: 回退年数（仅在无上次同步记录时使用）
        retmax: 最大返回数量

    Returns:
        抓取到的文献列表
    """
    if keywords is None:
        keywords = ["自闭症", "肠道菌群"]

    if repo is None:
        from article_repository.storage.repository import LiteratureRepository

        repo = LiteratureRepository()

    # 读取上次同步日期
    last_sync = repo.get_last_sync_date()

    if last_sync is None:
        # 从未同步过，自动回退到全量同步
        print("未找到同步记录，首次运行将执行全量同步")
        return run_full_sync(
            repo=repo,
            keywords=keywords,
            mode=mode,
            years_back=years_back if years_back > 0 else 20,
            retmax=retmax,
        )

    # 增量抓取：仅拉取 last_sync 之后发表的文章
    # 往前推 1 天作为安全边界，避免遗漏时区边缘的文章
    safe_date_from = last_sync - timedelta(days=1)
    articles = fetch_pubmed_articles(
        keywords=keywords,
        mode="broad",  # 增量模式始终使用 broad 最大化召回
        years_back=0,
        retmax=retmax,
        date_from=safe_date_from,
    )

    saved_count = save_pubmed_articles(repo, articles, incremental=True)
    _apply_tags_to_articles(repo, articles)

    # 记录本次增量同步
    repo.record_sync(
        sync_type="incremental",
        articles_fetched=len(articles),
        articles_saved=saved_count,
        keywords=",".join(keywords) if keywords else "",
        date_from=safe_date_from.isoformat() if safe_date_from else None,
        message=f"增量同步完成，自 {safe_date_from.strftime('%Y-%m-%d')} 之后新增/更新 {saved_count} 篇",
    )

    print(
        f"PubMed 增量同步完成，共新增/更新 {saved_count} 篇文献"
        f"（自 {safe_date_from.strftime('%Y-%m-%d')} 之后）"
    )
    return articles


if __name__ == "__main__":
    run_full_sync(retmax=5)