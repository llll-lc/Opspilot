# TASKS

状态枚举：`NOT_STARTED`、`IN_PROGRESS`、`BLOCKED`、`DONE`。

只有本文件记录正式任务状态。任务必须满足 `AGENTS.md` 的完成标准后才能标记 `DONE`。

| ID | 任务 | 状态 | 依赖 | 主要交付 |
|---|---|---|---|---|
| OP-000 | 项目规格与跨会话文档 | DONE | 无 | 规格、ADR、任务与交接体系 |
| OP-001 | 环境、资源与关键兼容性风险闸门 | DONE | OP-000 | 冲突审计、版本/资源基准、技术回退结论 |
| OP-002 | 仓库脚手架与前端基线 | DONE | OP-001 | 后端/前端结构、配置、质量门禁；只预留 Agent/MCP Provider/Skill/委派包边界 |
| OP-003 | Superset 最小目标系统、原生 MCP 风险闸门与故障真值 | NOT_STARTED | OP-001,OP-002 | 真实 API/MCP 兼容、安全、健康语义、降级证据；三类/五个场景 |
| OP-004 | 基础设施与核心领域模型 | NOT_STARTED | OP-002,OP-003 | PostgreSQL/pgvector、父子块/检索版本、稳定工具/Provider 审计、迁移 |
| OP-005 | 知识、混合 RAG、Skills 与独立评测 | NOT_STARTED | OP-003,OP-004 | 父子切块、精确+Dense+Sparse+RRF+Reranker、RAG 消融、首批 Skills |
| OP-006 | 工单、身份、稳定工具网关与 Provider | NOT_STARTED | OP-003,OP-004 | 工单状态机、稳定工具、REST/Probe/MCP 映射与降级、RBAC、审计、幂等 |
| OP-007 | 可独立闭环的 LangGraph 主 Agent | NOT_STARTED | OP-005,OP-006 | Incident Commander、动态诊断、Skill 消融、HITL、检查点、恢复；无 Specialist 依赖 |
| OP-008 | 诊断与工单工作台 | NOT_STARTED | OP-007 | 会话、工单、证据、工具轨迹、审批和验证 UI |
| OP-009 | 五类故障、只读 Specialist 与分轴评测 | NOT_STARTED | OP-003-OP-008 | 扩展故障/Skills、最后实现可关闭 Specialist、四类分轴评测与默认开关结论 |
| OP-010 | 安全、故障恢复与可观测性 | NOT_STARTED | OP-007,OP-009 | 注入防护、MCP/Skill/子智能体隔离与降级、Trace、安全回归 |
| OP-011 | Docker profiles 与端到端验收 | NOT_STARTED | OP-008-OP-010 | 单 OpsPilot 应用镜像、Compose 一键交付、健康检查、五类故障演示 |
| OP-012 | 求职材料、演示与代码复盘 | NOT_STARTED | OP-011 | README 完善、演示脚本、简历描述、面试复盘 |

## 执行规则

- 任务原则上按依赖执行；只有无共享写入且当前任务文件明确允许时才并行。
- 每个任务开始前创建或补全 `tasks/OP-xxx.md`，详细范围以该文件为准。
- OP-001 是风险闸门；它可以依据实测调整版本、部署形态和服务 profile，但不得未经确认改变业务方向或安全边界。
- OP-003 必须先建立少量真实可重复故障，不得先生成大量对话数据或 Agent Prompt。
- OP-003 还必须先验证固定 Superset 6.1.0 的 MCP 启动、工具发现、认证/RBAC、只读允许列表、审计、资源和降级；风险闸门未通过时保留原生适配器回退，不能伪报 MCP 已实现。
- OP-002 只能建立包目录、空接口/Protocol、配置 Schema 和质量门禁；不得实现 Tool Gateway 映射、MCP 连接、Skill 加载、Agent 节点、委派逻辑或占位业务返回。
- OP-007 必须先证明关闭 Skill/MCP/Specialist 时主 Agent 仍能通过稳定工具完成闭环；Specialist 只在 OP-009 最后实现。
- OP-009 必须分别执行 RAG、Skill、MCP、Specialist 四个评测轴，禁止用同时改变 Skill+MCP+Specialist 的 A/B/C 结果归因。
- OP-009 不是第一次考虑评测；故障真值 Schema 和基础断言在 OP-003 建立，OP-009 扩展到最终五类并完善轨迹报告。
- 若前置任务改变后续设计，只修改未开始任务，不改写已完成任务的历史证据。
