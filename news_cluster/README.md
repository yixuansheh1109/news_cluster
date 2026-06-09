# News Cluster 新闻聚类工具

`news_cluster` 是一个轻量级新闻聚类工具，用来把报道同一事件、同一主题或同一故事的新闻文章聚合到一起。

它适合用于新闻采集后的数据清洗流程，减少重复报道，为后续的新闻评分、排序、推荐或事件库建设做准备。

当前版本默认使用 `jieba` 进行中文分词，并保留无依赖 fallback：如果运行环境没有安装 `jieba`，工具会自动回退到中文 2/3 字符 n-gram token，避免程序直接中断。

## 功能特点

- 读取 JSONL 格式的新闻文章数据
- 默认使用 `jieba` 对中文标题、正文和关键词进行分词
- 根据标题、正文摘要、关键词和发布时间进行相似度聚类
- 支持可选精确去重
- 为每篇文章添加 `cluster_info`
- 输出新闻簇文件 `clusters.json`
- 输出带聚类信息的文章文件 `clusters.articles.jsonl`
- 支持默认、严格、宽松三种聚类配置
- 可作为独立工具运行，也可以接在新闻采集 agent 后面使用

## 适用场景

这个工具可以用于：

- 去除新闻采集结果中的重复报道
- 把多个来源对同一事件的报道合并成一个新闻簇
- 在下游评分系统中按“事件”而不是按“单篇文章”打分
- 对财经新闻、政策新闻、公司新闻等进行初步事件归并
- 为新闻 ranking / scoring 系统准备更干净的输入数据

推荐处理流程：

```text
新闻采集
-> 数据清洗 / 校验
-> 精确去重
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

推荐使用 Python 3.10 或以上版本。

安装依赖：

```powershell
pip install -r requirements.txt
```

当前依赖：

```text
jieba>=0.42.1
```

如果没有安装 `jieba`，程序仍然可以运行，但会回退到中文 n-gram token。回退模式更轻量，但中文分词质量不如 `jieba`。

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

## 使用精确去重

如果希望在聚类前先删除完全重复或高度重复的文章，可以加上 `--dedup`：

```powershell
$env:PYTHONPATH = "src"
python -m news_cluster.cli `
  --input examples/articles.sample.jsonl `
  --out output/clusters.json `
  --dedup
```

默认去重优先使用：

```text
article_id
url
content_hash
title_hash
title
```

注意：去重和聚类不是同一件事。

- 去重：删除完全重复或几乎完全相同的记录
- 聚类：把不是完全重复、但报道同一事件的文章归到同一组

推荐流程是：

```text
先 exact dedup
再 similarity clustering
```

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

## token 和关键词是怎么来的

当前版本默认使用 `jieba` 对中文文本进行分词。

工具会从三类字段提取 token：

```text
title
content / content_info.excerpt
keywords
```

对应生成：

```text
title_tokens
content_tokens
keyword_tokens
```

例如标题：

```text
央行宣布降准释放长期资金
```

使用 `jieba` 后可能得到：

```text
央行
宣布
降准
释放
长期
资金
```

这些 token 会参与文章相似度计算。

如果没有安装 `jieba`，工具会回退到中文 2/3 字符 n-gram，例如：

```text
央行
宣布
降准
释放
长期
资金
央行宣
宣布降
降准释
```

cluster 输出里的 `keywords` 不是大模型生成的，而是从簇内文章的标题 token 和原始 `keywords` 字段中统计出的高频 token。

## 聚类逻辑说明

当前版本使用确定性的相似度聚类方法。

主要步骤：

```text
1. 读取文章
2. 可选精确去重
3. 用 jieba 提取中文 token
4. 提取英文、数字、股票代码等 token
5. 分别计算标题、正文、关键词相似度
6. 使用发布时间窗口过滤明显不相关的文章
7. 相似度超过阈值时合并文章
8. 为每个新闻簇选择代表文章
```

默认相似度权重：

```text
title_weight = 0.65
content_weight = 0.25
keyword_weight = 0.10
```

标题权重最高，因为新闻标题通常最能表达事件核心。

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
  "max_keywords": 8,
  "tokenizer": "jieba",
  "fallback_to_ngrams": true
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
- `tokenizer`：中文分词器，当前推荐 `jieba`
- `fallback_to_ngrams`：当 `jieba` 不可用时，是否回退到中文 n-gram

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

所以本工具既输出：

```text
新闻簇列表
```

也输出：

```text
每篇文章所属的 cluster 属性
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
  --out output/clusters_20260607.json `
  --dedup
```

如果 `news_cluster` 和采集项目在同一个 workspace 下：

```text
workspace/
  news-ingestion-v1/
  news_cluster/
```

可以在 `news-ingestion-v1` 目录下运行：

```powershell
$env:PYTHONPATH = "..\news_cluster\src"
python -m news_cluster.cli `
  --input data\daily\20260607\articles_20260607.jsonl `
  --out ..\news_cluster\output\clusters_20260607.json `
  --dedup
```

## 当前方案的优点和边界

优点：

- 使用 `jieba` 后，中文 token 质量比纯字符 n-gram 更好
- 算法可解释，方便汇报和调试
- 不依赖大模型或外部 API
- 支持 fallback，环境不完整时也能运行
- 输出结构清楚，适合下游 ranking system 使用

边界：

- 它不是大模型语义聚类
- 标题差异很大的同事件新闻可能漏聚
- 使用相同财经高频词但事件不同的新闻可能误聚
- 当前相似度比较适合百级到低千级文章，大规模数据需要候选召回优化

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

- 加入自定义财经词典，提高 `jieba` 对公司名、股票代码、机构名的识别
- 增加 cluster confidence 聚类置信度
- 增加 avg_pair_similarity / min_pair_similarity 等质量指标
- 增加 cluster 级热度、来源覆盖度、时效性特征
- 面向下游 ranking system 输出更完整的事件级特征
- 针对大规模数据增加候选召回和分桶策略

## License

当前项目暂未指定 License。上传公开仓库前，建议根据使用目标添加合适的开源协议。
