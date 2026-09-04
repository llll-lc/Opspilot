# ADR-003：受控主智能体、子智能体、MCP 与 Skills 架构

- 状态：Accepted
- 日期：2026-09-04
- 影响任务：OP-002～OP-012

## 背景

ADR-001 为了控制个人项目范围，选择一张主要 LangGraph 工作流，并在首版排除多 Agent、内部函数 MCP 化和强行覆盖教程技术。OP-001 已完成 DeepSeek、Superset 6.1.0、PostgreSQL/pgvector、本地 BGE、前端和资源基线验证；正式业务代码尚未开始。

项目所有者在完成 Agent 课程后进一步明确求职目标：项目不仅要形成可信的企业故障闭环，还要实际展示领域内通用主智能体、受控子智能体、真实 MCP 接入和可版本化 Skill。当前规格没有为这三项提供可验收实现，因此需要在不破坏企业可靠性和个人设备约束的前提下升级架构。

Superset 6.1.0 的版本化用户文档已经列出原生 MCP 能力；当前管理文档说明 MCP 以独立进程运行并提供认证、作用域和工具禁用能力。管理文档可能随 `Next` 版本更新，所以这些能力不能替代对固定 6.1.0 镜像的本地兼容性和安全验证。

## 决定

### 1. 采用四层、单向依赖的可降级架构

| 层级 | 内容 | 交付地位 | 运行时要求 |
|---|---|---|---|
| L0 确定性底座 | FastAPI、认证/RBAC、工单状态机、PostgreSQL、Tool Gateway、RAG 检索服务、审计、幂等、故障真值 | 必须 | 不依赖模型、MCP 或子智能体完成权限与数据一致性判断 |
| L1 独立主 Agent | `Incident Commander` LangGraph 主图 | 必须 | 在 Skill、MCP、Specialist 任一或全部关闭时仍能通过稳定工具完成诊断闭环或安全升级 |
| L2 标准化增强 | 版本化 Skills；可降级的 Superset MCP Provider | Skill 必须实现；MCP 必须接入并验证但不是单点依赖 | Skill 可为消融/故障回退关闭；MCP 失败自动切换 REST/只读 Probe，稳定工具语义不变 |
| L3 Specialist 增强 | 两个有界只读专业子智能体 | 最后实现、可配置关闭 | 默认是否启用由 OP-009 Specialist 消融决定，不得成为主闭环前置条件 |

依赖只能从高层指向低层，L0/L1 不得反向依赖 L2/L3。验收必须证明 `SKILLS_ENABLED=false`、`SUPERSET_MCP_ENABLED=false`、`SPECIALISTS_ENABLED=false` 时，主 Agent 仍可完成支持范围内的诊断、HITL、验证和工单闭环；证据不足时的安全升级也属于正确闭环。

Skill 是正式核心能力，求职版必须实现、展示和评测。上述关闭开关用于消融、故障演练和回退，不表示可以从交付范围删除 Skill。MCP 是外部协议接入，不得成为业务语义或可用性的唯一来源。Specialist 是最后一层性能/上下文增强，没有评测收益时允许默认关闭。

### 2. 保留可独立运行的领域内通用主智能体

主智能体命名为 `Incident Commander`，继续由自定义 LangGraph 主图承载。这里的“通用”指能够在企业 BI/数据平台支持领域内处理五类故障，而不是拥有任意文件、Shell、浏览器或主机权限的通用助手。

主智能体独占以下职责：

- 与用户交互、补问和最终答复。
- 创建/关联工单并维护唯一业务状态。
- 选择 Skill（启用时）、决定是否委派（启用时）、合并证据和作出最终诊断。
- 生成动作计划、触发 HITL、执行受控写操作、验证恢复和关单。
- 维护授权上下文、检查点、幂等和完整审计链。

主 Agent 只调用 OpsPilot 的稳定工具名，不知道也不选择 MCP、REST 或 Probe。Provider 选择、参数转换、认证、允许列表、重试和降级全部属于 L0 Tool Gateway。

### 3. Skills 是核心方法层，MCP 是可降级 Provider

首批三个 Skill：

- `database-connectivity-triage`
- `access-control-triage`
- `scheduled-report-triage`

核心闭环稳定后再增加 `export-job-triage` 和 `worker-service-health-triage`。每个 Skill 使用版本控制下的 `SKILL.md`，至少定义触发症状、适用版本、所需观测、稳定工具组与推荐顺序、证据门槛、停止/升级条件、禁止动作和结构化输出契约。Skill 可以引用知识来源/Runbook ID，但不复制大段知识正文。

边界定义：RAG 提供事实、配置和依据；Skill 提供排障方法；LangGraph 管理阶段和状态；Tool Gateway 提供稳定工具语义；MCP/REST/Probe 是 Tool Gateway 背后的不同 Provider；Specialist 隔离专业上下文。

