# OP-001 可删除兼容性验证

本目录只包含风险闸门所需的最小探针，不是正式业务代码。它验证本地 BGE、DeepSeek、pgvector、Superset 和前端基线；`vendor/`、`runtime/` 与 `*.local.json` 均不提交。

## Python 环境

统一使用 Python 3.12，避免本机 `python`（3.12）与 `py` 默认版本（3.13）漂移：

```powershell
uv venv --python 3.12 .op001-venv
uv pip install --python .op001-venv\Scripts\python.exe -r spikes\op001\requirements-models.txt
```

## 模型基准

```powershell
.op001-venv\Scripts\python.exe spikes\op001\model_benchmark.py embedding --output spikes\op001\results\bge-m3.local.json
.op001-venv\Scripts\python.exe spikes\op001\model_benchmark.py reranker --output spikes\op001\results\bge-reranker-large.local.json
.op001-venv\Scripts\python.exe spikes\op001\model_benchmark.py combined --output spikes\op001\results\bge-combined.local.json
```

每个模式单进程、CPU、推理并发 1。脚本记录加载时间、输出维度/分数、短批次 P50/P95 与进程 RSS 峰值。

Windows 上 `sentencepiece==0.2.2` 对这两个 XLM-R tokenizer 触发原生访问冲突；脚本使用 BGE-M3 自带 fast `tokenizer.json`。两个模型的 SentencePiece 文件 SHA-256 相同，因此 reranker 的复用有文件级等价证据。脚本还绕过 Transformers 对 2+ GiB legacy `.bin` 的 mmap 快速路径，并对 reranker 只允许一个已知旧缓冲键。

## DeepSeek

把 `.env.example` 复制为未提交的 `.env` 并填写 Key：

```powershell
python spikes\op001\deepseek_compat.py --output spikes\op001\results\deepseek.local.json
```

探针不会输出 Key；普通对话、JSON、工具调用会发起最小真实请求。401 和超时使用真实请求验证，429 等官方错误码映射使用确定性断言验证，不通过制造流量触发限流。

## pgvector

```powershell
docker compose -f spikes\op001\compose.pgvector.yml --profile core up -d
```

临时容器使用 tmpfs，只验证 pgvector 0.8.6 能创建 `vector(1024)`，不创建正式业务表。

## Superset

```powershell
docker compose -f spikes\op001\compose.superset.yml --profile target-light up -d
python spikes\op001\superset_probe.py
docker compose -f spikes\op001\compose.superset.yml --profile target-light down --volumes

docker compose -f spikes\op001\compose.superset.yml --profile target-reports up -d
python spikes\op001\superset_probe.py
docker compose -f spikes\op001\compose.superset.yml --profile target-reports down --volumes
```

凭据全部是本机 spike 专用固定值，不能复制到正式 Compose。`target-reports` 只有一个 beat 和一个并发为 1 的 worker；未加入浏览器和 SMTP。

## 前端基线

`vendor/agent-chat-ui-official` 固定在 commit `325517352ca3672c8bc0745c4143b2301dd74997`，只用于审计，不提交：

```powershell
pnpm install --frozen-lockfile --store-dir D:\Agent\OpsPilot\spikes\op001\runtime\pnpm-store
pnpm format:check
pnpm lint
pnpm build
```

生产构建通过；上游 warnings 记录在 `handoffs/OP-001.md`，不在本 spike 修改第三方源码。
