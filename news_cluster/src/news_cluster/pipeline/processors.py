from __future__ import annotations

from typing import Any, Callable

from .framework import PipelineStage
from ..clustering import ClustererFactory


class DeduplicationProcessor:
    def __init__(self, key_func: Callable[[dict[str, Any]], str] | None = None) -> None:
        self.key_func = key_func or self._default_key

    def process(self, articles: list[dict[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        deduplicated: list[dict[str, Any]] = []
        for article in articles:
            key = self.key_func(article)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(article)
        return {
            "articles": deduplicated,
            "stats": {
                "input_count": len(articles),
                "output_count": len(deduplicated),
                "duplicates_removed": len(articles) - len(deduplicated),
            },
        }

    def get_stage_info(self) -> PipelineStage:
        return PipelineStage(name="deduplication", description="Remove exact duplicate articles before clustering.")

    def _default_key(self, article: dict[str, Any]) -> str:
        return str(
            article.get("article_id")
            or article.get("url")
            or article.get("content_hash")
            or article.get("title_hash")
            or article.get("title")
            or ""
        )


class ClusteringProcessor:
    def __init__(self, clusterer_type: str = "similarity", config: dict[str, Any] | None = None) -> None:
        self.clusterer_type = clusterer_type
        self.config = config or {}
        self.clusterer = ClustererFactory.create(clusterer_type, config=self.config)

    def process(self, articles: list[dict[str, Any]]) -> dict[str, Any]:
        clusters = self.clusterer.cluster(articles)
        annotated = self.clusterer.annotate_articles(articles)
        return {
            "articles": annotated,
            "clusters": [cluster.to_dict(include_articles=False) for cluster in clusters],
            "cluster_payload": self.clusterer.to_payload(include_articles=True),
            "stats": {
                "input_count": len(articles),
                "cluster_count": len(clusters),
                "multi_article_cluster_count": sum(1 for cluster in clusters if cluster.size > 1),
            },
        }

    def get_stage_info(self) -> PipelineStage:
        return PipelineStage(
            name=f"clustering:{self.clusterer_type}",
            description=f"Cluster articles with {self.clusterer_type}.",
        )


class FilteringProcessor:
    def __init__(self, predicate: Callable[[dict[str, Any]], bool] | None = None, description: str = "Filter articles.") -> None:
        self.predicate = predicate or (lambda article: True)
        self.description = description

    def process(self, articles: list[dict[str, Any]]) -> dict[str, Any]:
        filtered = [article for article in articles if self.predicate(article)]
        return {
            "articles": filtered,
            "stats": {
                "input_count": len(articles),
                "output_count": len(filtered),
                "filtered_out": len(articles) - len(filtered),
            },
        }

    def get_stage_info(self) -> PipelineStage:
        return PipelineStage(name="filtering", description=self.description)
