# 02 系统架构与技术栈

## 1. 架构原则

- 模块化单体优先，不拆微服务。
- 四层单向依赖：确定性底座 → 可独立主 Agent → Skill/MCP 标准化增强 → 可关闭只读 Specialist 增强。
- 一张主要 LangGraph 图是唯一业务编排中心；关闭全部增强仍可诊断闭环或安全升级。
- Skill 是正式核心能力；MCP 只是可降级外部 Provider，不包装内部普通函数；Specialist 最后实现且默认开关由消融决定。
- 业务事实与向量统一进入 PostgreSQL，减少个人项目的服务数量。
- 模型负责语义推理，服务端负责认证、授权、状态机、幂等和动作策略。
- 目标系统与 Agent 自身基础设施明确隔离。
- Agent 服务、前端基线和 Docker profiles 已由 OP-001 实测定版；版本升级仍需重跑对应风险闸门。

## 2. 逻辑架构

```text
┌───────────────────────────────────────────────────────────┐
│ Next.js / React                                           │
│ Chat + 工单 + 诊断证据 + 工具轨迹 + 审批 + 恢复验证      │
└─────────────────────────┬─────────────────────────────────┘
                          │ SDK / HTTP / SSE
┌─────────────────────────▼─────────────────────────────────┐
│ L3 可关闭 Specialist：两个只读专家（最后实现）           │
├───────────────────────────────────────────────────────────┤
│ L2 正式 Skills + 可降级 Superset MCP Provider             │
├───────────────────────────────────────────────────────────┤
│ L1 Incident Commander：可独立受理→诊断→审批→验证→闭环   │
├───────────────────────────────────────────────────────────┤
│ L0 FastAPI / RBAC / 工单 / RAG / Tool Gateway / 审计幂等 │
└───────────────┬──────────────────────────┬────────────────┘
                │                          │ OpsPilot 稳定工具
       ┌────────▼─────────┐       ┌────────▼────────────────┐
       │ PostgreSQL       │       │ Tool Gateway            │
       │ 业务/向量/审计   │       │ Provider 映射/降级/审计 │
       └──────────────────┘       └──────┬──────────┬───────┘
                                        │ MCP      │ REST/Probe
                                  ┌─────▼──────────▼──────┐
                                  │ Superset Lab          │
                                  │ Web/API + Worker/Redis │
                                  └────────────────────────┘
```

## 3. 技术栈及职责

| 层 | 规划技术 | 职责 | 定版条件 |
|---|---|---|---|
| IDE | PyCharm | Python 后端开发、调试和测试 | OP-001 记录配置，不提交个人设置 |
| 前端 | 官方 Agent Chat UI 组件基线（commit `325517352ca3672c8bc0745c4143b2301dd74997`） | Next.js/React/TypeScript；对话、工单、证据、轨迹、审批和验证 | 不沿用上游 API passthrough 认证边界 |
| Agent | LangGraph | 可独立闭环的 Incident Commander 主图；显式状态、条件路由、interrupt、checkpoint | Specialist 关闭不影响主链路 |
| Agent 服务 | FastAPI + 开源 LangGraph persistence | 自有 Thread/Run/SSE、认证、持久化和业务 API | ADR-002 已定版 |
| MCP Provider | 与选定 LangChain/LangGraph 版本兼容的 MCP Client | Tool Gateway 背后的可降级外部协议 Provider | OP-003 风险闸门后由 OP-006 实现 |
| Agent Skills | 仓库内版本化 `SKILL.md` + 最小 Registry | 正式核心方法层；渐进加载排障 SOP、证据门槛和停止条件 | 首批三个；实现必须，运行可为消融/故障回退关闭 |
| Specialist | LangGraph 受限子图/Agent 候选 | 两个只读专家，隔离专业上下文 | OP-009 最后实现；默认开关由独立消融决定 |
| 业务 API | FastAPI | 工单、知识、审批、评测等确定性接口 | 不要求全部走模型工具 |
| 数据访问 | SQLAlchemy + Alembic 候选 | ORM、事务和迁移 | 与最终 Python 版本兼容 |
| 关系/向量 | PostgreSQL + pgvector | 工单、审计、检查点边界、1024 维向量 | 作品级规模优先准确过滤 |
| 临时状态 | 不设 Agent Redis | 首版无明确独立职责；状态与检查点进入 PostgreSQL | Target Redis 仅属于 Superset reports profile |
| 对象存储 | 项目数据目录 + PostgreSQL 元数据/哈希 | POC 知识原文、附件和评测产物 | 首版删除 MinIO；出现多机/对象语义需求再 ADR |
| LLM | DeepSeek OpenAI-compatible API | 语义分类、假设、计划、解释和结构化输出 | 模型名与接口 OP-001 实测 |
| Embedding | 本地 BGE-M3 | 1024 维 Dense + Sparse lexical weights | CPU 单实例；ColBERT 暂缓 |
| Reranker | 本地 BGE-Reranker-Large | 小候选集重排 | 实测有收益才保留常驻方案 |
| 目标系统 | Apache Superset | 首个真实企业软件实验对象 | 固定来源/许可证和测试版本 |
| 观测 | 结构化日志 + 可选 LangSmith/Langfuse | 节点、工具、延迟、模型和错误 | 至少一种本地可查看方式 |
| 部署 | Docker Compose profiles | 分阶段本地启动 | 适配 13.9 GB 可见内存 |

