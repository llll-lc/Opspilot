# OP-005 知识与 RAG 资产

`sources.json` 是本任务唯一的知识来源 manifest：每项都保存来源链接、访问日期、目标版本、许可/再分发边界、局部派生笔记的 SHA-256。`corpus/` 不保存第三方正文；官方条目均为短小的项目自编派生笔记。三个 `runbook-*` 文件均醒目标为合成的 OpsPilot 演示材料。

`evaluation/frozen_queries.json` 固定 12 条检索查询和其支持来源真值。它不是根因或工具真值，不能被模型重写；同一索引、同一范围过滤、同一查询集依次运行 Dense、Dense+exact、hybrid 和 reranked 四组。

## 实际本地运行

先显式启动并迁移 OpsPilot 自己的 pgvector 数据库；这不会启动 Superset、Provider 或任何 Tool Gateway。

```powershell
docker compose --project-name opspilot-op005 --profile core up -d postgres
$env:DATABASE_URL = "postgresql+psycopg://opspilot:opspilot-local-only@127.0.0.1:55432/opspilot"
uv --cache-dir .cache/uv run alembic upgrade head
uv --cache-dir .cache/uv run pytest --no-cov tests/integration
uv --cache-dir .cache/uv run python labs/op005/run_rag_evaluation.py `
  --report evidence/OP-005_RAG_ABLATION_YYYY-MM-DD.json
```

模型必须指向配置化的 `EMBEDDING_MODEL_PATH` / `RERANKER_MODEL_PATH`，默认分别是 `D:\Agent\models\bge-m3` 与 `D:\Agent\models\bge-reranker-large`。Windows 使用 fast `tokenizer.json` 和非 mmap legacy `.bin` 加载；CPU 请求由进程内锁串行化。Reranker 只在最后一个消融组按需加载，默认关闭。

每条最终命中包含来源 key、URL/object locator、标题路径、原文行定位、短引用、冻结索引版本和父块上下文。检索固定先强制组织、目标、索引、可见性、来源类型和目标版本过滤；随后才允许精确、Dense、Sparse、RRF 与可选重排。