首版不允许用户上传 Skill、运行时自动生成/安装 Skill、联网下载后立即生效，也不在 Skill 中提供任意 Shell/SQL 脚本。Skill 修改必须经过代码审查、版本更新和受影响评测。

OpsPilot 作为 MCP Client 接入 Superset 原生 MCP，但 Agent 不直接看到 `health_check`、`get_instance_info` 等上游名称。示例映射：

| OpsPilot 稳定工具名 | 候选 Provider | 明确语义 |
|---|---|---|
| `check_target_connector_health` | MCP `health_check` | 只证明 MCP Server/连接可用，不证明 Superset Web、Worker、Redis 或业务任务健康 |
| `get_target_instance_summary` | MCP `get_instance_info`，失败时 REST/Adapter | 目标实例的受限摘要 |
| `list_target_databases` / `get_target_database_info` | MCP list/get，失败时 REST/Adapter | 授权范围内数据库元数据 |
| `list_target_datasets` / `get_target_dataset_info` | MCP list/get，失败时 REST/Adapter | 授权范围内数据集元数据 |
| `list_target_dashboards` / `get_target_dashboard_info` | MCP list/get，失败时 REST/Adapter | 授权范围内仪表盘元数据 |
| `get_target_application_health` | Superset REST health/受控 Probe | Superset Web/API 应用健康，不代表异步运行时健康 |
| `get_target_runtime_health` | Worker/Beat/Redis 只读 Probe | 分组件返回异步运行时状态，不能由 MCP `health_check` 替代 |

Tool Gateway 对外只注册稳定名，并把 Provider、上游工具名和降级过程写入审计。MCP 允许的原始上游范围限于 `health_check`、`get_instance_info`、`get_schema` 和数据库/数据集/图表/仪表盘 list/get 元数据工具；SQL、保存、创建、生成、更新和未知工具必须拒绝。

Superset 原生 MCP 没有覆盖的权限校验、报表任务、Worker/Redis、日志和恢复验证继续使用窄接口 REST/只读 Probe。只有第二个消费者证明独立 MCP Server 有复用价值后，才考虑建立 OpsPilot 自有 MCP Server。

OP-003 必须先完成固定 Superset 6.1.0 的 MCP 风险闸门：启动方式、工具发现、认证/RBAC、工具禁用、审计、响应大小、超时、资源、`health_check` 语义和降级。验证通过前，文档只能称为“已选方案/待兼容验证”，不能称为“已实现”。

### 4. 子智能体最后实现且可关闭

只设置两个专业角色：

1. `Access & Connectivity Specialist`：负责数据库连接、认证、用户/角色/资源访问问题。
2. `Jobs & Runtime Specialist`：负责定时报表、导出任务、Worker、Redis 和相关服务状态问题。

子智能体必须满足：

- 在 L0～L2 与独立主 Agent 闭环通过后才实现；关闭时不改变主 Agent 的业务能力和工具集合。
- 仅在专业上下文或工具集合确实需要隔离时由主智能体条件式调用。
- 接收最小、脱敏、带组织和资源范围的上下文；不得读取完整会话或无关工单。
- 只使用 OpsPilot 稳定只读工具和已批准 Skill，设置最大步数、超时和调用次数。
- 不直接面对用户，不写工单、不审批、不执行修复、不改变图终态，也不能再委派其他智能体。
- 返回统一 `SpecialistFinding`：候选原因、支持证据 ID、反对证据 ID、缺失证据、结论等级和建议下一步。
- 首版串行；只有后续独立评测证明并行有收益且资源/状态互不影响时才考虑并发。

### 5. 固定 RAG 目标链路与结构感知切块

在强制组织/可见性/目标系统/版本/来源类型等元数据过滤后，召回链路固定为：

```text
元数据过滤
→ 精确匹配（错误码、配置键、任务名）
  + BGE-M3 Dense
  + BGE-M3 Sparse
→ RRF 融合与去重
→ BGE-Reranker-Large 对小候选集重排
→ 取回父块上下文并生成可定位引用
```

检索单元采用结构感知父子切块：较小子块参与精确/Dense/Sparse 召回和重排，命中后取回所属父块补充上下文；标题层级、代码块、配置段、表格和连续操作步骤不得从中间硬切。小规模语料先使用 pgvector 精确向量检索，不建 HNSW；Dense-only 保留为消融基线；首版不使用 BGE-M3 ColBERT/multi-vector。Sparse、RRF 和 Reranker 是否带来净收益分别评测，不以模型支持某能力作为保留理由。

### 6. 不为展示框架而替换主图

主工作流继续使用 FastAPI + 开源 LangGraph persistence。子智能体可以实现为受限的编译子图或 Agent，但不为了使用 `DeepAgents` 名称而重写主图。OP-002 只锁定基础依赖并预留包边界，不实现 Agent、MCP、Skill 或委派业务；具体 helper API 由后续责任任务依据最小实现和测试结果决定。

### 7. 分轴评测，禁止同时改变多个变量