## 4. PostgreSQL + pgvector 的定位

概念上，PostgreSQL 对应项目所有者熟悉的 MySQL，pgvector 对应 Milvus；不同点是 pgvector 是 PostgreSQL 扩展，不是独立向量服务。

选择理由：

- 当前知识和故障数据规模小，不需要 Milvus 的分布式能力。
- 工单、资源范围、知识元数据、向量和事务可以统一管理。
- 过滤条件与向量召回在同一查询边界，降低跨数据库一致性和运维成本。
- 求职项目可以更集中展示业务模型、迁移、查询和隔离测试。

限制：

- 不把该选择宣传成适合任意大规模向量业务。
- 初期先使用精确检索基线；是否建 HNSW 由规模和评测决定。
- 中文关键词检索不能假定 PostgreSQL 默认分词足够，OP-005 用数据比较最小方案。

## 5. Agent 服务定版

OP-001 已确认生产自托管 Agent Server 还需要 Redis、许可密钥和许可校验出站；这与低资源、可独立复现的求职项目目标不匹配。正式基线固定为 FastAPI + 开源 LangGraph PostgreSQL checkpointer/store，详见 ADR-002。`langgraph dev` 只用于本地图调试，不是交付运行时或权威数据层。

## 6. 稳定工具、MCP 与原生 Provider 边界

Agent 和 Skill 只能引用 OpsPilot 稳定工具名，不能看到、选择或拼接 Superset MCP/REST URL、上游工具名和 Probe 实现。Tool Gateway 根据配置和健康状态映射 Provider，并保证授权、输入/输出 Schema、错误类型和证据语义稳定：

1. Superset MCP Provider：读取连接器状态、实例和授权范围内元数据。
2. REST/Adapter Provider：同语义元数据回退，以及精确权限、任务和应用健康。
3. 只读 Probe Provider：Worker、Beat、Redis、脱敏日志和恢复验证。

固定 Superset 6.1.0 的 MCP 启动、工具目录、认证/RBAC、工具禁用、审计、资源和错误语义必须由 OP-003 实测；滚动管理文档不能直接当成兼容性证据。Tool Gateway 必须对发现到的工具再次执行固定版本允许列表，未知新增工具默认拒绝。

稳定工具和健康语义至少分为：

