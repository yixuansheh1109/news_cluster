from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from .pipeline import NewsPipeline
from .pipeline.processors import ClusteringProcessor, DeduplicationProcessor


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "clustering_config.v1.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
    return records


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def resolve_config(preset: str, config_path: Path, overrides: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    full_config = read_json(config_path) if config_path.exists() else {}
    clustering = full_config.get("clustering") or {}
    presets = clustering.get("presets") or {}
    selected = presets.get(preset) or presets.get(clustering.get("default_clusterer")) or {}
    clusterer_type = str(selected.get("type") or preset or "similarity")
    config = dict(selected.get("config") or {})
    config.update({key: value for key, value in overrides.items() if value is not None})
    return clusterer_type, config


def cluster_file(
    input_path: Path,
    out_path: Path,
    config_path: Path,
    preset: str,
    threshold: float | None,
    dedup: bool,
) -> None:
    articles = read_jsonl(input_path)
    clusterer_type, config = resolve_config(preset, config_path, {"threshold": threshold})

    pipeline = NewsPipeline(name="news_cluster")
    if dedup:
        pipeline.add_stage(DeduplicationProcessor())
    pipeline.add_stage(ClusteringProcessor(clusterer_type=clusterer_type, config=config))
    result = pipeline.execute(articles, verbose=True)

    cluster_payload = result.get("cluster_payload") or {"clusters": result.get("clusters") or []}
    clustered_articles = result.get("articles") or articles
    articles_out = out_path.with_suffix(".articles.jsonl")

    write_json(out_path, cluster_payload)
    write_jsonl(articles_out, clustered_articles)
    print(f"input_articles={len(articles)}")
    print(f"cluster_count={cluster_payload.get('cluster_count', 0)}")
    print(f"clusters={out_path}")
    print(f"clustered_articles={articles_out}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone news article clustering tool")
    parser.add_argument("--input", type=Path, required=True, help="Input JSONL file containing article records")
    parser.add_argument("--out", type=Path, required=True, help="Output JSON file for cluster summary")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Clustering config JSON")
    parser.add_argument("--preset", default="similarity", help="Config preset name")
    parser.add_argument("--threshold", type=float, default=None, help="Override similarity threshold")
    parser.add_argument("--dedup", action="store_true", help="Remove exact duplicate article identities first")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    cluster_file(
        input_path=args.input,
        out_path=args.out,
        config_path=args.config,
        preset=args.preset,
        threshold=args.threshold,
        dedup=args.dedup,
    )


if __name__ == "__main__":
    main()
