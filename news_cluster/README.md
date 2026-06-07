# News Cluster

Standalone news article clustering tool extracted from the news ingestion project.

It groups articles that appear to describe the same story, event, or topic, and writes:

- `clusters.json`: cluster summaries, representative article, keywords, source list, and article IDs
- `clusters.articles.jsonl`: original articles annotated with `cluster_info`

The implementation is dependency-free and uses deterministic title/content token similarity, so it is easy to run in local scripts, CI, or small production jobs.

## Project Layout

```text
news_cluster/
  config/clustering_config.v1.json
  examples/articles.sample.jsonl
  src/news_cluster/
    cli.py
    clustering/
    pipeline/
```

## Run

From this folder:

```powershell
$env:PYTHONPATH = "src"
python -m news_cluster.cli --input examples/articles.sample.jsonl --out output/clusters.json
```

Use a stricter preset:

```powershell
$env:PYTHONPATH = "src"
python -m news_cluster.cli --input examples/articles.sample.jsonl --out output/clusters.json --preset similarity_strict
```

Override the threshold:

```powershell
$env:PYTHONPATH = "src"
python -m news_cluster.cli --input examples/articles.sample.jsonl --out output/clusters.json --threshold 0.5
```

## Input Format

Input is JSONL: one JSON article per line. Recommended fields:

- `article_id`
- `title`
- `url`
- `source`
- `published_at`
- `content`
- `keywords`
- `quality_score`
- `hotness.score`

Unknown fields are preserved in the annotated output.

## Output

Each annotated article receives:

```json
{
  "cluster_info": {
    "cluster_id": "cl_...",
    "cluster_size": 2,
    "representative_article_id": "...",
    "representative_title": "...",
    "is_representative": true,
    "cluster_score": 42.0,
    "keywords": ["..."]
  }
}
```