| 稳定工具 | Provider 示例 | 不能误解为 |
|---|---|---|
| `check_target_connector_health` | MCP `health_check` | Superset Web/API、Worker、Redis 或任务健康 |
| `get_target_application_health` | REST health/受控 Probe | Worker/Beat/Redis 全部健康 |
| `get_target_runtime_health` | Worker/Beat/Redis 分组件 Probe | MCP 连接或 Web 应用一定健康 |
| `get_target_instance_summary` | MCP `get_instance_info` → REST/Adapter | 完整敏感配置或总体健康结论 |
| `list/get_target_{database,dataset,chart,dashboard}` | MCP list/get → REST/Adapter | 任意 SQL、数据导出或写权限 |

REST/Probe 适配器只暴露任务需要的窄接口，例如：

- 获取当前用户/角色和资源访问结果。
- 获取数据库、数据集、仪表盘和报表调度摘要。
- 获取任务状态、服务健康和脱敏日志片段。
- 在批准后触发白名单内的重试/重跑动作。
- 获取验证结果。

约束：

- 优先使用官方 REST API、健康接口和受控实验端点。
- 不把 Superset 管理员凭据或数据库连接交给模型。
- 不允许模型执行任意 URL、SQL、Shell 或直接写 Superset 元数据库。
- 适配器把第三方错误转换为稳定的领域错误，保留原始关联 ID 而不泄露密钥。
- 工单、知识、审批、检查点和 OpsPilot 数据访问保持内部服务，不因采用 MCP 而协议化。

MCP 上游首版允许：`health_check`、`get_instance_info`、`get_schema` 及数据库/数据集/图表/仪表盘的 list/get 元数据工具。Agent 仍只看到对应 OpsPilot 稳定名。`execute_sql`、保存查询、创建虚拟数据集、生成/修改图表或仪表盘等工具必须由 Tool Gateway 拒绝；Superset 支持配置禁用时再增加上游防线，并测试两层策略。

## 7. Redis、Celery 与职责隔离

必须区分两个上下文：

- **OpsPilot 自身**：首版不额外引入 Celery，避免与 LangGraph Run/检查点形成两套状态和重试机制。
- **Superset 实验环境**：定时报表/告警等真实目标功能可能需要 Redis、Celery Worker/Beat 和浏览器/邮件相关组件。这些是被诊断系统的一部分，也是服务故障场景来源。

若两边都需要 Redis，使用不同容器名、端口/网络、数据库或命名空间，配置项以 `OPSPILOT_*` 和 `SUPERSET_*` 分开，日志和仪表板不得混淆。

## 8. Docker 资源 profile

OP-001 固化的 profile：

- `core`：一个 OpsPilot 应用镜像/容器（FastAPI/LangGraph，最终由后端提供编译后的前端资产）和独立 PostgreSQL/pgvector；不含 Agent Redis/MinIO。
- `ingest-eval`：模型在宿主机单进程、按需串行运行，避免复制模型和与完整目标栈争用内存。
- `target-light`：最小 Superset Web/API + 元数据存储，验证权限/连接场景。
- `target-mcp`：在 `target-light` 基础上按需启动 Superset 原生 MCP Provider，用于兼容、安全与降级评测。
- `target-reports`：按需增加 Target Redis、Worker、Beat 和必要的报表依赖。
- `observability`：只在评测或演示时启动额外观测组件。

日常开发不默认同时启动所有 profile。最终交付用一个 Compose 入口编排应用与独立有状态/目标服务；“一个应用容器”不等于把 PostgreSQL、Superset、Redis、Worker 和 Beat 塞进同一多进程容器。

## 9. RAG 目标链路

```text
强制元数据过滤（组织/可见性/目标系统/版本/来源类型）
→ 三路候选：精确错误码/配置键/任务名 + BGE-M3 Dense + BGE-M3 Sparse
→ RRF 融合、去重
→ BGE-Reranker-Large 对小候选集重排
→ 取回父块上下文
→ Top-K 可定位引用
```

采用结构感知父子切块：子块参与三路召回和重排，命中后按 `parent_chunk_id` 取回父块补足上下文。标题层级、代码块、配置段、表格和连续步骤作为不可从中间硬切的结构单元；超长单元使用保留结构标记的受控拆分，并能回溯原文定位。

