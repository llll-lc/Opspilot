# 11 项目所有者学习地图

## 1. 用途与边界

本地图帮助项目所有者在每个 OP 开始前建立必要概念，在完成后用自己的语言复盘。它不是技术规格、任务状态或实现证据，不记录版本号、工具允许列表、阈值和测试结果；发生冲突时，以链接的 ADR、专题规格、当前任务、实际代码/测试和交接为准。

使用方法：

1. 开始任务前先执行 [`AGENTS.md`](../AGENTS.md) 和 [`docs/07_DEVELOPMENT_WORKFLOW.md`](07_DEVELOPMENT_WORKFLOW.md) 的新会话流程，再阅读本表对应入口。
2. 完成任务后以任务验收、测试和 `handoffs/OP-xxx.md` 为证据，回答“完成后应能解释”；不能只背本表措辞。
3. 尚未创建的任务文件不在本地图提前生成；任务范围始终以 [`TASKS.md`](../TASKS.md) 和当时创建的 `tasks/OP-xxx.md` 为准。

## 2. 分阶段学习目标

| OP | 开始前应理解什么 | 完成后应能解释什么 | 权威阅读入口 |
|---|---|---|---|
| OP-000 | 为什么要先固定业务范围、证据标准和跨会话规则 | 如何判断需求、ADR、任务状态和聊天建议的权威级别 | [业务范围](01_BUSINESS_AND_SCOPE.md)、[开发流程](07_DEVELOPMENT_WORKFLOW.md)、[风险变更](09_RISKS_AND_CHANGES.md) |
| OP-001 | 风险闸门与“候选技术不等于已验证事实”的区别 | 哪些环境/版本/资源结论已经实测，哪些仍待验证及其回退 | [环境版本](08_ENVIRONMENT_AND_VERSIONS.md)、[ADR-002](../decisions/ADR-002_AGENT_SERVICE_BASELINE.md)、[OP-001 交接](../handoffs/OP-001.md) |
| OP-002 | 四层架构的依赖方向，以及脚手架和业务实现的边界 | 仓库结构、配置入口、前后端边界和质量门禁为何这样划分；指出哪些仅为包边界 | [ADR-003](../decisions/ADR-003_CONTROLLED_AGENT_MCP_SKILLS_ARCHITECTURE.md)、[系统架构](02_ARCHITECTURE_AND_TECH_STACK.md)、[当前状态](../CURRENT_STATE.md) |
| OP-003 | 故障真值、运行时证据、MCP 风险闸门和健康范围的区别 | 如何注入/断言/重置故障；为什么 MCP 连通不等于目标系统整体健康；失败怎样回退 | [知识与故障真值](05_KNOWLEDGE_FAULTS_AND_GROUND_TRUTH.md)、[安全验收 Gate A](06_SECURITY_EVALUATION_ACCEPTANCE.md)、[环境版本](08_ENVIRONMENT_AND_VERSIONS.md) |
| OP-004 | 业务事实、Graph State、Evidence、稳定工具和 ProviderBinding 的职责 | 数据关系、事务/幂等边界、父子块及工具 Provider 审计怎样支撑后续模块 | [领域模型](03_DOMAIN_AND_DATA_MODEL.md)、[架构边界](02_ARCHITECTURE_AND_TECH_STACK.md) |
| OP-005 | 来源、Runbook、Skill、父子切块和检索评分链分别解决什么 | 如何从来源进入父子块和索引；怎样读 RAG 消融并解释保留/放弃某检索组件 | [知识/RAG/Skill](05_KNOWLEDGE_FAULTS_AND_GROUND_TRUTH.md)、[RAG 与 Skill 评测](06_SECURITY_EVALUATION_ACCEPTANCE.md)、[ADR-003](../decisions/ADR-003_CONTROLLED_AGENT_MCP_SKILLS_ARCHITECTURE.md) |
| OP-006 | Agent 稳定工具与 MCP/REST/Probe Provider 的隔离；服务端授权为何不能交给模型 | 同一稳定工具如何授权、映射、审计和降级；工单/动作如何防止越权与重复 | [工具与 Provider](02_ARCHITECTURE_AND_TECH_STACK.md)、[领域模型](03_DOMAIN_AND_DATA_MODEL.md)、[安全约束](06_SECURITY_EVALUATION_ACCEPTANCE.md) |
| OP-007 | 可独立主 Agent、LangGraph 状态、动态诊断、interrupt/checkpoint 和 Skill 开关 | 主图如何在增强关闭时闭环；Skill 如何改变方法而不改变权限；副作用如何恢复一次 | [Agent 工作流](04_AGENT_WORKFLOW.md)、[ADR-003](../decisions/ADR-003_CONTROLLED_AGENT_MCP_SKILLS_ARCHITECTURE.md)、[Gate B](06_SECURITY_EVALUATION_ACCEPTANCE.md) |
| OP-008 | 对话事件与业务状态、证据、工具轨迹、审批、验证之间的关系 | UI 如何呈现真实后端状态、等待/恢复和 Provider 降级，而不是制造仅前端存在的流程 | [业务流程](01_BUSINESS_AND_SCOPE.md)、[前端策略](02_ARCHITECTURE_AND_TECH_STACK.md)、[可观测性](04_AGENT_WORKFLOW.md) |
| OP-009 | 冻结集、单变量消融、轨迹真值和 Specialist 受控边界 | 怎样分别解读 RAG、Skill、MCP、Specialist 报告；为什么 Specialist 默认开关由证据决定 | [评测与 Gate C](06_SECURITY_EVALUATION_ACCEPTANCE.md)、[故障/轨迹真值](05_KNOWLEDGE_FAULTS_AND_GROUND_TRUTH.md)、[ADR-003](../decisions/ADR-003_CONTROLLED_AGENT_MCP_SKILLS_ARCHITECTURE.md) |
| OP-010 | Prompt 注入、工具漂移、审批重放、跨范围访问和降级失败模式 | 如何用测试证明稳定工具、Skill、MCP、Specialist、HITL 和恢复路径没有扩大权限 | [威胁与安全回归](06_SECURITY_EVALUATION_ACCEPTANCE.md)、[风险登记](09_RISKS_AND_CHANGES.md)、[Agent 防护](04_AGENT_WORKFLOW.md) |
| OP-011 | Compose profile、应用/基础设施/目标系统边界和 CPU-only 资源取舍 | 如何启动、诊断和停止各 profile；怎样根据资源报告解释按需加载与回退 | [环境与 Profiles](08_ENVIRONMENT_AND_VERSIONS.md)、[架构/部署](02_ARCHITECTURE_AND_TECH_STACK.md)、[性能验收](06_SECURITY_EVALUATION_ACCEPTANCE.md) |
| OP-012 | POC 能证明什么、不能声称什么；演示结论必须指向证据 | 在演示/简历/面试中讲清业务价值、四层架构、关键取舍、失败样本和个人掌握边界 | [交付与演示](10_DELIVERY_AND_DEMO.md)、[README](../README.md)、[业务成功定义](01_BUSINESS_AND_SCOPE.md) |

## 3. 每个任务的最小复盘动作

每个 OP 完成后，项目所有者至少亲自完成一次：

1. 按任务文档运行一个主要验证入口，看到成功与失败各一条证据。
2. 沿 UI/API → 主图/服务 → 稳定工具/数据 → 目标系统追踪一条真实链路。
3. 不看提示词，用三分钟说明该任务解决的问题、确定性代码与模型各负责什么、主要失败与回退是什么。
4. 将无法解释的问题记录到该任务复盘，不修改本地图来掩盖实现差距。
