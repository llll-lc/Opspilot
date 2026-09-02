# 08 环境、模型与版本策略

## 1. OP-001 实测本机环境

| 项 | 已知情况 |
|---|---|
| 操作系统 | Windows 11 Home，10.0.26200，x64 |
| IDE | PyCharm 2023.2.5（PY-232.10227.11）；项目解释器尚未绑定 |
| CPU/GPU | AMD Ryzen 7 5800H，8 核/16 线程；CPU-only |
| 内存 | 系统可见 13.87 GiB；初始可用 4.29 GiB，用户释放后台软件后组合模型前约 8.46 GiB |
| 开发盘 | D 盘约 157.83 GB 剩余 |
| WSL | WSL 2.7.8，kernel 6.18.33.1；Ubuntu-24.04 停止，docker-desktop 运行 |
| 容器 | Docker Desktop 4.78.0；Engine/Client 29.5.3；Compose 5.1.4；Linux/amd64；cgroup v2；分配约 6.70 GiB、16 CPU |
| Git | 2.54.0.windows.1；OP-001 初始化本地 `main` 仓库；无 remote |
| Python | 统一 3.12.4（Anaconda）；`py` 默认 3.13 不用于项目；uv 0.12.1 |
| Node | Node 24.16.0、npm 11.13.0、pnpm 10.5.1、Corepack 0.35.0 |
| Embedding | `D:\Agent\models\bge-m3` |
| Reranker | `D:\Agent\models\bge-reranker-large` |
| Agent 教程 | `D:\Agent\learning_knowledge` |

OP-001 检查时 3000、5432、6379、8000、8088、9000、9001、2024、8123 均无监听冲突。用户原有 8 个 medical-rag 停止容器未修改。

## 2. 版本原则

- 规划阶段不猜测并锁死未验证版本。
- OP-001 选择互相兼容的版本、生成锁文件策略并记录上游 commit/tag。
- 优先选择仍受支持的稳定版本，不以“最新”作为唯一标准。
- 滚动更新的在线 API 文档不能代替目标版本实际 OpenAPI/配置。
- 升级目标系统、LLM、Embedding、工具 Schema 或关键框架必须重跑受影响评测。

## 3. OP-001 定版矩阵

| 组件 | 规划候选 | OP-001 要确认 |
|---|---|---|
| Python | 3.12 | 仓库虚拟环境/容器统一；不得跟随本机 `py` 3.13 |
| Node.js/包管理器 | Node 24.16.0、pnpm 10.5.1 | 官方前端 lockfile 实装通过；后续镜像固定 Node major/patch |
| LangGraph | 开源 LangGraph | PostgreSQL checkpoint/store；具体包版在 OP-002 锁定 |
| Agent 服务 | FastAPI + LangGraph | ADR-002；不用生产 Agent Server 许可/Redis 路径 |
| FastAPI/Pydantic | 与选定 Agent 栈兼容 | Schema 与流式接口 |
| PostgreSQL/pgvector | `pgvector/pgvector:0.8.6-pg17-bookworm` | PostgreSQL 17 + pgvector 0.8.6；`vector(1024)` 已验证 |
| Redis | Agent 侧删除 | 仅 `target-reports` 使用隔离的 `redis:7.4-alpine` |
| MinIO | 首版删除 | 项目数据目录 + PostgreSQL 元数据/哈希；多机需求再 ADR |
| Superset | `apache/superset:6.1.0-dev` | 实验固定 6.1.0；公开 API、健康、种子、reports 组合已验证 |
| 前端 | 官方 Agent Chat UI commit `3255173...` | MIT；Next 16.3.3、React 19.2.8、SDK 1.10.0；构建通过 |

Redis 和 MinIO 不是为了“技术栈齐全”而强制保留；OP-001 已从 Agent 首版删除两者。未来只有新职责和资源证据充分时才能通过 ADR 重新引入。

## 4. DeepSeek 配置

2026-09-02 官方 Base URL 为 `https://api.deepseek.com`，可用模型为 `deepseek-v4-flash` / `deepseek-v4-pro`；旧 `deepseek-chat` / `deepseek-reasoner` 已停用。默认使用可配置的 `deepseek-v4-flash`，不得把模型名写死在业务代码。

环境变量概念：

```text
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=
DEEPSEEK_MODEL=
LLM_TIMEOUT_SECONDS=
LLM_MAX_RETRIES=
```

无效 Key 的真实 401、真实客户端超时和官方错误码映射已通过。普通对话、JSON 与工具调用因本地未提供 Key 暂无成功证据，必须在进入 OP-007 前补跑；API Key 只能由用户写入未提交 `.env`。

## 5. 本地 BGE 配置

### BGE-M3

- 规划使用稠密向量能力，输出 1024 维。
- 不因为模型支持更长输入就默认使用超长分块。
- 稀疏和多向量能力只有评测证明收益后才增加。

### BGE-Reranker-Large

- 只对小候选集使用。
- 是否常驻、按需加载或最终不启用由 CPU 内存与检索收益共同决定。

OP-001 CPU 基准（4 线程、并发 1、短批次 4、7 次）：BGE-M3 输出 1024 维，组合测试中 P50/P95 为 424/607 ms；Reranker raw-logit P50/P95 为 835/920 ms；两模型组合加载 9.30 s + 12.29 s，进程 RSS 峰值约 4.84 GiB。结论是技术上可并存，但默认按需/串行，收益仍由 OP-005 评测决定。

