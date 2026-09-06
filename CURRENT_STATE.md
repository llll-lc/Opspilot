# CURRENT_STATE

更新时间：2026-09-06

## 当前阶段

`OP-005 知识、混合 RAG、固定 Skills 与独立评测完成；准备进入 OP-006 工单、身份、稳定工具网关与 Provider`

仓库已有可运行但不含诊断业务的 FastAPI/Next.js 基线、锁文件、质量门禁和前端工作台壳，以及经实际 PostgreSQL 验证的 L0 数据契约；尚未开发正式工单、知识入库/检索、Agent 图、工具网关或业务 UI。

## 已完成

- 已完成规格—官方事实—本机现实冲突审计，并初始化本地 `main` Git 仓库；已配置 GitHub `origin`。
- 已实测 Windows/WSL2/Docker/Git/Python/Node/PyCharm、CPU/内存/磁盘、端口和用户现有 Docker 资源。
- 已固定 Python 3.12；本机 `py` 默认 3.13 不作为项目解释器。
- 已验证 BGE-M3 与 BGE-Reranker-Large 的文件、真实 CPU 推理、单独/组合加载、延迟和峰值内存；组合峰值约 4.84 GiB。
- 已定位 Windows SentencePiece 原生崩溃，并建立 fast tokenizer JSON + 非 mmap 的可复现 spike；正式 Linux 镜像仍需回归。
- 已验证 pgvector 0.8.6 的 `vector(1024)`。
- 已固定 Superset 6.1.0 spike；`target-light` 与 `target-reports` 的 Web/API、种子、OpenAPI、Redis、单 worker/beat、健康和资源均有证据。
- 已接受 ADR-002：FastAPI + 开源 LangGraph PostgreSQL persistence；删除 Agent Server 生产路径与 Agent Redis。
- 已删除首版 MinIO；Reranker 作为目标链路能力由 OP-005 实现并消融，首版按需/可关闭而非常驻；OpsPilot 与 Superset 使用独立数据库容器/卷边界。
- 已选择官方 Agent Chat UI 固定 commit 作为组件基线；格式、lint 和生产构建通过，已记录上游 warnings 与认证边界。
- 已接受 CR-002：最终一个 OpsPilot 应用镜像/容器，其他基础设施/目标服务由一个 Compose 入口分容器编排。
- 已用本地未提交 Key 验证 DeepSeek V4 普通对话、JSON、工具调用、401、超时和错误映射；Key 未进入日志/Git。
- OP-001 临时容器、网络和测试卷已清理；用户原有 medical-rag 停止容器未修改。
- 已接受 CR-003 / ADR-003：采用确定性底座、独立主 Agent、Skill/可降级 MCP、可关闭只读 Specialist 四层架构；RAG、Skill、MCP、Specialist 分轴评测。
- 已确认 Agent 只调用 OpsPilot 稳定工具名；Tool Gateway 映射 MCP/REST/Probe，且 MCP `health_check` 不代表完整目标系统健康。
- 已确认 RAG 目标链路和结构感知父子切块；ColBERT、HNSW 等延后项按风险文档中的重评条件处理。
- 已建立 Python 3.12 `uv` 后端包、FastAPI 进程级健康入口、pytest/ruff/mypy/coverage 门禁和 `uv.lock`；健康入口不探测数据库、模型或目标系统。
- 已建立 Next.js/React/TypeScript 工作台壳、`pnpm-lock.yaml`、Prettier/ESLint/typecheck/production build 门禁与 GitHub Actions 质量工作流。
- 已接入官方 `langchain-ai/agent-chat-ui` 固定 commit `325517352ca3672c8bc0745c4143b2301dd74997` 的 MIT 视觉原语；来源/许可证保留在 `frontend/THIRD_PARTY_NOTICES.md`，未复制其 API passthrough、认证、API key 或线程运行时。
- 已仅以空 `Protocol` 包边界和默认关闭的配置 Schema 预留 Agent、MCP Provider、Skill Registry 与 Specialist；未实现连接、加载、节点或委派。
- 已固定 `pgvector/pgvector:0.8.6-pg17-bookworm` 的 OpsPilot `core` 数据库基础设施；回环端口、健康检查和持久卷与 Superset 目标环境隔离。
- 已建立 SQLAlchemy 2.x 组合根和 Alembic `0001` 迁移：Organization/TargetSystem、版本化 KnowledgeDocument、RetrievalIndexVersion、父子 KnowledgeChunk、ToolDefinition/ProviderBinding/CatalogSnapshot、ToolExecution/AuditEvent 共 11 张表。
- 已实测 pgvector 0.8.6 的 `vector(1024)`；没有 HNSW/IVFFlat。父子块同范围、READY Dense/Sparse 完整性、表示版本、Sparse 数值权重及 Provider 执行快照由数据库约束/触发器保护。
- 已完成空库升级、降级、再次升级和 `alembic check`；实际数据库集成测试 2 项通过，完整后端 18 passed / 100% coverage，前端 frozen install、格式、lint、类型和 production build 通过。
- 已完成 OP-004 最终只读 review 修复：MCP/目录哈希 binding 的执行必须带匹配目录快照；DocumentVersion/CatalogSnapshot/ToolExecution/AuditEvent 为 append-only；检索版本和 Provider/工具契约只允许明确生命周期变更。CI mypy 已与本地统一为 `mypy src tests`，数据库 integration 测试仍为显式本地 PostgreSQL 验证。
- 已完成 OP-005 提交前 review 修复：冻结检索索引身份贯穿结果/Citation，Reranker off/on/load-or-score-failure 不伪造结果且可安全回退 Hybrid RRF，超长不可分结构单元有可定位的明确支持边界；实际 pgvector 回归还覆盖组织、目标、索引、可见性、来源类型和目标版本的逐项跨范围拒绝。2026-09-06 最终常规后端为 26 passed / 3 skipped、94% coverage；冻结消融未因本次测试/文档收尾重复运行。仍未提交，等待所有者 review。

