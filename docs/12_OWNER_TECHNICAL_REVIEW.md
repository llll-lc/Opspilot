# 12 项目所有者技术复盘

- 最近更新：2026-09-04
- 当前复盘基线：`f4e42ee`（OP-002）
- 当前覆盖范围：项目故障闭环、OP-002 工程骨架与前端基线

## 1. 用途、权威边界与使用方法

本文档用于项目所有者在阶段完成后复习核心技术、真实数据流和设计取舍，并为面试复述提供线索。它不是业务规格、架构决策、任务状态或验收证据的权威来源。

若本文档与其他内容冲突，按以下顺序核实：

1. 当前代码与测试；
2. 最新已接受 ADR；
3. [`TASKS.md`](../TASKS.md) 和对应的 `tasks/OP-xxx.md`；
4. 对应的 `handoffs/OP-xxx.md`；
5. 专题规格和 [`CURRENT_STATE.md`](../CURRENT_STATE.md)；
6. 本复盘文档。

维护规则：

- 只在一个开发阶段完成测试、交接和本地提交后总结，不把预期设计写成完成事实。
- 只记录核心概念、真实链路、关键取舍和个人易错点，不复制大量代码、命令或聊天内容。
- 规划中的内容必须标记为“尚未实现”；真实测试结果以任务交接和测试文件为准。
- 学习过程中若发现需要改变业务或技术边界，先交由主边界会话确认并更新 ADR/规格，再同步到本文档。
- 每次更新注明所依据的提交；新学习会话仍须按 [`AGENTS.md`](../AGENTS.md) 读取当时的任务和实际代码。

学习顺序见 [`docs/11_OWNER_LEARNING_MAP.md`](11_OWNER_LEARNING_MAP.md)。

## 2. 阶段索引

| 阶段 | 核心主题 | 复盘状态 |
|---|---|---|
| 项目总览 | 企业软件故障诊断与工单闭环 | 已复盘 |
| OP-002 | FastAPI/Next.js 骨架、配置、边界与质量门禁 | 已复盘 |
| OP-003 | Superset、MCP 风险闸门与故障真值 | 待任务完成后复盘 |
| OP-004 | PostgreSQL、pgvector、领域模型与迁移 | 待任务完成后复盘 |
| OP-005 | 父子切块、混合 RAG、Reranker 与 Skills | 待任务完成后复盘 |
| OP-006 | 工单、身份、Tool Gateway、Provider 与审计 | 待任务完成后复盘 |
| OP-007 | Incident Commander、LangGraph、HITL 与恢复 | 待任务完成后复盘 |
| OP-008 | 诊断与工单工作台 | 待任务完成后复盘 |
| OP-009～OP-012 | Specialist、综合评测、安全、部署与求职交付 | 待任务完成后复盘 |

---

## 3. 项目总览：一次故障怎样形成闭环

### 3.1 解决什么企业支持问题

OpsPilot 面向企业 BI/数据平台支持场景。第一目标系统是本地 Apache Superset，首批处理数据库连接、访问权限、定时报表、导出任务和 Worker/Redis 等运行时故障。

它不是只根据文档回答问题的聊天机器人。完整目标是：

```text
受理问题
→ 创建或关联 Case
→ 提出故障假设
→ 检索知识并检查现场状态
→ 形成有证据的诊断
→ 生成受控 ActionPlan
→ 必要时等待人工审批
→ 执行动作
→ 重新检查并验证恢复
→ 关闭工单或安全升级人工
```

### 3.2 用“定时报表未发送”理解整条链路

用户报告“每天 9 点的销售报表今天没有发送”时，这只是故障现象，不是根因。

主 Agent 可以先提出候选假设：

- 报表任务被禁用；
- Superset Beat 没有调度任务；
- Redis 没有正常传递任务；
- Worker 收到任务但执行失败；
- 报表生成成功但邮件发送失败；
- 浏览器渲染、凭据或数据库连接异常。

然后按照风险低、信息量高的顺序调用只读工具。假设现场证据显示：

```text
报表任务：已启用
Superset Web/API：正常
Redis：正常
Worker：正常
Beat：未运行
今天的调度记录：不存在
```