所有消融使用冻结样本和相同安全过滤，不把 Skill 与 MCP 一次同时加入：

1. **RAG 消融**：Dense-only → 加精确匹配 → 加 BGE-M3 Sparse + RRF → 加 Reranker；分别报告 Recall@K、MRR/nDCG、引用有效率、延迟和内存。
2. **Skill 消融**：固定检索版本、稳定工具和 Provider，只切换 Skill off/on；报告必需观测覆盖、无效/重复工具、停止/升级和根因结果。
3. **MCP 兼容/安全/降级评测**：固定 Agent、Skill 和稳定工具契约，只切换 MCP Provider 与 REST/Probe Provider，并注入断连、认证失败、目录漂移和恶意返回；验证语义等价、允许列表、审计和回退，不把 MCP 当推理增益。
4. **Specialist 消融**：固定 RAG、Skill 和 Provider，比较 Specialists off/on；报告根因/轨迹变化、错误或不必要委派、上下文/Token、延迟和成本。

Specialist 的默认开关只由第 4 组结果决定。无收益时保持实现和演示入口，但默认关闭并如实报告；MCP 不兼容时保留 REST/Probe；任何增强失败都不得破坏独立主 Agent 闭环。

## 任务落点

- OP-002：只预留主 Agent、MCP Provider、Skill Registry 和委派的包边界/配置；不得实现任何相关业务。
- OP-003：在故障真值之外增加 Superset 6.1.0 原生 MCP 兼容性/安全/健康语义/降级风险闸门。
- OP-004：为父子块、Dense/Sparse 表示、检索版本和稳定工具/Provider 审计预留最小领域模型。
- OP-005：实现来源、结构感知父子切块、完整混合检索链、独立 RAG 消融和首批三个版本化 Skill。
- OP-006：实现独立可用的稳定 Tool Gateway、REST/Probe Provider、MCP Provider、授权、审计和降级；工单/HITL 保持内部服务。
- OP-007：先实现可独立闭环的 Incident Commander，并完成 Skill 消融；不在主闭环验收前实现子智能体。
- OP-009：扩展五类 Skill/场景，最后实现两个可关闭只读 Specialist，并分别完成 Specialist 消融和其他分轴评测。
- OP-010：覆盖 MCP 工具漂移/不可用、恶意返回、Skill 篡改、子智能体越权和降级。
- OP-012：在求职材料中解释每个组件的职责、收益证据和未采用方案。

## 代价与控制

- 新增约 3～5 个有效开发日的工作量，主要来自 MCP 风险闸门、Skill 契约、委派协议和消融评测；这是估算而非日历承诺。
- 多一次或两次模型调用会增加延迟和成本，因此子智能体必须条件触发、可关闭，不能把所有问题强制广播。
- 13.9 GiB 可见内存下不为子智能体加载额外本地大模型；它们共享配置化 DeepSeek Client，本地 BGE/Reranker 仍按需、并发 1。
- MCP Server/工具结果、Skill、知识和日志全部视为不可信输入；服务端 Tool Gateway 仍是最终权限边界和 Provider 降级入口。

## 被否决或暂缓

- 五个故障家族各建一个 Agent、多 Agent 自由讨论、循环委派：范围和评测成本过高。
- 把工单、RAG、审批、数据库函数全部 MCP 化：没有外部互操作收益。
- 通过 MCP 执行任意 SQL、写 Superset 资源或高风险修复：不满足最小权限。
- Tavily/泛化 Web、Excel、文件系统、Shell、Docker Socket MCP：与核心故障闭环无关或风险过高。
- 动态生成/安装 Skill：供应链、Prompt 注入和不可复现风险过高。
- 用 DeepAgents 替换主 LangGraph：不能证明对显式状态、HITL 和幂等有净收益。

## 依据

- [Superset 6.1.0：Using AI with Superset](https://superset.apache.org/user-docs/6.1.0/using-superset/using-ai-with-superset/)（访问：2026-09-04）
- [Superset：MCP Server Deployment & Authentication](https://superset.apache.org/admin-docs/configuration/mcp-server/)（访问：2026-09-04；当前页面为滚动版本，需对 6.1.0 实测）
- [Model Context Protocol：Architecture](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture)（访问：2026-09-04）
- [Agent Skills Specification](https://agentskills.io/specification)（访问：2026-09-04）
- [LangChain：Multi-agent](https://docs.langchain.com/oss/python/langchain/multi-agent/index)（访问：2026-09-04）

## 与既有决定的关系

本 ADR 不改变 ADR-001 的项目方向、五类故障、真实故障真值、安全边界和模块化单体，也不改变 ADR-002 的 FastAPI + 开源 LangGraph persistence 基线。它只替代 ADR-001 中“首版完全不使用多 Agent”的部分，并把“禁止内部函数 MCP 化”细化为“Agent 只看稳定工具，由 Tool Gateway 可降级接入外部 Superset 原生只读 MCP”。
