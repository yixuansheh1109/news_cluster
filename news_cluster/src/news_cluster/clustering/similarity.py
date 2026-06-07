from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Any

from .base import ClusterResult, ClustererMixin, stable_hash


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "into",
    "that",
    "this",
    "news",
    "article",
}


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def article_time(article: dict[str, Any]) -> datetime | None:
    time_info = article.get("time_info") or {}
    return parse_dt(time_info.get("published_at") or article.get("published_at") or article.get("crawled_at"))


def hot_score(article: dict[str, Any]) -> float:
    hotness = article.get("hotness") or {}
    value = hotness.get("score")
    if isinstance(value, (int, float)):
        return float(value)
    return float(article.get("quality_score") or 0.0)


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return
        if self.rank[root_left] < self.rank[root_right]:
            self.parent[root_left] = root_right
        elif self.rank[root_left] > self.rank[root_right]:
            self.parent[root_right] = root_left
        else:
            self.parent[root_right] = root_left
            self.rank[root_left] += 1


class SimilarityClusterer(ClustererMixin):
    """Dependency-free article clusterer for grouping the same story across sources."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.name = "similarity"
        self.config = {
            "threshold": 0.42,
            "title_weight": 0.65,
            "content_weight": 0.25,
            "keyword_weight": 0.10,
            "time_window_hours": 72,
            "min_shared_tokens": 2,
            "max_articles": 2000,
            "include_singletons": True,
            "max_keywords": 8,
        }
        self.config.update(config or {})
        self.clusters: list[ClusterResult] = []
        self._features: list[dict[str, Any]] = []

    def cluster(self, articles: list[dict[str, Any]]) -> list[ClusterResult]:
        if not articles:
            self.clusters = []
            self._features = []
            return []
        max_articles = int(self.config.get("max_articles") or 2000)
        if len(articles) > max_articles:
            raise ValueError(f"clustering input has {len(articles)} articles; max_articles={max_articles}")

        self._features = [self.extract_features(article) for article in articles]
        uf = UnionFind(len(articles))

        for i in range(len(articles)):
            for j in range(i + 1, len(articles)):
                if self._same_identity(articles[i], articles[j]):
                    uf.union(i, j)
                    continue
                if not self._within_time_window(self._features[i], self._features[j]):
                    continue
                similarity = self.calculate_similarity(self._features[i], self._features[j])
                shared = len(self._features[i]["all_tokens"] & self._features[j]["all_tokens"])
                if similarity >= float(self.config["threshold"]) and shared >= int(self.config["min_shared_tokens"]):
                    uf.union(i, j)

        groups: dict[int, list[int]] = {}
        for idx in range(len(articles)):
            groups.setdefault(uf.find(idx), []).append(idx)

        clusters = [self._build_cluster(indexes, articles) for indexes in groups.values()]
        if not bool(self.config.get("include_singletons", True)):
            clusters = [cluster for cluster in clusters if cluster.size > 1]
        clusters.sort(key=lambda cluster: (cluster.size, cluster.score, cluster.last_published_at or ""), reverse=True)
        self.clusters = clusters
        return clusters

    def extract_features(self, article: dict[str, Any]) -> dict[str, Any]:
        content_info = article.get("content_info") or {}
        keyword_values = [compact_text(value).lower() for value in article.get("keywords") or content_info.get("keywords") or []]
        title = compact_text(article.get("title"))
        excerpt = compact_text(content_info.get("excerpt") or article.get("content"))
        title_tokens = self._tokens(title)
        content_tokens = self._tokens(excerpt)
        keyword_tokens = {token for value in keyword_values for token in self._tokens(value)}
        return {
            "title_tokens": title_tokens,
            "content_tokens": content_tokens,
            "keyword_tokens": keyword_tokens,
            "all_tokens": title_tokens | content_tokens | keyword_tokens,
            "published_at": article_time(article),
        }

    def calculate_similarity(self, left: dict[str, Any], right: dict[str, Any]) -> float:
        title = self._jaccard(left["title_tokens"], right["title_tokens"])
        content = self._cosine(left["content_tokens"], right["content_tokens"])
        keywords = self._jaccard(left["keyword_tokens"], right["keyword_tokens"])
        if not left["keyword_tokens"] and not right["keyword_tokens"]:
            keywords = 0.0
        score = (
            title * float(self.config["title_weight"])
            + content * float(self.config["content_weight"])
            + keywords * float(self.config["keyword_weight"])
        )
        return round(min(max(score, 0.0), 1.0), 6)

    def _tokens(self, text: str) -> set[str]:
        normalized = text.lower()
        latin = {
            token
            for token in re.findall(r"[a-z0-9][a-z0-9_.-]{1,}", normalized)
            if token not in STOPWORDS and len(token) > 1
        }
        cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
        cjk = {"".join(cjk_chars[i : i + size]) for size in (2, 3) for i in range(0, max(len(cjk_chars) - size + 1, 0))}
        return latin | cjk

    def _same_identity(self, left: dict[str, Any], right: dict[str, Any]) -> bool:
        for key in ("article_id", "url", "content_hash", "title_hash"):
            left_value = left.get(key)
            right_value = right.get(key)
            if left_value and right_value and left_value == right_value:
                return True
        return False

    def _within_time_window(self, left: dict[str, Any], right: dict[str, Any]) -> bool:
        hours = self.config.get("time_window_hours")
        if hours is None:
            return True
        left_dt = left.get("published_at")
        right_dt = right.get("published_at")
        if not left_dt or not right_dt:
            return True
        return abs((left_dt - right_dt).total_seconds()) <= float(hours) * 3600

    def _build_cluster(self, indexes: list[int], articles: list[dict[str, Any]]) -> ClusterResult:
        cluster_articles = [articles[idx] for idx in indexes]
        representative = max(cluster_articles, key=lambda article: (hot_score(article), float(article.get("quality_score") or 0.0), article.get("title") or ""))
        article_ids = [str(article.get("article_id") or stable_hash([article.get("url"), article.get("title")])) for article in cluster_articles]
        times = sorted(filter(None, (article.get("published_at") or article.get("crawled_at") for article in cluster_articles)))
        token_counter: Counter[str] = Counter()
        for idx in indexes:
            token_counter.update(self._features[idx]["title_tokens"])
            token_counter.update(self._features[idx]["keyword_tokens"])
        max_keywords = int(self.config.get("max_keywords") or 8)
        keywords = [token for token, _ in token_counter.most_common(max_keywords)]
        sources = sorted({str(article.get("source") or article.get("source_id") or "unknown") for article in cluster_articles})
        cluster_id = "cl_" + stable_hash(sorted(article_ids))
        return ClusterResult(
            cluster_id=cluster_id,
            size=len(cluster_articles),
            representative_article_id=str(representative.get("article_id") or ""),
            representative_title=str(representative.get("title") or ""),
            article_ids=article_ids,
            articles=cluster_articles,
            score=round(sum(hot_score(article) for article in cluster_articles) / max(len(cluster_articles), 1), 4),
            keywords=keywords,
            sources=sources,
            first_published_at=times[0] if times else None,
            last_published_at=times[-1] if times else None,
            created_at=datetime.now().isoformat(),
        )

    def _jaccard(self, left: set[str], right: set[str]) -> float:
        if not left and not right:
            return 0.0
        return len(left & right) / len(left | right)

    def _cosine(self, left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / math.sqrt(len(left) * len(right))
