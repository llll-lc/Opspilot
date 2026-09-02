# ADR-001：OpsPilot 项目方向与初始架构

- 状态：Accepted（规划期；候选技术需 OP-001 验证）
- 日期：2026-09-02

## 背景

项目所有者已完成医疗 RAG 项目，并学习包含 LangChain、LangGraph、工具调用、Agent Chat UI、文件处理、MCP、SubAgent、MinIO 和 Docker 的 Agent 教程。求职项目需要展示 RAG 之外的企业 Agent 能力，同时受到 Windows、CPU-only、约 13.9 GB 可见内存和个人开发周期约束。

此前已建立 BidPilot 招投标规格，但进一步讨论认为企业软件故障诊断更适合突出动态工具、权限、人工审批、恢复和轨迹评测。为保护已有工作，新的方向不覆盖 BidPilot，而是建立独立仓库。

## 决定

1. 新建独立项目 `D:\Agent\OpsPilot`；`D:\Agent\BidPilot` 保持不变。
2. 产品定位为“企业软件智能故障诊断与工单闭环 Agent”，首个垂直落点收窄到企业 BI / 数据平台支持。
3. Apache Superset 作为首个真实目标系统和故障实验环境，不进入项目名；README 透明披露来源、许可证和非官方关系。
4. 最终求职版覆盖数据库连接、权限、定时报表、导出和服务健康五类故障；Gate A 先完成三类至少五个确定性场景。
5. 先建立自动注入、断言、重置的故障真值，再开发知识、工具和 Agent，防止固定脚本/RAG 套壳。
6. 采用模块化单体和一张主要 LangGraph 工作流，结合结构化输出、受控工具、checkpoint、Human-in-the-loop、幂等和恢复验证。
7. 使用 PostgreSQL + pgvector 保存业务与向量数据；DeepSeek 作为配置化 LLM，本地 BGE-M3 / BGE-Reranker-Large负责检索。
8. Agent 服务先评估 Agent Server + FastAPI 自定义路由；不满足自托管、许可或资源条件时，回退 FastAPI + 开源 LangGraph 持久化。
9. Agent 自身不引入 Celery。Superset 报表实验所需 Redis、Worker 和 Beat 属于目标系统，并与 Agent 配置/网络隔离。
10. Redis、MinIO、Reranker 等候选组件只有在 OP-001/后续评测证明职责和收益时定版，不为教程覆盖率强行保留。
11. Agent 不获得 Docker Socket、任意 Shell/SQL 或 Superset 元数据库写权限；故障注入仅存在于隔离的测试控制面。
12. 前端复用经许可证与兼容性审计的教程/官方 Agent Chat UI 基线，只增加工单、证据、工具轨迹、审批和验证所需页面。

## 理由

- 企业软件排障需要知识与实时状态结合，能清楚展示 Agent 相对普通 RAG 的新增价值。
- Superset 有公开代码、文档、API、权限和异步报表组件，可形成真实但可控的企业软件实验环境。
- 可重复故障和机器真值使根因、工具轨迹、安全和恢复能够自动评测，而不是只做演示视频。
- 单图、模块化单体和分阶段 profile 更适合个人开发、CPU-only 设备和面试解释。
- PostgreSQL + pgvector 减少 MySQL + Milvus 双存储的一致性与资源成本，足以支撑作品级规模。

## 代价

- Windows 不是 Superset 官方支持的 Compose 环境，必须先做兼容性 spike。
- 报表/导出可能引入 Redis、Celery 和浏览器，完整栈资源较高，需要分 profile 演示。
- 真实 API 与故障注入比生成静态问答数据开发更慢，但这是项目可信度的必要成本。
- 项目不能宣称覆盖所有企业软件，也不能用 POC 指标推断生产收益。

## 被否决或暂缓的方案

- 覆盖 BidPilot 目录：会丢失已确认规格和 Git 历史，拒绝。
- 项目名直接写“Superset Agent”：会把作品限制为单一产品插件，暂不采用。
- 通用 SaaS 客服/FAQ Agent：难体现实时诊断和安全动作闭环，拒绝作为核心。
- 一开始支持多个企业软件：会先建设抽象框架而不是可验证场景，暂缓。
- MySQL + Milvus：技术上可行，但当前数据规模和资源不需要两个数据系统。
- 多 Agent、MCP 化内部函数、完整 ITSM、Kubernetes：没有可测收益且增加复杂度，首版排除。
- Agent 直接操作 Docker 或 Superset 元库：权限风险过高且绕过产品边界，禁止。

## 验证与回退

OP-001 必须验证本机资源、Superset 最小/报表 profile、公开 API、DeepSeek、BGE、前端和 Agent 服务候选。

- Agent Server 不成立：新增 ADR，回退 FastAPI + LangGraph 开源 checkpoint/store。
- 完整 Superset 报表栈过重：核心三类场景保留真实 Superset API，重型故障使用明确标记的确定性 fixture；最终演示分步骤启动。
- 两个 BGE 模型同时常驻过重：先按需/串行加载；Reranker 无显著收益则不启用。
- Redis/MinIO 没有明确 Agent 职责：从 Agent 栈删除，不视为功能降级。

任何回退都不能取消运行时证据、权限策略、HITL、幂等、故障真值和轨迹评测这些核心深度。

## 结果

后续会话不再重新评选 BidPilot 与 OpsPilot。重大方向变化按 `docs/09_RISKS_AND_CHANGES.md` 登记；技术候选由 OP-001 实测，而不是由规划文本假定成功。