文档中“Redis 故障可能导致报表失败”只能帮助提出候选原因；它不能覆盖本次事故的现场证据。当前更合理的诊断是 Beat 未运行导致任务没有产生，并且需要用任务启用状态、Beat 状态和调度记录共同支撑，不能仅凭一个孤立信号下结论。

### 3.3 RAG、Skill、Tool 与 Agent 的区别

| 组件 | 回答的问题 | 不能替代什么 |
|---|---|---|
| RAG | 文档、配置和历史依据怎么说？ | 不能证明当前系统实际状态 |
| Skill | 这一类故障应按什么方法、顺序和停止条件排查？ | 不能充当现场证据或执行权限 |
| Tool | 当前目标系统实际返回了什么？ | 不能自行综合原因或承担业务决策 |
| 主 Agent | 下一步查什么，证据如何组合，最可能的根因是什么？ | 不能绕过服务端权限和审批直接执行危险操作 |

最短记忆方式：

```text
RAG 提供知识
Skill 提供方法
Tool 提供现场事实
Agent 负责综合判断
```

### 3.4 模型、确定性代码与人工的职责

模型适合负责：

- 理解用户的自然语言；
- 提出、更新和排除诊断假设；
- 选择下一项受控只读检查；
- 综合证据、解释根因并生成候选修复计划。

确定性代码必须负责：

- 身份、组织、资源范围与权限；
- Case 状态机、参数 Schema、工具允许列表和风险分级；
- 数据持久化、审计、幂等和恢复；
- 真正的工具调用与受控动作执行；
- 判断审批是否存在且有效。

人工负责：

- 补充系统无法获得的业务信息；
- 确认影响范围；
- 批准或拒绝有影响的动作；
- 接管证据不足、越界或无法安全自动处理的情况。

核心原则：

> 模型提出判断，代码约束并执行，人工授权并承担最终责任。

### 3.5 为什么执行成功不等于故障恢复

“重启 Beat”命令返回成功，只能证明执行请求完成，不能证明定时报表已经恢复。系统还需要重新读取：

- Beat 是否持续运行；
- 是否出现新的调度记录；
- Worker 是否收到并完成任务；
- 报表是否成功生成或发送；
- 必要时用户是否确认业务结果恢复。

只有验证通过才能关闭 Case；否则继续诊断或升级人工。

### 3.6 当前四层架构中的位置

根据 [`ADR-003`](../decisions/ADR-003_CONTROLLED_AGENT_MCP_SKILLS_ARCHITECTURE.md)：

| 层级 | 内容 | 关键要求 |
|---|---|---|
| L0 确定性底座 | FastAPI、RBAC、工单、PostgreSQL、RAG 服务、Tool Gateway、审计与幂等 | 不把权限和数据一致性交给模型 |
| L1 主 Agent | `Incident Commander` LangGraph 主图 | 所有增强关闭时仍能闭环或安全升级 |
| L2 标准化增强 | 版本化 Skills、可降级 Superset MCP Provider | Skill 是方法增强；MCP 不是唯一 Provider |
| L3 Specialist | 两个最后实现、可关闭的只读专家 | 不面对用户、不写工单、不审批或执行修复 |

依赖方向是高层使用低层。L2/L3 关闭或失败，不能破坏 L0/L1 的基础闭环。

### 3.7 面试复述

可以用下面这段话作为复述骨架，但需要结合后续真实实现和测试自行表达：

> OpsPilot 不是让模型直接操作系统，而是由主 Agent 根据 RAG 知识、版本化排障 Skill 和现场只读证据动态更新假设。身份、权限、状态机、工具允许列表、审计和幂等由确定性服务端控制。模型只生成诊断和动作计划，有影响的操作经过人工审批，执行后必须重新读取系统状态验证恢复，最终关闭工单或安全升级人工。

---

## 4. OP-002：工程骨架与前端基线

### 4.1 本阶段解决什么问题

OP-002 没有实现诊断业务，而是建立后续模块共同使用的、可重复运行和验证的工程地基：

