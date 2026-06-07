from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class PipelineStage:
    name: str
    description: str
    enabled: bool = True


class PipelineProcessor(Protocol):
    def process(self, articles: list[dict[str, Any]]) -> dict[str, Any]:
        ...

    def get_stage_info(self) -> PipelineStage:
        ...


class NewsPipeline:
    def __init__(self, name: str = "default") -> None:
        self.name = name
        self.stages: list[PipelineProcessor] = []
        self.stage_results: dict[str, dict[str, Any]] = {}
        self.metadata: dict[str, Any] = {
            "name": name,
            "created_at": datetime.now().isoformat(),
            "stages": [],
        }

    def add_stage(self, processor: PipelineProcessor) -> None:
        stage = processor.get_stage_info()
        self.stages.append(processor)
        self.metadata["stages"].append(
            {
                "name": stage.name,
                "description": stage.description,
                "enabled": stage.enabled,
            }
        )

    def execute(self, articles: list[dict[str, Any]], verbose: bool = False) -> dict[str, Any]:
        current: dict[str, Any] = {"articles": articles}
        for index, processor in enumerate(self.stages, 1):
            stage = processor.get_stage_info()
            if not stage.enabled:
                if verbose:
                    print(f"[skip] {stage.name}")
                continue
            if verbose:
                print(f"[stage {index}/{len(self.stages)}] {stage.name}: {stage.description}")
            result = processor.process(current.get("articles", []))
            self.stage_results[stage.name] = result
            current.update(result)
            if verbose:
                print(f"[ok] {stage.name}: {self._format_stats(result)}")
        current["pipeline_metadata"] = self.metadata
        current["executed_at"] = datetime.now().isoformat()
        return current

    def _format_stats(self, result: dict[str, Any]) -> str:
        stats = result.get("stats") or {}
        if stats:
            return ", ".join(f"{key}={value}" for key, value in stats.items())
        if "articles" in result:
            return f"articles={len(result['articles'])}"
        return "done"
