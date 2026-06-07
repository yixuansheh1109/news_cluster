from __future__ import annotations

from typing import Any

from .base import BaseClusterer
from .similarity import SimilarityClusterer


class ClustererFactory:
    _registry: dict[str, type[BaseClusterer]] = {}

    @classmethod
    def register(cls, name: str, clusterer_class: type[BaseClusterer]) -> None:
        cls._registry[name] = clusterer_class

    @classmethod
    def create(cls, clusterer_type: str = "similarity", config: dict[str, Any] | None = None) -> BaseClusterer:
        clusterer_class = cls._registry.get(clusterer_type)
        if not clusterer_class:
            available = ", ".join(sorted(cls._registry)) or "<none>"
            raise ValueError(f"Unknown clusterer type '{clusterer_type}'. Available types: {available}")
        return clusterer_class(config=config)

    @classmethod
    def list_available(cls) -> list[str]:
        return sorted(cls._registry)


ClustererFactory.register("similarity", SimilarityClusterer)
