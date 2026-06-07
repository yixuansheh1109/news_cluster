from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Protocol


def stable_hash(parts: Iterable[Any], length: int = 16) -> str:
    payload = json.dumps(list(parts), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


@dataclass(frozen=True)
class ArticleRef:
    article_id: str | None
    title: str
    url: str
    source: str | None
    published_at: str | None
    hot_score: float | None = None
    quality_score: float | None = None


@dataclass
class ClusterResult:
    cluster_id: str
    size: int
    representative_article_id: str | None
    representative_title: str
    article_ids: list[str]
    articles: list[dict[str, Any]]
    score: float
    keywords: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    first_published_at: str | None = None
    last_published_at: str | None = None
    created_at: str | None = None

    def to_dict(self, include_articles: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "cluster_id": self.cluster_id,
            "size": self.size,
            "representative_article_id": self.representative_article_id,
            "representative_title": self.representative_title,
            "article_ids": self.article_ids,
            "score": self.score,
            "keywords": self.keywords,
            "sources": self.sources,
            "first_published_at": self.first_published_at,
            "last_published_at": self.last_published_at,
            "created_at": self.created_at,
        }
        if include_articles:
            payload["articles"] = self.articles
        return payload


class BaseClusterer(Protocol):
    name: str
    config: dict[str, Any]
    clusters: list[ClusterResult]

    def cluster(self, articles: list[dict[str, Any]]) -> list[ClusterResult]:
        ...

    def annotate_articles(self, articles: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        ...

    def to_payload(self, include_articles: bool = True) -> dict[str, Any]:
        ...

    def save_clusters(self, output_path: str | Path, include_articles: bool = True) -> dict[str, Any]:
        ...


class ClustererMixin:
    name: str
    config: dict[str, Any]
    clusters: list[ClusterResult]

    def annotate_articles(self, articles: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        source_articles = articles if articles is not None else [article for cluster in self.clusters for article in cluster.articles]
        cluster_by_article: dict[str, ClusterResult] = {}
        for cluster in self.clusters:
            for article_id in cluster.article_ids:
                cluster_by_article[article_id] = cluster

        annotated: list[dict[str, Any]] = []
        for article in source_articles:
            copied = dict(article)
            article_id = str(article.get("article_id") or "")
            cluster = cluster_by_article.get(article_id)
            if cluster:
                copied["cluster_info"] = {
                    "cluster_id": cluster.cluster_id,
                    "cluster_size": cluster.size,
                    "representative_article_id": cluster.representative_article_id,
                    "representative_title": cluster.representative_title,
                    "is_representative": article_id == cluster.representative_article_id,
                    "cluster_score": cluster.score,
                    "keywords": cluster.keywords,
                }
            annotated.append(copied)
        return annotated

    def to_payload(self, include_articles: bool = True) -> dict[str, Any]:
        total_articles = sum(cluster.size for cluster in self.clusters)
        created_at = datetime.now().isoformat()
        return {
            "schema_version": "1.0",
            "clusterer": self.name,
            "config": self.config,
            "created_at": created_at,
            "total_articles": total_articles,
            "cluster_count": len(self.clusters),
            "multi_article_cluster_count": sum(1 for cluster in self.clusters if cluster.size > 1),
            "clusters": [cluster.to_dict(include_articles=include_articles) for cluster in self.clusters],
        }

    def save_clusters(self, output_path: str | Path, include_articles: bool = True) -> dict[str, Any]:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.to_payload(include_articles=include_articles)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        return {
            "output_path": str(path),
            "total_articles": payload["total_articles"],
            "cluster_count": payload["cluster_count"],
            "multi_article_cluster_count": payload["multi_article_cluster_count"],
        }
