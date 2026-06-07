# News Cluster 新闻聚类工具

`news_cluster` 是一个轻量级新闻聚类工具，用来把报道同一事件、同一主题或同一故事的新闻文章聚合到一起。

它适合用于新闻采集后的数据清洗流程，减少重复报道，为后续的新闻评分、排序、推荐或事件库建设做准备。

## 功能特点

- 读取 JSONL 格式的新闻文章数据
- 根据标题、正文摘要、关键词和发布时间进行相似度聚类
- 为每篇文章添加 `cluster_info`
- 输出新闻簇文件 `clusters.json`
- 输出带聚类信息的文章文件 `clusters.articles.jsonl`
- 不依赖外部模型或第三方服务
- 适合本地脚本、定时任务和小型生产流程

## 适用场景

这个工具可以用于：

- 去除新闻采集结果中的重复报道
- 把多个来源对同一事件的报道合并成一个新闻簇
- 在下游评分系统中按“事件”而不是按“单篇文章”打分
- 对财经新闻、政策新闻、公司新闻等进行初步事件归并

推荐处理流程：

```text
新闻采集
-> 数据清洗 / 校验
-> 新闻聚类
-> 事件级评分 / 排名
-> 下游应用
```

## 项目结构

```text
news_cluster/
  README.md
  requirements.txt
  config/
    clustering_config.v1.json
  examples/
    articles.sample.jsonl
  src/
    news_cluster/
      cli.py
      clustering/
        base.py
        factory.py
        similarity.py
      pipeline/
        framework.py
        processors.py
```

## 环境要求

Python 3.10 或以上版本。

当前版本只使用 Python 标准库，不需要额外安装依赖。

## 快速开始

在 `news_cluster` 目录下运行：

```powershell
$env:PYTHONPATH = "src"
python -m news_cluster.cli --input examples/articles.sample.jsonl --out output/clusters.json
```

运行后会生成：

```text
output/clusters.json
output/clusters.articles.jsonl
```

其中：

- `clusters.json` 是聚类后的新闻簇汇总
- `clusters.articles.jsonl` 是带 `cluster_info` 的文章结果

## 使用不同聚类配置

默认配置在：

```text
config/clustering_config.v1.json
```

使用更严格的聚类配置：

```powershell
$env:PYTHONPATH = "src"
python -m news_cluster.cli `
  --input examples/articles.sample.jsonl `
  --out output/clusters.json `
  --preset similarity_strict
```

使用更宽松的聚类配置：

```powershell
$env:PYTHONPATH = "src"
python -m news_cluster.cli `
  --input examples/articles.sample.jsonl `
  --out output/clusters.json `
  --preset similarity_loose
```

手动覆盖相似度阈值：

```powershell
$env:PYTHONPATH = "src"
python -m news_cluster.cli `
  --input examples/articles.sample.jsonl `
  --out output/clusters.json `
  --threshold 0.5
```

## 输入格式

输入文件必须是 JSONL 格式，也就是一行一篇文章。

推荐字段：

```text
article_id
title
url
source
published_at
content
keywords
quality_score
hotness
```

最小可用示例：

```json
{"article_id":"a1","title":"央行宣布降准释放长期资金","url":"https://example.com/a1","source":"source_a","published_at":"2026-06-07T09:00:00+08:00","content":"央行宣布降准，预计释放长期流动性。","keywords":["央行","降准","流动性"]}
```

未知字段会被保留，不会被删除。

## 输出格式

### clusters.json

`clusters.json` 包含聚类汇总信息，例如：

```json
{
  "schema_version": "1.0",
  "clusterer": "similarity",
  "total_articles": 90,
  "cluster_count": 80,
  "multi_article_cluster_count": 9,
  "clusters": []
}
```

每个 cluster 包含：

```text
cluster_id
size
representative_article_id
representative_title
article_ids
score
keywords
sources
first_published_at
last_published_at
```

### clusters.articles.jsonl

`clusters.articles.jsonl` 保留原始文章字段，并为每篇文章增加：

```json
{
  "cluster_info": {
    "cluster_id": "cl_xxx",
    "cluster_size": 3,
    "representative_article_id": "a1",
    "representative_title": "央行宣布降准释放长期资金",
    "is_representative": true,
    "cluster_score": 82.5,
    "keywords": ["央行", "降准", "流动性"]
  }
}
```

## 和新闻采集 Agent 配合使用

如果你已经有一个新闻采集 agent，并且它输出 JSONL 文件，例如：

```text
data/daily/20260607/articles_20260607.jsonl
```

可以直接用本工具聚类：

```powershell
$env:PYTHONPATH = "src"
python -m news_cluster.cli `
  --input data/daily/20260607/articles_20260607.jsonl `
  --out output/clusters_20260607.json
```

如果 `news_cluster` 和采集项目在同一个 workspace 下，也可以这样运行：

```text
workspace/
  news-ingestion-v1/
  news_cluster/
```

在 `news-ingestion-v1` 目录下运行：

```powershell
$env:PYTHONPATH = "..\news_cluster\src"
python -m news_cluster.cli `
  --input data\daily\20260607\articles_20260607.jsonl `
  --out ..\news_cluster\output\clusters_20260607.json
```

## 聚类逻辑说明

当前版本使用确定性的相似度聚类方法：

- 提取标题 token
- 提取正文 / 摘要 token
- 提取关键词 token
- 使用时间窗口过滤明显不相关的文章
- 根据相似度阈值合并文章
- 为每个新闻簇选择代表文章

这种方法的优点是简单、稳定、可解释，不需要外部模型。

需要注意的是，它不是大模型语义聚类。对于标题差异很大但语义相同的新闻，可能会漏聚；对于使用相同财经关键词但事件不同的新闻，可能会误聚。可以通过调节配置文件里的阈值改善效果。

## 配置说明

主要配置项：

```json
{
  "threshold": 0.42,
  "title_weight": 0.65,
  "content_weight": 0.25,
  "keyword_weight": 0.1,
  "time_window_hours": 72,
  "min_shared_tokens": 2,
  "max_articles": 2000,
  "include_singletons": true,
  "max_keywords": 8
}
```

含义：

- `threshold`：相似度阈值，越高越严格
- `title_weight`：标题相似度权重
- `content_weight`：正文 / 摘要相似度权重
- `keyword_weight`：关键词相似度权重
- `time_window_hours`：只比较发布时间相近的文章
- `min_shared_tokens`：最少共享 token 数
- `max_articles`：单次最多处理文章数
- `include_singletons`：是否保留单篇文章簇
- `max_keywords`：每个簇最多输出关键词数

## 上传 GitHub 建议

建议上传这个目录内的文件：

```text
README.md
requirements.txt
.gitignore
config/
examples/
src/
```

不要上传运行产生的文件：

```text
output/
__pycache__/
*.pyc
```

这些已经写在 `.gitignore` 里。

## 后续改进方向

可以继续增强：

- 更好的中文分词
- 公司名、股票代码、机构名等实体识别
- 聚类置信度评分
- 更适合大规模数据的候选召回机制
- cluster 级别的热度和重要性评分
- 面向下游 ranking system 的事件级输出格式

## License

当前项目暂未指定 License。上传公开仓库前，建议根据使用目标添加合适的开源协议。
