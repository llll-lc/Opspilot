# 10 开发链路、交付与演示

## 1. 完整开发链路

```text
OP-000 规格与跨会话制度
→ OP-001 环境/资源/版本/部署风险闸门
→ OP-002 仓库脚手架与最小前端基线
→ OP-003 Superset 真实 API/MCP 风险闸门 + 三类/五场景故障真值
→ OP-004 PostgreSQL/pgvector、父子块和稳定工具/Provider 领域模型
→ OP-005 结构感知父子切块、混合 RAG、Skills 与 RAG 消融
→ OP-006 工单、稳定 Tool Gateway、REST/Probe/MCP Provider 与降级
→ OP-007 可独立闭环 Incident Commander、Skill 消融、HITL 和恢复
→ OP-008 诊断与工单工作台
→ OP-009 扩展五类场景/Skills + 最后实现可关闭 Specialist + 四类分轴评测
→ OP-010 安全、降级、恢复和可观测性回归
→ OP-011 Docker profiles 与端到端验收
→ OP-012 求职材料、演示和代码复盘
```

顺序的关键是先证明故障和真值，再写 Agent；不能先让模型“看起来会诊断”，最后才寻找能配合回答的数据。

## 2. 里程碑

### M1：风险解除（OP-001～OP-002）

- 本机版本、模型资源、DeepSeek、Agent 服务候选、前端和 Superset 最小启动得到实测。
- 仓库骨架和质量门禁建立，但不堆业务空壳。

### M2：可信故障与证据底座（OP-003～OP-006）

- 三个核心故障家族至少五个场景能注入、断言和重置。
- Superset 6.1.0 原生 MCP 风险闸门完成；知识引用、父子块混合 RAG、首批 Skills、稳定工具、REST/Probe/MCP Provider 和审计可用。

### M3：Agent 业务闭环（OP-007～OP-008）

- Incident Commander 根据运行时证据动态诊断，在所有增强关闭时仍能完成追问、升级、审批、恢复和验证；Skill 独立消融完成。
- 前端展示业务状态，不只是聊天框。

### M4：求职交付（OP-009～OP-012）

- 扩展五类故障，最后实现两个可关闭 Specialist，完成 RAG/Skill/MCP/Specialist 分轴评测、安全、Docker、演示和复盘。

## 3. 周期预期

在 Codex 承担绝大多数实现、测试和文档，用户及时完成密钥/下载批准和体验验收的前提下：

- 4～7 个有效开发日：Gate A、Superset MCP 风险闸门和最小可运行诊断原型，不适合作为最终求职交付。
- 10～15 个有效开发日：三类核心故障、混合 RAG、首批 Skills、稳定工具/MCP 降级、独立主 Agent、HITL、工单、UI 和基础评测完整。
- 15～23 个有效开发日：覆盖最终五类故障/Skills、最后实现 Specialist、完成四类分轴评测、安全回归、Docker 演示和求职材料的较完整版本。

这是工作量估算，不是日历承诺。Superset 在 Windows/Docker 的兼容性、镜像下载、CPU 推理和用户可参与时间会改变周期。风险闸门若发现重型场景不可行，应采用已定义回退，而不是跳过真值和安全。

## 4. 教程知识映射

| 教程主题 | OpsPilot 中的实际应用 | 是否必须 |
|---|---|---|
| LangChain Agent / Tool Calling | 选择权限内的状态与工单工具 | 是 |
| ReAct 思路 | 有界诊断循环和假设更新 | 是，但不开放无限循环 |
| 结构化输出 | 症状、假设、计划、诊断、升级和验证 Schema | 是 |
| 流式输出 | 节点、工具和等待审批的进度 | 是 |
| LangGraph | 可独立主控图、条件路由、checkpoint、interrupt；最后增加可关闭专家子图 | 是 |
| FastAPI + 开源 LangGraph | Thread/Run/SSE、本地运行与 PostgreSQL persistence | 是，ADR-002 |
| Middleware | 认证上下文、重试、限流、日志和脱敏 | 按需必须 |
| Agent Chat UI | 对话、Thread、工具事件和审批基线 | 是，兼容审计后复用 |
| RAG | 结构感知父子切块、精确+Dense+Sparse+RRF+Reranker 与引用 | 是；Dense-only 为消融基线 |
| PostgreSQL/pgvector | 工单/审计/向量统一存储 | 是 |
| 项目数据目录 + PostgreSQL 元数据/哈希 | 附件、日志样本和产物 | 是；首版不引入 MinIO |
| Docker Compose | 资源 profile 和可复现实验环境 | 是 |
| 本地结构化观测 | 诊断轨迹与评测 | 是；Langfuse 按重评条件延后 |
| MCP | Tool Gateway 背后的 Superset 原生只读 Provider、允许列表和降级 | 必须接入/评测，但运行时不是单点依赖 |
| SubAgent | Access & Connectivity、Jobs & Runtime 两个有界只读 Specialist | 最后实现、可关闭；默认开关由独立消融决定 |
| DeepAgents | 可选实现 helper | 否；不为框架名称重写主图 |
| Agent Skill | 首批三个、最终五个版本化排障 SOP | 是；固定 Registry，禁止动态安装 |
| OCR/图像 | 截图错误识别 | 首版不做 |

