# CURRENT_STATE

更新时间：2026-09-05

## 当前阶段

`OP-003 风险闸门与 Gate A 故障真值完成；准备进入 OP-004 领域模型`

仓库已有可运行但不含业务能力的 FastAPI/Next.js 基线、锁文件、质量门禁和前端工作台壳；尚未开发正式工单、知识、Agent 图、工具网关、故障场景或业务 UI。

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

## 尚未完成

- 尚未实现 PostgreSQL 领域模型/迁移、认证/RBAC、工单、RAG、稳定工具网关、MCP/REST/Probe Provider、Agent 图、Skill、Specialist/委派、审批或最终评测。
- 已完成三类五个 Superset 故障真值与原生 MCP 风险闸门。当前 API 证据中，Gamma Reader 对临时命名数据源 `OP003 Restricted` 的 get 为 `404` 且 list 结果过滤该资源，连续三轮后资源已删除；这仅是 Superset 目标侧实测，不是 OpsPilot RBAC 实现。
- 固定 6.1.0 原生 CLI 的 JWT、审计和连接器语义可用，但默认目录暴露 10 个危险工具，原生只读闸门为 `FAIL`。受控超限测试将隔离 profile 与 MCP 容器环境的上限均确认为 1 token，读取 `get_instance_info` 仍返回 416 B 成功结果而未拒绝，故原生大小限制执行明确为 `FAIL`；验证器在强制拒绝断言下会先写报告、再以退出码 1 安全失败。仅极短客户端超时探针为 `PASS`；OP-006 必须走稳定工具允许列表与 REST/只读 Probe 回退，不能将原生 MCP 直接接入。
- 尚未构建最终 OpsPilot 应用镜像；该实现属于 OP-011，不得提前。

## 下一任务

`OP-004：基础设施与核心领域模型`

执行前完整阅读 `tasks/OP-004.md`（若不存在，按模板与规格创建）、`handoffs/OP-003.md`、ADR-003 和当前领域规格。OP-004 仅实现 PostgreSQL/pgvector 领域模型、迁移、父子块/检索版本与 Provider 审计模型；不得导入 OP-003 实验控制脚本，也不得提前实现 Tool Gateway 或 Agent 业务。

## 当前阻塞与外部事项

- OP-001 本身无阻塞。
- Superset 6.1.0 原生 MCP 的本机启动、认证、目录、审计、资源和降级已验证；本机结论是只读目录与响应大小闸门均未通过，风险已移交 OP-006 的稳定工具/REST/Probe 回退实现。
- 本地 `.env` 已存在并被 Git 忽略；后续不得输出、提交或复制其中的 DeepSeek Key。
- Docker 当前分配约 6.70 GiB，项目所有者表示后续可增加；即使增加，profiles 与按需模型策略仍保留。
- Windows Python Launcher 当前未注册 Python 3.12；仓库仍可用 `D:\Agent\OpsPilot\.op001-venv\Scripts\python.exe`（3.12.4）由 uv 建立 `.venv`。不修改全局 Python；本地命令使用 `uv --cache-dir .cache/uv ...` 避开受限的全局 uv 缓存。

## 新会话启动语句

```text
继续开发 D:\Agent\OpsPilot。先完整读取 AGENTS.md、PROJECT_CONTEXT.md、CURRENT_STATE.md、TASKS.md、decisions/ADR-003_CONTROLLED_AGENT_MCP_SKILLS_ARCHITECTURE.md、docs/11_OWNER_LEARNING_MAP.md、tasks/OP-004.md 和 handoffs/OP-003.md，检查 Git、锁文件和实际环境。按 ADR-003 四层架构工作；本会话只执行 OP-004，建立 PostgreSQL/pgvector 领域模型与迁移，不实现 Tool Gateway、Provider 运行时或 Agent 业务。
```