- Python 3.12 FastAPI 后端包；
- Next.js/React/TypeScript 前端工作台壳；
- 类型化配置和安全默认值；
- Agent、MCP Provider、Skill、Specialist 的包边界；
- Python/前端依赖锁和质量门禁；
- 官方 Agent Chat UI 视觉原语的固定来源和许可证归属。

实际完成证据见 [`tasks/OP-002.md`](../tasks/OP-002.md)、[`handoffs/OP-002.md`](../handoffs/OP-002.md) 和提交 `f4e42ee`。

### 4.2 当前真实运行链路

当前后端只交付一个进程级健康接口，没有 Case、RAG、Agent、工具或数据库调用。

```text
客户端或测试程序
→ Uvicorn 监听端口并接收 HTTP 请求
→ FastAPI 应用匹配请求
→ /api/v1 前缀下的 Router 找到 /healthz
→ read_process_health() 创建 ProcessHealth
→ Pydantic 校验响应结构
→ FastAPI 返回 HTTP 200 和 JSON
```

对应代码：

- [`src/opspilot/main.py`](../src/opspilot/main.py)：应用组合根，创建 FastAPI 并安装总 Router；
- [`src/opspilot/api/router.py`](../src/opspilot/api/router.py)：汇总当前 API 路由；
- [`src/opspilot/api/routes/health.py`](../src/opspilot/api/routes/health.py)：定义进程健康响应和 `/healthz`；
- [`src/opspilot/config/settings.py`](../src/opspilot/config/settings.py)：读取、校验并缓存运行配置。

路径由两部分组成：

```text
应用前缀 /api/v1 + 接口路径 /healthz
= /api/v1/healthz
```

### 4.3 Uvicorn、FastAPI、Router 和 Pydantic 分别做什么

| 组件 | 当前职责 |
|---|---|
| Uvicorn | 监听网络端口，把 HTTP 请求交给 Python Web 应用 |
| FastAPI | 创建应用、匹配请求、调用接口并生成 HTTP 响应 |
| Router | 按路径组织和登记接口，避免所有接口堆在入口文件 |
| Pydantic | 校验配置和输入/输出对象的类型与约束 |

`main.py` 是“组合根”，负责把应用需要的模块装配起来，不承载具体诊断逻辑。

### 4.4 `/healthz` 的准确含义

接口返回：

```json
{
  "status": "ok",
  "application": "OpsPilot API",
  "version": "0.1.0"
}
```

它能够说明：

- 当前访问到的 OpsPilot Uvicorn/FastAPI 进程可以响应；
- FastAPI 应用已加载；
- `/api/v1/healthz` 路由和响应序列化可以执行。

它不能说明：

- 其他业务 API 一定正常；
- PostgreSQL、DeepSeek、BGE 模型或 RAG 正常；
- Superset Web/API 正常；
- Redis、Worker、Beat 或业务任务正常；
- Agent 已经能够完成诊断。

因此，即使未来所有功能已经开发，下面的情况仍然可能合理存在：

```text
GET  /api/v1/healthz → 200 OK
POST /api/v1/cases   → 500 Internal Server Error
```

准确表述是：

> `/healthz` 返回 `ok` 可以排除当前 OpsPilot API 进程完全没有启动或完全不可达，但不能排除该进程内的业务功能和外部依赖故障。

以后还会分别检查 MCP 连接、Superset Web/API 和异步运行时，不能用一个健康信号推断整个系统。

### 4.5 API、Service 与 Repository 的未来分工

OP-002 还没有业务 Service 和 Repository；下面是后续 Case 功能应遵循的概念边界，不代表已经实现：

```text
浏览器
→ API：接收 HTTP、校验格式、取得认证上下文、返回状态码
→ Service：执行创建/合并 Case、状态流转、权限和审计等业务规则
→ Repository：按照 Service 的要求读写 PostgreSQL
```

例子：

| 动作 | 所属层 |
|---|---|
| 校验请求中的 `title` 是否为空 | API/请求 Schema |
| 判断相同故障是否应该合并 | Service |
| 把 Case 插入 PostgreSQL | Repository |

不是每个接口都必须机械地经过三层。`/healthz` 没有业务规则和数据库访问，所以当前直接在 API 层返回结果，避免为分层而分层。

