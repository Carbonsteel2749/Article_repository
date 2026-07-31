# Article Repository

面向“自闭症 + 肠道菌群”文献场景的结构化仓库。

## 主要功能

### 1. 文献抓取与增量更新

  ** 首次全量抓取：**自动从权威库（PubMed；OpenAlex, Semantic Scholar, Crossref补充）抓取自闭症与肠道菌群相关的历史文献元数据（标题、摘要、作者、DOI、发表时间）。
   **定时增量更新：**每月自动监控数据源，仅抓取新发表的文献，入库。

### 2. 检索与归类

  ** AI自动打标签：**系统自动调用大模型识别出每篇文献里的核心菌种、实验模型、干预手段、数据种类、分析方法等学术上较为关心的维度
 **  精准检索：**通过关键词或标签进行快速检索，深度检索。

### 3. 文献综述与问答预置

   **常见问题预置（FAQ）：**主页提供经典问题一键提问。
   **基于文献的问答（RAG）：**用户可以提出文献检索要求。系统从数据库和联网搜索结果返回契合的n篇文献，用户可以查看、选择部分文献并进行文献综述。

## 目录结构

```text
Article_repository/
├── README.md
├── pyproject.toml
├── article_repository/
│   ├── __init__.py
│   ├── config.py
│   ├── constants.py
│   ├── paths.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── article.py
│   │   ├── source.py
│   │   ├── tagging.py
│   │   └── query.py
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── sources/
│   │   │   ├── __init__.py
│   │   │   ├── pubmed.py
│   │   │   ├── openalex.py
│   │   │   ├── semantic_scholar.py
│   │   │   └── crossref.py
│   │   ├── full_sync.py
│   │   ├── incremental_sync.py
│   │   └── pipeline.py
│   ├── classification/
│   │   ├── __init__.py
│   │   ├── tagger.py
│   │   ├── schema.py
│   │   └── prompts.py
│   ├── search/
│   │   ├── __init__.py
│   │   ├── keyword_search.py
│   │   ├── tag_search.py
│   │   └── deep_search.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── faq.py
│   │   ├── retrieval.py
│   │   ├── selection.py
│   │   └── summarization.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── repository.py
│   │   ├── metadata_store.py
│   │   └── indexes.py
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── sync_workflow.py
│   │   ├── tagging_workflow.py
│   │   └── rag_workflow.py
│   └── api/
│       ├── __init__.py
│       ├── app.py
│       ├── routes.py
│       └── schemas.py
├── configs/
│   └── example.yaml
├── data/
│   ├── raw/
│   ├── processed/
│   └── indexes/
└── tests/
    └── README.md
```

## 模块说明

### ingestion

负责各数据源适配、全量同步、增量同步和统一入库流程。

### classification

负责大模型标签抽取与标准化，输出可检索的结构化标签。

### search

负责关键词检索、标签检索和深度检索入口，为前端和 API 提供统一查询能力。

### rag

负责 FAQ 预置、文献召回、文献筛选和综述生成的工作流编排。

### storage

负责元数据、标签、索引和中间结果的持久化抽象。

### workflows

负责把抓取、归类、检索、综述串成可调度的流程。

### api

负责后续对外提供 HTTP 接口。

## 当前状态

**已完成：**结构设计、模块划分、能力边界说明

**未实现：**真实数据抓取、标签抽取、向量检索、FAQ、RAG、API 服务