Windows 兼容事实：`sentencepiece==0.2.2` 加载本地 XLM-R tokenizer 会产生 `0xC0000005`；两模型 SentencePiece 文件哈希一致，spike 使用 BGE-M3 自带 `tokenizer.json`。旧 reranker 检查点仅允许忽略非参数缓冲键 `roberta.embeddings.position_ids`。Linux 正式镜像需要重新验证标准加载路径。

```text
EMBEDDING_MODEL_PATH=D:\Agent\models\bge-m3
RERANKER_MODEL_PATH=D:\Agent\models\bge-reranker-large
MODEL_DEVICE=cpu
MODEL_INFERENCE_CONCURRENCY=1
```

Windows 路径映射到容器时必须转换为容器内挂载路径；不得在代码中假定宿主绝对路径在容器内存在。

## 6. Superset 环境事实与约束

- Superset 是开源 BI/数据探索 Web 应用，首个真实适配对象；代码采用 Apache License 2.0，使用代码/资产时保留许可证与 NOTICE，并说明无官方隶属关系。
- 官方提供 REST API/OpenAPI；项目优先调用公开 API，不依赖私有 ORM 或直接写元数据库。
- Alerts & Reports 场景通常涉及独立 Redis、Celery Worker、单一 Beat，并可能需要无头浏览器。
- 官方 Docker Compose 用于本地/开发体验，不是生产模板；Windows 不是其正式支持环境，完整开发构建在低内存环境可能很慢。
- 因此在 Docker Desktop 的 Linux 容器/WSL2 环境中先做 spike，按 `target-light` 与 `target-reports` 分开，不把成功写成预设事实。

官方入口（执行时再次核验）：

- [Apache Superset repository](https://github.com/apache/superset)
- [Superset REST API / OpenAPI](https://superset.apache.org/developer-docs/api/open-api/)
- [Security and roles](https://superset.apache.org/admin-docs/security/)
- [Alerts and Reports](https://superset.apache.org/admin-docs/configuration/alerts-reports/)
- [Docker Compose](https://superset.apache.org/admin-docs/installation/docker-compose/)

## 7. 启动 profile 与资源实测

定版：

- `core`：一个 OpsPilot 应用容器 + 独立 PostgreSQL/pgvector；应用镜像不内置本地模型文件。
- `target-light`：Superset Web/API 和最小元数据/示例资源。
- `target-reports`：按需增加 Target Redis、Worker、单一 Beat；浏览器类导出单独验证。
- `ingest-eval`：批量 Embedding/Reranker/评测，避免和完整报表栈同时高负载。
- `observability`：可选观测组件。

实测：pgvector 冷启动约 4.15 s、约 70.88 MiB；`target-light` 冷启动约 72.6 s、约 304.3 MiB；`target-reports` 冷启动约 62.77 s，稳定样本约 834.7 MiB（DB 51.21、Redis 8.80、Web 255.3、worker 290.8、beat 228.6 MiB）。首次 Superset DNS 配置和 beat 写目录失败均已复盘修复；修复后无异常重启。

硬要求：不默认同时运行两模型组合与完整 reports profile。日常使用 `core + target-light`；检索/评测切到 `ingest-eval`；reports 场景按需切换。Docker 配额可由项目所有者后续增加，但 profiles 仍保留，不能用更大配额掩盖服务职责。

## 8. 目标系统与 Agent 服务命名

配置、容器、网络和卷必须可区分，例如：

```text
opspilot-postgres
superset-app
superset-metadata-db
superset-redis
superset-worker
superset-beat
```

Agent 不连接 Docker Socket。故障注入控制面只在测试 profile/网络存在，不与普通 Agent API 共用凭据。

## 9. PyCharm 与宿主机开发

- 项目解释器固定为 Python 3.12 的仓库虚拟环境或容器解释器；OP-002 配置正式开发入口。
- 不提交 `.idea` 中的个人路径、密钥和窗口状态；只提交确有团队价值且不含机器信息的配置（若需要）。
- 提供可从 PyCharm Run/Debug 和命令行执行的等价入口，避免只能点 IDE 按钮运行。
- 本地 BGE 若运行在宿主机，Web 服务不得通过多 worker 复制加载。

## 10. 数据、磁盘与下载

- 模型保留在 `D:\Agent\models`，不复制进项目或镜像。
- Superset 源码/镜像版本和磁盘占用由 OP-001 记录，避免重复克隆和无界缓存。
- 数据库卷、对象卷、日志、缓存、截图、导出产物和大型评测结果不提交 Git。
- 清理脚本只操作已验证的项目专属路径/容器/卷；禁止对 `D:\Agent`、D 盘根或用户目录递归删除。
- 下载依赖、镜像和官方源代码需要用户批准时一次说明用途与体积预期。

## 11. 回退顺序

遇到资源或兼容问题按最小影响顺序处理：

1. 固定兼容版本、减少同时启动 profile。
2. Reranker 按需/串行加载或在无收益时关闭。
3. 模型放宿主机单进程，容器只调用受控本地服务。
4. Agent Server 回退 FastAPI + LangGraph 开源持久化。
5. Superset 重型场景使用明确标记的确定性 fixture，但至少保留真实 API/状态链路。
6. 更换模型或核心数据库必须有新 ADR 和评测，不直接决定。