### 4.6 类型化配置和安全默认值

[`Settings`](../src/opspilot/config/settings.py) 集中管理应用版本、环境、API 前缀、DeepSeek、本地模型、数据库、Superset 和增强开关等配置。

关键设计：

- 密钥保留在被 Git 忽略的 `.env`，示例文件不包含真实值；
- `SecretStr` 降低密钥被普通打印直接暴露的风险；
- 配置对象被冻结，避免运行时被业务代码随意修改；
- `get_settings()` 缓存每个进程的配置快照；
- CPU 模型推理并发固定为 1；
- `SKILLS_ENABLED`、`SUPERSET_MCP_ENABLED`、`SPECIALISTS_ENABLED` 默认均为 `false`。

开关存在不代表能力已经实现。默认关闭证明后续增强不能成为基础主流程的隐式依赖。

### 4.7 为什么只创建空的 Protocol 边界

OP-002 创建了以下命名边界：

- [`IncidentCommander`](../src/opspilot/agent/contracts.py)；
- [`McpProvider`](../src/opspilot/providers/mcp/contracts.py)；
- [`SkillRegistry`](../src/opspilot/skills/contracts.py)；
- [`Specialist`](../src/opspilot/specialists/contracts.py)。

它们当前没有方法和运行逻辑。这样既固定了未来代码所属位置，又避免在缺少 OP-003～OP-006 实测结论时，提前猜测错误的工具、Skill 或 Agent 接口。

“只有空边界”不是漏做，而是任务范围的一部分。Agent 图属于 OP-007，Specialist 属于 OP-009。

### 4.8 前端边界为什么这样设计

当前 [`frontend/src/app/page.tsx`](../frontend/src/app/page.tsx) 只是明确标注“未连接”的中文工作台壳，展示未来工单摘要、诊断证据、工具/审批时间线和恢复验证的位置。

[`frontend/src/lib/opspilot-api.ts`](../frontend/src/lib/opspilot-api.ts) 当前只返回 OpsPilot API 根地址，尚未真正发起健康或业务请求。

项目只复用官方 Agent Chat UI 固定 commit 的 MIT 视觉组件和基础样式，没有复制它的 LangGraph API passthrough、认证、API Key 或 Thread runtime。这样可以保证未来浏览器先进入 OpsPilot 自己的认证和业务 API，而不是绕过服务端边界直接连接 LangGraph 或目标 Superset。

第三方来源和许可证见：

- [`frontend/THIRD_PARTY_NOTICES.md`](../frontend/THIRD_PARTY_NOTICES.md)；
- [`frontend/LICENSE.agent-chat-ui`](../frontend/LICENSE.agent-chat-ui)。

### 4.9 测试和质量门禁在保护什么

[`tests/test_health.py`](../tests/test_health.py) 不只检查 `/healthz` 返回 200，还验证：

- 响应只包含进程名称、版本和状态；
- 未实现的 `/api/v1/incidents` 必须返回 404，防止脚手架伪造业务能力。

[`tests/test_settings.py`](../tests/test_settings.py) 验证：

- Skill、MCP、Specialist 默认关闭；
- 进程启动不强制依赖真实 API Key 或数据库；
- 本地模型推理并发保持为 1。

[`tests/test_boundaries.py`](../tests/test_boundaries.py) 验证预留包只有命名契约，没有偷偷加入 LangGraph、MCP 连接或运行函数。

`pyproject.toml`、`uv.lock`、`frontend/pnpm-lock.yaml` 和 CI 共同固定依赖，并执行格式、lint、类型检查、测试和生产构建。根据 OP-002 交接，Python 测试为 6 passed、coverage 100%，前后端质量门禁均通过；这些结果以交接和提交时的实际输出为准。

### 4.10 为什么选择当前最简单实现

- 只用一个 FastAPI 进程入口验证自有后端边界，不伪造 Case、Agent 或工具返回；
- 采用模块化单体，避免个人作品过早拆成微服务；
- 先锁依赖和质量门禁，再让后续任务在可重复基线上开发；
- 只复用官方 UI 视觉原语，保留 OpsPilot 自己的认证、授权和审计入口；
- 只创建空契约，不让脚手架抢占后续责任任务的设计权。

