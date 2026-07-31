"""PubMed adapter for fetching and normalizing literature metadata."""

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional

from article_repository.search.query_builder import (
    build_query_variants,
    build_query_with_date_from,
)


def _request_json(url: str) -> Dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "BioFLow-ArticleRepo/0.1"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _safe_text(element, tag_name: str) -> str:
    child = element.find(tag_name) if element is not None else None
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _parse_date(pub_date_elem) -> Optional[datetime]:
    if pub_date_elem is None:
        return None
    year = _safe_text(pub_date_elem, "Year")
    month = _safe_text(pub_date_elem, "Month")
    day = _safe_text(pub_date_elem, "Day")
    if not year:
        return None
    try:
        month_num = int(month) if month.isdigit() else 1
        day_num = int(day) if day.isdigit() else 1
        return datetime(int(year), month_num, day_num)
    except Exception:
        return None


def _extract_abstract(article) -> str:
    abstract_text = []
    for abstract_elem in article.findall("./Abstract/AbstractText"):
        if abstract_elem.text:
            abstract_text.append(abstract_elem.text.strip())
    return "\n".join(abstract_text)


def _extract_authors(article) -> List[Dict]:
    authors = []
    for author in article.findall("./AuthorList/Author"):
        last_name = _safe_text(author, "LastName")
        initials = _safe_text(author, "Initials")
        name = f"{last_name} {initials}".strip()
        if not name:
            name = _safe_text(author, "CollectiveName")
        if name:
            authors.append({"name": name, "affiliation": ""})
    return authors


def _extract_keywords(article) -> List[str]:
    keywords = []
    for keyword in article.findall("./KeywordList/Keyword"):
        value = (keyword.text or "").strip()
        if value:
            keywords.append(value)
    return keywords


def fetch_pubmed_articles(
    keywords: Optional[List[str]] = None,
    mode: str = "balanced",
    years_back: int = 10,
    retmax: int = 50,
    date_from: Optional[datetime] = None,
) -> List[Dict]:
    """Fetch PubMed literature metadata for the given keywords and normalize it.

    Args:
        keywords: 搜索关键词列表，默认 ["自闭症", "肠道菌群"]
        mode: 检索模式 strict/balanced/broad
        years_back: 往前回溯的年数（date_from 为 None 时生效）
        retmax: 最大返回数量
        date_from: 增量同步的起始日期，仅拉取该日期之后发表的文章

    Returns:
        归一化后的文献元数据列表
    """
    if keywords is None:
        keywords = ["自闭症", "肠道菌群"]

    # 增量模式 vs 全量模式：使用不同的查询策略
    if date_from is not None:
        # 增量模式：使用带 date_from 的 broad 检索式，最大化召回
        query = build_query_with_date_from(
            keywords, mode="broad", date_from=date_from, years_back=0
        )
        query_variants = [query]
    else:
        # 全量模式：使用渐进式多级查询（strict → balanced → broad）
        query_variants = build_query_variants(keywords, years_back=years_back)

    seen_ids = set()
    articles: List[Dict] = []
    last_error: Optional[Exception] = None

    for query in query_variants:
        # PubMed E-utilities 限流：无 API key 时每秒最多 3 次请求
        # 每次 esearch + efetch 共 2 次请求，间隔 0.4 秒确保安全
        time.sleep(0.4)

        search_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            "?db=pubmed&retmode=json&retmax={retmax}&term={term}"
        ).format(retmax=retmax, term=urllib.parse.quote(query))
        try:
            search_result = _request_json(search_url)
        except Exception as exc:
            last_error = exc
            continue

        id_list = search_result.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            continue

        # 请求间隔
        time.sleep(0.4)

        fetch_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            "?db=pubmed&id={ids}&retmode=xml&rettype=abstract"
        ).format(ids=",".join(id_list))
        try:
            fetch_result = urllib.request.urlopen(
                urllib.request.Request(
                    fetch_url,
                    headers={"User-Agent": "BioFLow-ArticleRepo/0.1"},
                ),
                timeout=30,
            )
        except Exception as exc:
            last_error = exc
            continue

        xml_text = fetch_result.read().decode("utf-8", errors="ignore")
        try:
            import xml.etree.ElementTree as ET

            root = ET.fromstring(xml_text)
        except Exception as exc:
            raise RuntimeError(f"PubMed XML 解析失败: {exc}") from exc

        for pubmed_article in root.findall("./PubmedArticle"):
            medline = pubmed_article.find("MedlineCitation")
            if medline is None:
                continue
            article = medline.find("Article")
            pmid = _safe_text(medline, "PMID")
            if not pmid or pmid in seen_ids:
                continue
            seen_ids.add(pmid)
            title = _safe_text(article, "ArticleTitle") if article is not None else ""
            abstract = _extract_abstract(article) if article is not None else ""
            journal_title = _safe_text(article.find("Journal"), "Title") if article is not None and article.find("Journal") is not None else ""
            pub_date = _parse_date(article.find("Journal/JournalIssue/PubMedPubDate")) if article is not None else None

            doi = ""
            article_id_list = article.find("ArticleIdList") if article is not None else None
            if article_id_list is not None:
                for article_id in article_id_list.findall("ArticleId"):
                    if article_id.attrib.get("IdType") == "doi":
                        doi = (article_id.text or "").strip()
                        break

            keywords = _extract_keywords(article) if article is not None else []
            authors = _extract_authors(article) if article is not None else []

            article_payload = {
                "doi": doi or f"pubmed:{pmid}",
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "publish_time": pub_date or datetime.now(),
                "journal": journal_title,
                "journal_division": None,
                "citation_count": 0,
                "keywords": keywords,
                "llm_tags": {},
                "source": "PubMed",
            }
            articles.append(article_payload)

        if len(articles) >= retmax:
            break

    if not articles and last_error is not None:
        raise RuntimeError(f"PubMed 检索失败: {last_error}") from last_error

    return articles


def save_pubmed_articles(repo, articles: List[Dict], incremental: bool = False) -> int:
    """Persist fetched PubMed articles to the repository."""
    if repo is None:
        from article_repository.storage.repository import LiteratureRepository

        repo = LiteratureRepository()
    if incremental:
        repo.increment_update_task(articles)
    else:
        repo.full_batch_save(articles)
    return len(articles)