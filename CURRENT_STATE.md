# CURRENT_STATE

更新时间：2026-09-04

## 当前阶段

`OP-002 仓库脚手架与前端基线完成；准备进入 OP-003 风险闸门与故障真值`

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

- 尚未实现 PostgreSQL 领域模型/迁移、认证/RBAC、工单、RAG、稳定工具网关、MCP/REST/Probe Provider、Agent 图、Skill、Specialist/委派、审批、故障真值或评测。
- 尚未实现 Superset 故障场景/MCP 风险闸门、知识库/Skills、工单、工具网关、Agent 图/子智能体、审批或评测。
- 尚未构建最终 OpsPilot 应用镜像；该实现属于 OP-011，不得提前。

## 下一任务

`OP-003：Superset 最小目标系统、原生 MCP 风险闸门与故障真值`

执行前先创建/补全 `tasks/OP-003.md`，并读取 `handoffs/OP-002.md`、ADR-003、故障真值与安全规格。OP-003 必须先验证固定 Superset 6.1.0 的 MCP 启动、目录、认证/RBAC、工具禁用、审计、资源、健康语义与降级，再建立最少的真实可重复故障真值；不得实现 OP-004 领域模型或 OP-006 Tool Gateway。

## 当前阻塞与外部事项

- OP-001 本身无阻塞。
- Superset 6.1.0 原生 MCP 已有官方版本化用户文档依据，但本地镜像的启动、认证、工具禁用、审计、资源和降级尚未验证；该风险闸门属于 OP-003，不在 OP-002 提前实现。
- 本地 `.env` 已存在并被 Git 忽略；后续不得输出、提交或复制其中的 DeepSeek Key。
- Docker 当前分配约 6.70 GiB，项目所有者表示后续可增加；即使增加，profiles 与按需模型策略仍保留。
- Windows Python Launcher 当前未注册 Python 3.12；仓库仍可用 `D:\Agent\OpsPilot\.op001-venv\Scripts\python.exe`（3.12.4）由 uv 建立 `.venv`。不修改全局 Python；本地命令使用 `uv --cache-dir .cache/uv ...` 避开受限的全局 uv 缓存。

## 新会话启动语句

```text
继续开发 D:\Agent\OpsPilot。先完整读取 AGENTS.md、PROJECT_CONTEXT.md、CURRENT_STATE.md、TASKS.md、decisions/ADR-003_CONTROLLED_AGENT_MCP_SKILLS_ARCHITECTURE.md、docs/11_OWNER_LEARNING_MAP.md、tasks/OP-003.md 和 handoffs/OP-002.md，检查 Git、锁文件和实际环境。按 ADR-003 四层架构工作；本会话只执行 OP-003，先做 Superset MCP 风险闸门和最小故障真值，不实现后续领域模型、Tool Gateway 或 Agent 业务。
```