### 4.11 如何验证和运行

以仓库 [`README.md`](../README.md) 和 [`tasks/OP-002.md`](../tasks/OP-002.md) 的最新命令为准。核心验证包括：

```powershell
uv --cache-dir .cache/uv run ruff check .
uv --cache-dir .cache/uv run mypy src
uv --cache-dir .cache/uv run pytest
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend build
```

运行后端并访问 `/api/v1/healthz`，应看到进程元数据；访问尚未实现的业务路径应看到 404。当前前端应显示未连接状态，而不是模拟诊断结果。

### 4.12 已知限制与不能夸大的结果

- 当前没有数据库迁移、Case、认证/RBAC、RAG、Agent、工具网关、MCP 连接、Skill 或 Specialist；
- 当前前端不是可操作的诊断工作台；
- `/healthz` 不能证明 Superset 或任何依赖健康；
- OP-002 证明的是工程基线可运行、可测试、边界清晰，不证明已经完成企业故障诊断。

### 4.13 面试可能追问

**为什么不用官方 Agent Chat UI 的 API passthrough？**

因为浏览器应先进入 OpsPilot 自己的认证、授权、审计和业务 API 边界。直接沿用上游 passthrough 可能绕过这些控制，并把客户端配置或凭据边界带进项目。

**为什么已经安装 LangGraph 依赖，却没有创建 Agent 图？**

OP-002 只负责锁定经过兼容验证的基础依赖和包边界。主图需要依赖后续稳定工具、数据模型、故障真值和 Skill 契约，应由 OP-007 根据实际结果实现，不能由脚手架预先猜测。

**为什么 `/healthz` 不检查数据库和 Superset？**

它的契约就是进程级健康。将所有依赖混入一个 `ok` 会模糊故障位置；后续会使用不同工具分别表示连接器、目标 Web/API 和 Worker/Beat/Redis 的健康。

**为什么测试还要检查不存在的接口返回 404？**

因为 OP-002 明确不交付业务能力。这个失败样本可以防止开发者用虚假占位接口让项目看起来“已经能创建工单”。

### 4.14 当前个人掌握情况

已经能够解释：

- 文档中的故障原因只是候选可能性，最终诊断必须由现场证据支撑；
- `/healthz` 的 `ok` 只表示当前 OpsPilot API 进程能够响应，不能代表其他业务和依赖健康；
- 健康检查需要明确检查对象和范围；
- OP-002 只搭建工程地基，没有实现后续 Agent/RAG 业务。

后续仍需结合 OP-004/OP-006 的真实实现继续掌握 API、Service、Repository、认证和状态机边界；当前不把概念说明当成已实现功能。

---

## 5. OP-003：Superset 故障实验室、MCP 风险闸门与故障真值

### 5.1 本阶段真正完成了什么

OP-003 没有实现 Agent、工单、Tool Gateway 或正式 MCP Provider。它先把 Superset 建成一个隔离、可重复弄坏和恢复的目标系统实验室，并记录未来诊断必须依赖的机器可读事实。

核心产物是三类五个场景的真值、三轮生命周期证据，以及对固定 Superset 6.1.0 原生 MCP 的安全结论。它们确保后续 Agent 不能只根据文档或聊天“猜根因”。

### 5.2 最重要的故障定位地图

不用优先背英文术语，先按四个问题判断故障位于哪里：

| 应问的问题 | 健康范围 | 它不能代表什么 |
|---|---|---|
| 能否连上 MCP 服务？ | `CONNECTOR` | Superset Web/API、Redis、Worker 或报表业务正常 |
| Superset 网页/API 能否响应？ | `APPLICATION` | 后台调度和报表已完成 |
| Redis、Beat、Worker 是否运行？ | `RUNTIME` | 用户已经收到报表 |
| 本次报表是否真正调度、消费并产生业务结果？ | `BUSINESS_JOB` | 单个容器或 HTTP 请求曾返回成功 |