项目覆盖教程中最适合企业 Agent 的知识；MCP、Skill 和 SubAgent 都必须有清晰职责和评测，不以章节覆盖率为目标。

## 5. 主演示脚本

1. 展示本地 POC、数据来源和 Superset 非官方关系声明。
2. 以业务用户身份报告“每日销售报表今天没有收到”。
3. Agent 补问报表、时间和影响范围，创建/关联工单。
4. 展示检索到的官方说明和合成内部 Runbook 引用。
5. 展示结构感知父子检索和 `scheduled-report-triage` Skill 的按需加载、证据门槛和禁止动作。
6. 展示 OpsPilot 稳定工具时间线：MCP 连接器健康、Superset Web/API 健康和 Worker/Redis 健康是三类不同证据。
7. 注入 MCP 断连并展示同一稳定工具降级到 REST/Probe，主 Agent 继续运行。
8. 展示候选根因与动态工具时间线：调度配置、最近运行、Worker、Redis、日志。
9. 动作计划在 LangGraph interrupt 处等待授权人审批。
10. 模拟进程重启后恢复；已完成查询/工单不重复，批准动作只执行一次。
11. 恢复 Worker 或执行受控重跑，验证新任务和产物成功，然后更新/关闭工单。
12. 用相同用户表述切换为“任务被禁用”根因，展示不同检查结果和处置。
13. 快速展示权限、连接、导出和服务故障样本及未知场景安全升级；另展示一次可选 Specialist 委派，并说明消融决定的默认开关。
14. 展示 Pure RAG、Fixed Rules、OpsPilot 业务对比，以及 RAG、Skill、MCP、Specialist 四份分轴报告。

目标主演示 8～12 分钟，另准备 2～3 分钟简版。

## 6. 最终仓库内容

- 清晰 README、架构图、业务边界和 Superset 非官方声明。
- 前后端代码、迁移、测试、锁文件和 `.env.example`。
- Docker Compose profiles、健康检查、种子和安全清理说明。
- 来源 manifest、合成 Runbook、父子块索引、版本化 Skills、稳定工具/ProviderBinding 清单、MCP 工具目录快照、故障场景和少量演示数据。
- 自动故障注入/重置/断言脚本与冻结评测集。
- 根因、轨迹、安全和资源报告，以及相互独立的 RAG、Skill、MCP、Specialist 评测报告。
- 演示脚本、截图/短视频说明、项目复盘、简历和面试材料。

模型文件、数据库卷、真实密钥/Cookie、用户敏感信息、不明许可原文和大型生成物不进入仓库。

## 7. 求职表述边界

可以表述：

> 构建面向企业 BI/数据平台支持的可恢复诊断 Agent，以 Apache Superset 作为首个真实故障实验环境；用 LangGraph 主图完成独立诊断闭环，以版本化 Skill 规范排障方法，通过稳定 Tool Gateway 可降级接入 MCP/REST/Probe，并用可重复故障真值和分轴消融评测检索、工具、委派、安全及幂等性。

不应表述：

- 与 Apache/Superset 官方合作或基于其资料自研了 Superset。
- 已替代 ServiceNow/Jira 或能诊断所有企业软件。
- 已在真实企业生产落地、降低具体 MTTR/成本但没有试点证据。
- Agent 可安全执行任意运维操作。
- 教程或第三方已有能力全部由自己从零研发。

## 8. 面试深度体现

项目的深度不靠服务数量，而来自：

- 相同症状由实时证据区分不同根因。
- 主 Agent 不依赖增强仍能闭环；Skill、MCP Provider 和 Specialist 各自有独立职责、降级路径和分轴评测。
- Agent 只依赖稳定工具语义，MCP/REST/Probe 切换及健康范围不会泄漏进推理契约。
- 父子切块和精确/Dense/Sparse/RRF/Reranker 每一步都有独立检索证据，而不是堆算法名词。
- 工具的身份/资源范围、风险分级和服务端授权。
- checkpoint 与外部副作用之间的幂等设计。
- 知识证据、运行时证据和恢复证据的明确区分。
- 故障注入/重置/断言、冻结测试和轨迹级评测。
- Prompt 注入、越权、审批重放和工具失败的安全回归。
- CPU-only/Windows 环境中的可测资源取舍。

## 9. 项目所有者的学习交付

每个 OP 开始前的理解目标、完成后的讲解目标和权威阅读入口统一维护在 [`docs/11_OWNER_LEARNING_MAP.md`](11_OWNER_LEARNING_MAP.md)。本文件不再复制另一套逐任务学习清单；最终演示和面试复盘必须能从学习地图链接回实际规格、任务、交接和评测证据。