## 尚未完成

- 已完成来源可追溯的最小知识语料、版本冻结的父子切块/入库、BGE-M3 Dense/Sparse、元数据过滤混合检索、可选 Reranker、冻结 RAG 消融和三个固定哈希校验的 Skill；尚未实现认证/RBAC、工单、稳定工具网关、MCP/REST/Probe Provider 运行时、Agent 图、Specialist/委派、审批或最终闭环评测。
- OP-005 的 Skill 只引用受限的稳定工具名称；没有向 `ToolDefinition` 写入种子、没有连接 Provider 或调用任何工具。OP-004 的工具/Provider 审计模型仍未注册具体工具、执行重试或降级；这些全部属于 OP-006。
- 已完成三类五个 Superset 故障真值与原生 MCP 风险闸门。当前 API 证据中，Gamma Reader 对临时命名数据源 `OP003 Restricted` 的 get 为 `404` 且 list 结果过滤该资源，连续三轮后资源已删除；这仅是 Superset 目标侧实测，不是 OpsPilot RBAC 实现。
- 固定 6.1.0 原生 CLI 的 JWT、审计和连接器语义可用，但默认目录暴露 10 个危险工具，原生只读闸门为 `FAIL`。受控超限测试将隔离 profile 与 MCP 容器环境的上限均确认为 1 token，读取 `get_instance_info` 仍返回 416 B 成功结果而未拒绝，故原生大小限制执行明确为 `FAIL`；验证器在强制拒绝断言下会先写报告、再以退出码 1 安全失败。仅极短客户端超时探针为 `PASS`；OP-006 必须走稳定工具允许列表与 REST/只读 Probe 回退，不能将原生 MCP 直接接入。
- 尚未构建最终 OpsPilot 应用镜像；该实现属于 OP-011，不得提前。

## 下一任务

`OP-006：工单、身份、稳定工具网关与 Provider`

执行前完整阅读并创建 `tasks/OP-006.md`、读取 `handoffs/OP-005.md`、ADR-003 和工具/Provider 规格。复用 OP-005 的 RAG 和固定 Skill，但不得改写其冻结索引、来源或评测真值；实现稳定 Tool Gateway、授权、工单及 REST/Probe/MCP 受控回退，不得提前实现 OP-007 Agent 图。

## 当前阻塞与外部事项

- OP-004 无阻塞；验证后的 `opspilot-op004` 容器、网络和专属卷已清理，用户原有 medical-rag 停止容器未修改。
- Superset 6.1.0 原生 MCP 的本机启动、认证、目录、审计、资源和降级已验证；本机结论是只读目录与响应大小闸门均未通过，风险已移交 OP-006 的稳定工具/REST/Probe 回退实现。
- 本地 `.env` 已存在并被 Git 忽略；后续不得输出、提交或复制其中的 DeepSeek Key。
- Docker 当前分配约 6.70 GiB，项目所有者表示后续可增加；即使增加，profiles 与按需模型策略仍保留。
- Windows Python Launcher 当前未注册 Python 3.12；仓库仍可用 `D:\Agent\OpsPilot\.op001-venv\Scripts\python.exe`（3.12.4）由 uv 建立 `.venv`。不修改全局 Python；本地命令使用 `uv --cache-dir .cache/uv ...` 避开受限的全局 uv 缓存。

## 新会话启动语句

```text
继续开发 D:\Agent\OpsPilot。先完整读取 AGENTS.md、PROJECT_CONTEXT.md、CURRENT_STATE.md、TASKS.md、decisions/ADR-003_CONTROLLED_AGENT_MCP_SKILLS_ARCHITECTURE.md、docs/11_OWNER_LEARNING_MAP.md、tasks/OP-005.md 和 handoffs/OP-004.md，检查 Git、锁文件和实际环境。按 ADR-003 四层架构工作；本会话只执行 OP-005，在 OP-004 数据契约上实现知识、混合 RAG、首批 Skills 与独立评测，不实现 Tool Gateway、工单、Agent 图或 Specialist。
```
