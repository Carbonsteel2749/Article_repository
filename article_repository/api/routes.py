"""API route registration for article browsing, sync, and evaluation."""

import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter, Query

from article_repository.api.schemas import (
	ArticleOut,
	HealthResponse,
	SearchResponse,
	SyncResponse,
	TagQualityResponse,
)
from article_repository.ingestion.full_sync import run_incremental_sync
from article_repository.storage.repository import LiteratureRepository

router = APIRouter()


def _get_repo() -> LiteratureRepository:
	return LiteratureRepository()


def _row_to_article(item: Dict[str, Any]) -> ArticleOut:
	return ArticleOut(
		doi=item.get("doi", ""),
		title=item.get("title", ""),
		abstract=item.get("abstract"),
		authors=item.get("authors", []),
		publish_time=item.get("publish_time"),
		journal=item.get("journal"),
		journal_division=item.get("journal_division"),
		citation_count=item.get("citation_count", 0),
		keywords=item.get("keywords", []),
		llm_tags=item.get("llm_tags", {}),
		source=item.get("source", "PubMed"),
	)


def _normalize_tags(tags: Optional[Dict[str, Any]]) -> Dict[str, Any]:
	if not tags:
		return {}
	return {k: v for k, v in tags.items() if str(v or "").strip()}


def _fetch_all_articles(repo: LiteratureRepository, keyword: Optional[str] = None) -> List[Dict[str, Any]]:
	params = {"keyword": keyword} if keyword else {}
	return repo.retrieve_literature(params, page=1, page_size=100000)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
	return HealthResponse()


@router.get("/api/stats")
def stats() -> Dict[str, Any]:
    repo = _get_repo()
    articles = _fetch_all_articles(repo)
    total = len(articles)
    valid_tags = [
        item for item in articles
        if _normalize_tags(item.get("llm_tags"))
    ]
    tagged = len(valid_tags)
    untagged = total - tagged
    source_counts = Counter(item.get("source", "unknown") for item in articles)
    last_sync = repo.get_last_sync_date()
    sync_history = repo.get_sync_history(limit=1)
    return {
        "total": total,
        "tagged": tagged,
        "untagged": untagged,
        "coverage": round(tagged / total, 4) if total else 0.0,
        "sources": dict(source_counts),
        "last_sync_date": last_sync.isoformat() if last_sync else None,
        "last_sync_message": sync_history[0].get("message", "") if sync_history else "",
    }


@router.get("/api/articles", response_model=SearchResponse)
def list_articles(
	keyword: Optional[str] = Query(default=None),
	tag_key: Optional[str] = Query(default=None),
	tag_value: Optional[str] = Query(default=None),
	page: int = Query(default=1, ge=1),
	page_size: int = Query(default=20, ge=1, le=200),
) -> SearchResponse:
	repo = _get_repo()
	search_params: Dict[str, Any] = {}
	if keyword:
		search_params["keyword"] = keyword
	if tag_key and tag_value:
		search_params["tag_filter"] = {tag_key: tag_value}
	items = repo.retrieve_literature(search_params, page=page, page_size=page_size)
	total_items = _fetch_all_articles(repo, keyword=keyword)
	if tag_key and tag_value:
		total_items = [item for item in total_items if str(item.get("llm_tags", {}).get(tag_key, "")) == tag_value]
	return SearchResponse(
		total=len(total_items),
		page=page,
		page_size=page_size,
		items=[_row_to_article(item) for item in items],
	)


@router.get("/api/eval/tag-quality", response_model=TagQualityResponse)
def tag_quality() -> TagQualityResponse:
	repo = _get_repo()
	articles = _fetch_all_articles(repo)
	total = len(articles)
	tagged = 0
	field_counter = Counter({"core_bacteria": 0, "experiment_model": 0, "intervention": 0, "analysis_method": 0})
	for article in articles:
		tags = _normalize_tags(article.get("llm_tags"))
		if tags and any(str(v).strip() for v in tags.values()):
			tagged += 1
		for field in field_counter.keys():
			if str(tags.get(field, "")).strip():
				field_counter[field] += 1
	field_fill_rate = {
		field: round(count / total, 4) if total else 0.0
		for field, count in field_counter.items()
	}
	return TagQualityResponse(
		total=total,
		tagged=tagged,
		untagged=total - tagged,
		coverage=round(tagged / total, 4) if total else 0.0,
		field_fill_rate=field_fill_rate,
	)


@router.post("/api/sync/pubmed", response_model=SyncResponse)
def sync_pubmed(retmax: int = 20) -> SyncResponse:
	articles = run_incremental_sync(retmax=retmax)
	return SyncResponse(
		fetched=len(articles),
		saved=len(articles),
		message="PubMed 增量同步完成，结果已写入数据库",
	)
