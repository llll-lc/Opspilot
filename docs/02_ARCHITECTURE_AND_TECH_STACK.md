# 02 系统架构与技术栈

## 1. 架构原则

- 模块化单体优先，不拆微服务。
- 一张主要 LangGraph 图优先，不做多 Agent 编排。
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
│ OpsPilot 应用（FastAPI + 开源 LangGraph persistence）     │
├───────────────────────────────────────────────────────────┤
│ 单主图：受理→补问→诊断→审批→处置→验证→闭环/升级           │
├─────────────────┬───────────────────┬─────────────────────┤
│ 领域服务        │ 知识检索服务      │ Tool Gateway        │
│ 工单/策略/审计  │ BGE + Reranker    │ 鉴权/参数/幂等/适配  │
└───────┬─────────┴────────┬──────────┴──────────┬──────────┘
        │                  │                     │
┌───────▼───────────────┐                 ┌──────▼──────────┐
│ OpsPilot PostgreSQL   │                 │ Superset Lab    │
│ + pgvector            │                 │ API/健康/任务   │
└───────────────────────┘                 └──────┬──────────┘
                                                  │ 按 profile
                                          ┌───────▼─────────┐
                                          │ Target Redis /  │
                                          │ Worker / Beat   │
                                          └─────────────────┘
```

## 3. 技术栈及职责

| 层 | 规划技术 | 职责 | 定版条件 |
|---|---|---|---|
| IDE | PyCharm | Python 后端开发、调试和测试 | OP-001 记录配置，不提交个人设置 |
| 前端 | 官方 Agent Chat UI 组件基线（commit `325517352ca3672c8bc0745c4143b2301dd74997`） | Next.js/React/TypeScript；对话、工单、证据、轨迹、审批和验证 | 不沿用上游 API passthrough 认证边界 |
| Agent | LangGraph | 显式状态、条件路由、interrupt、checkpoint | 单主图 |
| Agent 服务 | FastAPI + 开源 LangGraph persistence | 自有 Thread/Run/SSE、认证、持久化和业务 API | ADR-002 已定版 |
| 业务 API | FastAPI | 工单、知识、审批、评测等确定性接口 | 不要求全部走模型工具 |
| 数据访问 | SQLAlchemy + Alembic 候选 | ORM、事务和迁移 | 与最终 Python 版本兼容 |
| 关系/向量 | PostgreSQL + pgvector | 工单、审计、检查点边界、1024 维向量 | 作品级规模优先准确过滤 |
| 临时状态 | 不设 Agent Redis | 首版无明确独立职责；状态与检查点进入 PostgreSQL | Target Redis 仅属于 Superset reports profile |
| 对象存储 | 项目数据目录 + PostgreSQL 元数据/哈希 | POC 知识原文、附件和评测产物 | 首版删除 MinIO；出现多机/对象语义需求再 ADR |
| LLM | DeepSeek OpenAI-compatible API | 语义分类、假设、计划、解释和结构化输出 | 模型名与接口 OP-001 实测 |
| Embedding | 本地 BGE-M3 | 稠密检索，1024 维 | CPU 单实例 |
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

## 6. 目标系统适配边界

`SupersetAdapter` 只暴露任务需要的窄接口，例如：

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
- `target-reports`：按需增加 Target Redis、Worker、Beat 和必要的报表依赖。
- `observability`：只在评测或演示时启动额外观测组件。

日常开发不默认同时启动所有 profile。最终交付用一个 Compose 入口编排应用与独立有状态/目标服务；“一个应用容器”不等于把 PostgreSQL、Superset、Redis、Worker 和 Beat 塞进同一多进程容器。

## 9. 检索架构

最小演进顺序：

1. 来源、目标系统、版本、文档类型和访问范围过滤。
2. BGE-M3 稠密向量召回。
3. 用简单关键词/精确错误码通道补充配置键、错误码和组件名。
4. 合并去重后，让 BGE-Reranker-Large 只处理小候选集。
5. 返回 Top-K 引用、版本和来源定位。

先测 Dense-only，再保留能在固定评测集上产生可解释收益的混合检索和 Reranker。不要同时堆入 BGE 稀疏、多向量、Elasticsearch 和复杂知识图谱。

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
OPSPILOT_SECURITY_*
```

`.env.example` 只写变量名和非敏感示例；真实 Key、密码和本机绝对机密路径只在未提交的 `.env` 中。模型路径允许作为本机配置事实记录，但模型内容不进入 Git。

## 12. 失败与降级

- DeepSeek 不可用：保存运行状态，有限重试后转人工，不伪造诊断。
- Embedding 失败：知识版本标记失败，可重建。
- Reranker 失败：可降级到已评测的召回基线，并显式显示降级。
- Superset API/服务不可用：这可能是故障证据，也可能是工具故障；通过健康检查和错误类型区分。
- 部分日志不可访问：记录缺失证据，降低结论等级或升级。
- 审批期间进程重启：从检查点恢复，幂等检查后执行一次。
- Redis 短暂失败：不得丢失 PostgreSQL 中的工单、审批、动作和审计事实。

## 13. OP-001 后的未解决风险

- DeepSeek V4 普通对话、JSON、non-thinking 工具调用、无效 Key、超时和错误映射已验证；thinking 工具循环仍需在 OP-007 验证 `reasoning_content` 回传。
- Windows 的 `sentencepiece==0.2.2` 对本地 XLM-R tokenizer 发生原生访问冲突；当前 spike 使用已核验等价的 `tokenizer.json`，正式 Linux 容器必须重新验证标准加载路径。
- 两个 BGE 模型同进程可运行，但峰值约 4.84 GiB；不得与完整 Superset reports 栈默认同时常驻。
- Superset reports 的截图/邮件链路尚未加入浏览器与 SMTP，只验证到 Web/API、Redis、worker、单 beat。
- 官方 Agent Chat UI 构建通过但有 18 个 lint warning、一个 Tailwind 模块格式 warning，且其 passthrough 认证方案已被上游提示不再推荐。
