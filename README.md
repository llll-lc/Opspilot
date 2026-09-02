# OpsPilot

OpsPilot 是一个面向企业内部 IT / 数据平台支持团队的“智能故障诊断与工单闭环 Agent”。它根据用户故障描述主动补问，查询系统状态、权限、任务和日志，结合运维知识形成可引用的根因判断；低风险动作可受控执行，高风险动作进入人工审批，最后验证恢复并更新工单。

当前仓库处于“OP-001 风险闸门完成、尚未开始正式业务编码”阶段。

## 项目要解决的问题

企业软件支持并不只是回答文档。真实处理过程通常需要在知识库、用户权限、资源状态、后台任务、服务健康和工单系统之间切换，容易出现信息遗漏、排查路径不一致、重复建单、未经授权操作和故障解决后没有验证等问题。

OpsPilot 展示的核心能力是：让 Agent 在权限边界内完成一条可暂停、可恢复、可审计、可评测的诊断链路，而不是做一个通用 FAQ 聊天机器人。

## 核心业务链路

```text
用户报告故障
→ 识别用户、目标系统和受影响资源
→ 补问缺失信息并建立支持工单
→ 检索官方文档/内部 Runbook
→ 调用只读工具查询权限、任务、服务状态与日志
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

## 技术方向（候选组件需实测）

- 前端：Next.js / React / TypeScript，复用经兼容性审计的 Agent Chat UI 能力并增加诊断与工单工作台。
- Agent：LangGraph 单主图，结构化输出、受控工具调用、检查点和 Human-in-the-loop。
- 服务：FastAPI + 开源 LangGraph PostgreSQL persistence；生产 Agent Server 路径已由 ADR-002 排除。
- 数据：PostgreSQL + pgvector 为核心；首版不设 Agent Redis/MinIO，Target Redis 只属于 Superset reports profile。
- LLM：DeepSeek 官方 OpenAI-compatible API，具体模型名由环境任务核验并配置化。
- 检索：本地 BGE-M3 + BGE-Reranker-Large，CPU-only、单推理并发。
- 目标系统：Apache Superset 的最小 Docker 实验环境；定时报表场景按需启用其 Celery Worker/Beat 等依赖。
- 开发环境：Windows、Docker Desktop、PyCharm；最终构建一个 OpsPilot 应用镜像，并由 Compose 编排独立数据库和目标系统容器。

## 项目边界

OpsPilot 是求职作品级 POC，不是 ServiceNow/Jira Service Management 的替代品，也不是承诺可直接接入生产的自动运维平台。首版不做通用 AIOps、基础设施全自动修复、远程 Shell、生产凭据变更、完整 ITSM、多 Agent 自由协作或大型多租户 SaaS。

## 规格入口

- 长期项目上下文：[`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md)
- 当前状态：[`CURRENT_STATE.md`](CURRENT_STATE.md)
- 任务总表：[`TASKS.md`](TASKS.md)
- 业务与范围：[`docs/01_BUSINESS_AND_SCOPE.md`](docs/01_BUSINESS_AND_SCOPE.md)
- 架构与技术栈：[`docs/02_ARCHITECTURE_AND_TECH_STACK.md`](docs/02_ARCHITECTURE_AND_TECH_STACK.md)
- Agent 工作流：[`docs/04_AGENT_WORKFLOW.md`](docs/04_AGENT_WORKFLOW.md)
- 数据与故障真值：[`docs/05_KNOWLEDGE_FAULTS_AND_GROUND_TRUTH.md`](docs/05_KNOWLEDGE_FAULTS_AND_GROUND_TRUTH.md)
- 开发协作：[`docs/07_DEVELOPMENT_WORKFLOW.md`](docs/07_DEVELOPMENT_WORKFLOW.md)

## 诚实的项目表述

本项目将使用公开官方资料、受控 Superset 实验环境和明确标注的合成工单/日志数据。可以证明“在已定义测试场景下能够诊断、审批、执行和验证”；除非未来确实发生，不得声称已在真实企业部署或产生真实业务收益。