Dense-only 是评分消融基线，但所有实验都保留安全/版本元数据过滤。RAG 消融依次只增加精确通道、Sparse+RRF、Reranker，不能一次启用全部后声称某一组件有效。小规模先用 pgvector 精确检索，不建 HNSW；暂不使用 ColBERT/multi-vector、Elasticsearch 或知识图谱。

## 10. 前端策略

OP-001 选择官方 Agent Chat UI 的固定 commit 作为组件基线，不使用教程 fork 作为代码基座。OP-002 需要：

- 保留 MIT 许可归属并锁定上游 commit、Node、pnpm 和 lockfile。
- 中文化、文件/日志附件、线程、工具事件和 interrupt 展示能力。
- 修复或接受已记录的上游 lint/build warnings；移除旧 API passthrough 认证方案。

首版只增加四个核心区域：工单摘要、诊断证据/假设、工具与审批时间线、恢复验证。管理员大屏和通用页面构建器不做。

## 11. 配置与秘密

环境变量至少按以下命名空间分组：

```text
DEEPSEEK_*
EMBEDDING_*
RERANKER_*
DATABASE_*
SUPERSET_*
SUPERSET_MCP_*
OPSPILOT_SECURITY_*
```

`.env.example` 只写变量名和非敏感示例；真实 Key、密码和本机绝对机密路径只在未提交的 `.env` 中。模型路径允许作为本机配置事实记录，但模型内容不进入 Git。

## 12. 失败与降级

- DeepSeek 不可用：保存运行状态，有限重试后转人工，不伪造诊断。
- Embedding 失败：知识版本标记失败，可重建。
- Reranker 失败：可降级到已评测的召回基线，并显式显示降级。
- Superset API/服务不可用：这可能是故障证据，也可能是 Provider 故障；分别检查 MCP 连接、Web/API 和 Worker/Beat/Redis，禁止用单一 `health_check` 推断整体健康。
- Superset MCP 不可用/工具漂移：记录降级原因，对 MCP 未覆盖的既有只读能力回退原生适配器；不得静默启用新工具或把连接失败当作目标故障事实。
- Skill 加载失败：作为正式能力故障留痕，主图回退到受控基线完成诊断/升级；不得跳过权限与停止规则。
- Specialist 关闭或失败：主图使用同一稳定工具继续诊断或升级，不丢失工单状态、不重复观测/副作用。
- 部分日志不可访问：记录缺失证据，降低结论等级或升级。
- 审批期间进程重启：从检查点恢复，幂等检查后执行一次。
- Redis 短暂失败：不得丢失 PostgreSQL 中的工单、审批、动作和审计事实。

## 13. OP-001 后的未解决风险

- DeepSeek V4 普通对话、JSON、non-thinking 工具调用、无效 Key、超时和错误映射已验证；首版固定 non-thinking 基线，thinking 工具循环仅在 [`docs/09_RISKS_AND_CHANGES.md`](09_RISKS_AND_CHANGES.md) 的重评条件满足后单独验证 `reasoning_content` 回传。
- Windows 的 `sentencepiece==0.2.2` 对本地 XLM-R tokenizer 发生原生访问冲突；当前 spike 使用已核验等价的 `tokenizer.json`，正式 Linux 容器必须重新验证标准加载路径。
- 两个 BGE 模型同进程可运行，但峰值约 4.84 GiB；不得与完整 Superset reports 栈默认同时常驻。
- Superset reports 的截图/邮件链路尚未加入浏览器与 SMTP，只验证到 Web/API、Redis、worker、单 beat。
- 官方 Agent Chat UI 构建通过但有 18 个 lint warning、一个 Tailwind 模块格式 warning，且其 passthrough 认证方案已被上游提示不再推荐。
- Superset 6.1.0 原生 MCP 已有版本化用户文档依据，但当前滚动管理文档与固定镜像的 CLI、认证、工具禁用和审计尚未在本机验证；由 OP-003 关闭风险。