记忆重点是“健康信号有范围”。例如 MCP `health_check` 返回 200，只说明连接器可通信；它不能证明 Redis、Beat、Worker 或定时报表健康。

### 5.3 用一条报表流水线理解 Redis 与 Celery

把定时报表想成一条流水线：

```text
Beat（按时创建任务）
→ Redis（传递/暂存任务）
→ Worker（取走并执行任务）
→ 用户可验证的报表结果
```

因此“报表没有发送”不是唯一根因。Beat 停止时没有任务产生；Redis 停止时任务无法传递；Worker 停止时任务无人执行。OP-003 对这三种不同根因各连续验证三次，并在停止目标组件后确认 Superset Web/API 仍可健康响应。

### 5.4 五个故障真值怎样记

场景 ID 可查，不必死记；先记住三句话：

```text
连不上：F-DB-01，临时错误凭据导致连接测试失败。
看不到：F-AUTH-01，Gamma Reader 对命名数据源 OP003 Restricted 的 get 被拒绝、list 被过滤。
跑不起来：F-SCHED-01/02/03，分别是 Beat、Redis、Worker 故障。
```

“机器可读真值”就是先定义根因、必需观测、禁止操作、注入方式、恢复条件，再生成用户症状或日志。每次运行遵循：

```text
baseline → inject → assert active → recover → assert clean
```

如果注入后没有真的坏，或恢复后有残留，该样本是环境失败，不能拿去证明 Agent 准确。

### 5.5 MCP 的真实结论

原生 MCP 的 JWT 认证、审计和连接器调用均可运行；但实际目录有 24 个工具，其中 10 个包含 SQL、创建或更新能力。原生只读闸门因此是 `FAIL`，不是“连接成功所以可用”。受控实验把响应上限降到 1 token 后，只读 `get_instance_info` 仍返回 416 B 成功结果、没有被拒绝；验证器先保存报告，再以退出码 1 安全失败。说明原生响应大小限制也不能作为可信防线。

结论不是放弃 MCP 协议，而是：未来 Agent 绝不能直接看到原生目录。OP-006 必须让 Agent 只调用 OpsPilot 稳定工具名，以固定白名单、授权、参数限制、审计和 REST/只读 Probe 回退隔离原生 MCP。

### 5.6 现在必须掌握与暂时不必背诵的内容

当前必须能解释：健康范围为何不能混用；定时报表的 Beat → Redis → Worker 链路；“连不上、看不到、跑不起来”三类问题；以及 MCP 能通信不等于它可被安全交给 Agent。

暂时不必背：容器名、端口、JSON 每个字段、目录哈希、JWT 生成代码、全部 24 个工具名和 Docker 命令。这些应当能查到；面试或开发时更重要的是说明它们分别证明了什么。

### 5.7 对应代码、证据与不能夸大的结果

- 实验编排与验证脚本：[`labs/op003/`](../labs/op003/)；
- 当前权限/连接场景证据：[`OP-003_API_FIXTURE_LIFECYCLE_2026-09-05.json`](../evidence/OP-003_API_FIXTURE_LIFECYCLE_2026-09-05.json)；
- 当前 MCP 风险证据：[`OP-003_MCP_GATE_2026-09-05.json`](../evidence/OP-003_MCP_GATE_2026-09-05.json)；
- 实际任务交接：[`handoffs/OP-003.md`](../handoffs/OP-003.md)。

OP-003 证明的是受控目标系统、可重复场景和 MCP 风险结论；它不证明 OpsPilot 已经有前端报障、正式授权、Tool Gateway、Agent 推理、自动修复或端到端工单闭环。这些属于后续任务。

---

## 6. 后续阶段追加模板

每个阶段完成后，按实际需要精简使用以下结构：

```markdown
## OP-xxx：阶段名称

### 解决什么问题
### 在整体架构中的位置
### 核心技术与职责
### 一条真实数据/请求/证据流
### 模型、代码与人工的边界
### 当前方案及没有选择其他方案的原因
### 对应真实代码和测试
### 如何运行、注入失败和验证
### 常见误解、风险与降级
### 不能夸大的结果
### 面试复述与追问
### 当前个人掌握情况和待补问题
```
