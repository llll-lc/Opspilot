# OpsPilot

OpsPilot 是一个面向企业内部 IT / 数据平台支持团队的“智能故障诊断与工单闭环 Agent”。它根据用户故障描述主动补问，查询系统状态、权限、任务和日志，结合运维知识形成可引用的根因判断；低风险动作可受控执行，高风险动作进入人工审批，最后验证恢复并更新工单。

当前仓库处于“OP-002 脚手架完成、尚未开始正式业务编码”阶段。现有界面和 API 只验证应用边界，绝不伪造诊断、工单或目标系统结果。

## 本地开发（OP-002）

后端使用 Python 3.12、uv 与项目内缓存；当前 Windows Python Launcher 未注册 3.12 时，uv 会复用 OP-001 已验证的隔离解释器。首次同步后可以启动仅含进程健康检查的 API：

```powershell
uv --cache-dir .cache/uv sync --group dev
uv --cache-dir .cache/uv run uvicorn opspilot.main:app --reload
```

访问 `http://localhost:8000/api/v1/healthz` 只会返回 OpsPilot 进程名称和版本，不会连接数据库、模型或 Superset。

前端是独立的 OpsPilot 边界；它没有复制上游 LangGraph passthrough、浏览器 API key 或认证模型：

```powershell
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend dev
```

可在 `http://localhost:3000` 查看中文工作台壳。`frontend/.env.example` 仅允许配置公开的 OpsPilot API 根地址，目标系统凭据和认证秘密不得进入浏览器。

### 质量门禁

```powershell
uv --cache-dir .cache/uv lock --check
uv --cache-dir .cache/uv run ruff check .
uv --cache-dir .cache/uv run ruff format --check .
uv --cache-dir .cache/uv run mypy src
uv --cache-dir .cache/uv run pytest
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend format:check
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend build
```

GitHub Actions 在每个 push 和 pull request 执行同一组后端、前端检查。

### 仓库边界

```text
src/opspilot/api/              自有 FastAPI HTTP 边界（当前只有 process health）
src/opspilot/config/           Pydantic 配置与默认关闭的增强开关
src/opspilot/agent/            OP-007 前仅 Incident Commander Protocol
src/opspilot/providers/mcp/    OP-003/006 前仅 MCP Provider Protocol
src/opspilot/skills/           OP-005 前仅 Skill Registry Protocol
src/opspilot/specialists/      OP-009 前仅 Specialist Protocol
frontend/                      Next.js 工作台与 MIT 保留的 UI 基线
```

这些目录不是已实现功能。MCP 连接、Skill 加载、Tool Gateway、LangGraph 节点、委派、RAG、工单和认证分别由后续任务负责。

## 项目要解决的问题

企业软件支持并不只是回答文档。真实处理过程通常需要在知识库、用户权限、资源状态、后台任务、服务健康和工单系统之间切换，容易出现信息遗漏、排查路径不一致、重复建单、未经授权操作和故障解决后没有验证等问题。

OpsPilot 展示的核心能力是：让领域内通用主智能体在权限边界内完成一条可暂停、可恢复、可审计、可评测的诊断链路，并在必要时调用受控专业子智能体；它不是通用 FAQ 聊天机器人或任意主机操作 Agent。

## 核心业务链路

```text
用户报告故障
→ 识别用户、目标系统和受影响资源
→ 补问缺失信息并建立支持工单
→ 选择版本化排障 Skill，检索官方文档/内部 Runbook
→ 调用 OpsPilot 稳定工具，由 Tool Gateway 映射或降级到 MCP、REST、只读 Probe
→ Specialist 已启用且确有上下文隔离价值时才委派，否则由主 Agent 继续诊断
→ 生成并验证候选根因
→ 给出带证据的诊断和修复计划
→ 风险策略判断是否需要人工审批
→ 受控执行或转人工
→ 验证恢复、更新工单并形成审计轨迹
```

## 最终求职版五类故障

1. 数据库连接或认证失败。
2. 用户、角色、数据集或仪表盘权限不足。
3. 定时报表/告警任务未执行。
4. Excel/PDF 导出或后台任务失败。
5. Worker、Redis 或相关服务状态异常。

## Apache Superset 的角色

Apache Superset 是首个真实目标系统和可复现故障实验环境。它提供企业软件常见的数据库连接、权限、报表调度、导出任务、API 和后台服务场景。项目会透明标注所使用的官方文档、官方仓库和公开 issue；不会在名称中把 OpsPilot 限定为 Superset 专属产品，也不会隐瞒资料来源或声称与 Apache Superset 官方存在合作。

后续若增加第二个目标系统，只应新增小型适配器；首版不建设通用插件市场。

