"""新闻聚类模块 - 可扩展的聚类框架"""

from .base import BaseClusterer
from .similarity import SimilarityClusterer
from .factory import ClustererFactory

__all__ = ["BaseClusterer", "SimilarityClusterer", "ClustererFactory"]
