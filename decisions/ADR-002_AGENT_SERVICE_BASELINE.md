# ADR-002：Agent 服务回退到 FastAPI + 开源 LangGraph persistence

- 状态：Accepted
- 日期：2026-09-02
- 责任任务：OP-001

## 背景

ADR-001 将 Agent Server + FastAPI 自定义路由列为候选，并要求在 OP-001 核对自托管、许可、PostgreSQL/Redis、SDK 与本机资源；不成立时回退到 FastAPI + 开源 LangGraph persistence。

执行日的 LangChain 官方资料确认：

- `langgraph dev` 是单进程开发/测试服务器，数据落在本地 `.langgraph_api`，不是项目的独立交付运行时。
- 生产自托管 Standalone Agent Server 要求 PostgreSQL、Redis、`LANGSMITH_API_KEY`、`LANGGRAPH_CLOUD_LICENSE_KEY`，并需向许可校验端点出站。
- Agent Server 支持把 FastAPI app 注册为自定义路由，但这不消除上述服务、许可和出站要求。
- 开源 LangGraph 可直接使用 PostgreSQL checkpointer/store 支持 thread、interrupt、恢复和持久化；Redis 不是该路径的必要组件。

本机当前只有 13.87 GB 物理内存，Docker 当前配额约 6.70 GiB。OpsPilot 还需分阶段运行本地 BGE 模型和 Superset 实验环境。为复用 Agent Server 的协议而增加 Redis、许可密钥与许可出站，会扩大资源、交付和隐私边界，但不会增加本项目要展示的核心诊断能力。

## 决定

1. 正式交付基线选择模块化 FastAPI + 开源 LangGraph。
2. LangGraph 状态使用 PostgreSQL persistence；业务事实和向量仍使用同一 PostgreSQL 实例中的隔离数据库或 schema，具体迁移边界由 OP-004 固化。
3. 首版不保留 Agent 侧 Redis。Redis 仅在 Superset `target-reports` profile 中作为被诊断目标系统的依赖。
4. `langgraph dev` 可用于本地图调试和与官方 Agent Chat UI 的协议验证，但不作为部署承诺，也不作为业务数据的权威持久层。
5. 前端可以复用官方 Agent Chat UI 的组件与交互模型；OP-002 必须把生产请求接到 OpsPilot 自有认证/API 边界，不能要求最终用户持有 LangSmith API Key。

## 结果

- 删除 Agent Server、Agent Redis 和生产许可校验出站的默认依赖。
- OpsPilot 自身只保留一个应用进程和 PostgreSQL 作为首版核心运行时。
- Thread/Run/SSE 契约需由 OpsPilot API 明确定义；这会增加少量接口实现，但安全范围、幂等和审计均由本项目确定性代码控制。
- 若未来改回 Agent Server，必须新增 ADR，并重新验证许可、出站、认证、资源和数据边界。

## 证据

- https://docs.langchain.com/langsmith/cli （访问日期：2026-09-02）
- https://docs.langchain.com/langsmith/deploy-standalone-server （访问日期：2026-09-02）
- https://docs.langchain.com/langsmith/custom-routes （访问日期：2026-09-02）
- https://docs.langchain.com/oss/python/langgraph/persistence （访问日期：2026-09-02）