## 受控 Agent 架构

1. 确定性底座：认证、工单、权限、Tool Gateway、RAG、审计和幂等。
2. `Incident Commander`：可独立完成诊断闭环的领域主 Agent。
3. 标准化增强：正式版本化 Skills；可降级的 Superset MCP Provider。
4. Specialist 增强：最后实现、可关闭的两个只读专业子智能体，默认开关由独立消融决定。

Agent 只看到 OpsPilot 稳定工具名，由 Tool Gateway 映射到 MCP 或 REST/只读 Probe。MCP `health_check` 只表示连接器可用，不代表 Superset Web/API、Worker、Redis 或业务任务整体健康。所有增强关闭时，主 Agent 仍能完成闭环或安全升级。详细决定见 [`ADR-003`](decisions/ADR-003_CONTROLLED_AGENT_MCP_SKILLS_ARCHITECTURE.md)。

## 技术方向（候选组件需实测）

- 前端：Next.js / React / TypeScript，复用经兼容性审计的 Agent Chat UI 能力并增加诊断与工单工作台。
- Agent：先实现可独立闭环的 LangGraph 主图；两个条件式有界 Specialist 最后实现且可关闭。
- MCP：OpsPilot 通过 Tool Gateway 接入 Superset 6.1.0 原生 MCP；它是可降级 Provider，兼容性、安全、健康语义和资源仍需 OP-003 实测。
- Skill：正式核心能力；代码仓库内版本化 `SKILL.md`，渐进加载排障步骤和证据门槛，不支持运行时动态安装。
- 服务：FastAPI + 开源 LangGraph PostgreSQL persistence；生产 Agent Server 路径已由 ADR-002 排除。
- 数据：PostgreSQL + pgvector 为核心；首版不设 Agent Redis/MinIO，Target Redis 只属于 Superset reports profile。
- LLM：DeepSeek 官方 OpenAI-compatible API，具体模型名由环境任务核验并配置化。
- 检索：元数据过滤 + 精确匹配 + BGE-M3 Dense/Sparse + RRF + 按需 BGE-Reranker-Large；结构感知父子切块，Dense-only 消融基线，小规模精确检索。
- 目标系统：Apache Superset 的最小 Docker 实验环境；定时报表场景按需启用其 Celery Worker/Beat 等依赖。
- 开发环境：Windows、Docker Desktop、PyCharm；最终构建一个 OpsPilot 应用镜像，并由 Compose 编排独立数据库和目标系统容器。

## 项目边界

OpsPilot 是求职作品级 POC，不是 ServiceNow/Jira Service Management 的替代品，也不是承诺可直接接入生产的自动运维平台。首版不做通用 AIOps、基础设施全自动修复、远程 Shell、生产凭据变更、完整 ITSM、多 Agent 自由协作/循环委派、动态 Skill 安装或大型多租户 SaaS。

## 规格入口

- 长期项目上下文：[`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md)
- 当前状态：[`CURRENT_STATE.md`](CURRENT_STATE.md)
- 任务总表：[`TASKS.md`](TASKS.md)
- 业务与范围：[`docs/01_BUSINESS_AND_SCOPE.md`](docs/01_BUSINESS_AND_SCOPE.md)
- 架构与技术栈：[`docs/02_ARCHITECTURE_AND_TECH_STACK.md`](docs/02_ARCHITECTURE_AND_TECH_STACK.md)
- Agent 工作流：[`docs/04_AGENT_WORKFLOW.md`](docs/04_AGENT_WORKFLOW.md)
- 数据与故障真值：[`docs/05_KNOWLEDGE_FAULTS_AND_GROUND_TRUTH.md`](docs/05_KNOWLEDGE_FAULTS_AND_GROUND_TRUTH.md)
- 开发协作：[`docs/07_DEVELOPMENT_WORKFLOW.md`](docs/07_DEVELOPMENT_WORKFLOW.md)
- 受控 Agent/MCP/Skills 决定：[`decisions/ADR-003_CONTROLLED_AGENT_MCP_SKILLS_ARCHITECTURE.md`](decisions/ADR-003_CONTROLLED_AGENT_MCP_SKILLS_ARCHITECTURE.md)
- 项目所有者学习地图：[`docs/11_OWNER_LEARNING_MAP.md`](docs/11_OWNER_LEARNING_MAP.md)

## 诚实的项目表述

本项目将使用公开官方资料、受控 Superset 实验环境和明确标注的合成工单/日志数据。可以证明“在已定义测试场景下能够诊断、审批、执行和验证”；除非未来确实发生，不得声称已在真实企业部署或产生真实业务收益。
