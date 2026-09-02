# 03 领域模型与数据设计

本文件定义业务概念和关系，具体表名、字段类型、索引与迁移由 OP-003 实现后回写。概念模型不是最终 SQL。

## 1. 核心实体

| 实体 | 作用 | 关键关系 |
|---|---|---|
| Organization | 数据与授权边界 | 拥有用户、工单、知识和目标系统连接 |
| User | 报障、支持、审批或审计主体 | 属于组织并拥有角色 |
| TargetSystem | 被支持的软件实例 | 首个类型为 Superset，拥有资源和适配配置 |
| TargetResource | 仪表盘、数据集、数据库连接、报表任务或服务 | 属于 TargetSystem，可被工单引用 |
| SupportCase | 一次支持工单 | 关联用户、资源、诊断运行和时间线 |
| CaseMessage | 用户/支持/Agent 的可见消息 | 属于工单，区分内容来源 |
| DiagnosticRun | 一次可恢复诊断执行 | 关联 LangGraph Thread/Run、版本和状态 |
| Hypothesis | 候选根因 | 拥有支持/反对证据和当前状态 |
| Evidence | 知识引用、工具观测、用户确认或验证结果 | 连接工单、运行、假设和来源 |
| ToolDefinition | 工具契约与风险元数据 | 定义读写级别、参数和授权策略 |
| ToolExecution | 一次工具调用 | 保存请求摘要、结果、耗时、授权与幂等键 |
| ActionPlan | 建议执行的修复步骤 | 关联风险、预期、验证计划和审批 |
| Approval | 人工审批决定 | 保存审批人、范围、期限、理由和版本 |
| ActionExecution | 实际副作用 | 关联 ActionPlan、ToolExecution 和幂等记录 |
| Verification | 修复后验证 | 保存系统证据、用户确认和结果 |
| AuditEvent | 不可静默覆盖的操作事件 | 记录谁在何时改变了什么 |
| KnowledgeDocument | 官方资料或内部 Runbook 元数据 | 拥有版本、来源、许可和 Chunk |
| KnowledgeChunk | 检索最小单元 | 保存文本、定位、Embedding 和范围 |
| FaultScenario | 可复现故障定义与真值 | 关联注入、重置、预期工具和根因 |
| EvaluationCase/Run | 评测输入、输出和指标 | 记录代码、数据、模型和工具版本 |

## 2. 关键关系

```text
Organization
├─ User
├─ TargetSystem ─ TargetResource
├─ KnowledgeDocument ─ KnowledgeChunk
└─ SupportCase
   ├─ CaseMessage
   ├─ DiagnosticRun
   │  ├─ Hypothesis ─ Evidence
   │  ├─ ToolExecution ─ Evidence
   │  └─ ActionPlan ─ Approval ─ ActionExecution ─ Verification
   └─ AuditEvent

FaultScenario ─ EvaluationCase ─ EvaluationRun
```

## 3. SupportCase 建议字段

- `id`, `organization_id`, `target_system_id`
- `reporter_user_id`, `assignee_user_id`
- `title`, `description`, `status`, `priority`, `impact_scope`
- `resource_type`, `resource_id`
- `symptom_code`, `occurred_at`, `expected_behavior`
- `deduplication_key`, `source_channel`
- `resolution_summary`, `root_cause_code`
- `created_at`, `updated_at`, `resolved_at`, `closed_at`

去重键不能只依赖标题相似度；至少组合组织、目标系统、资源、症状类别和时间窗口。Agent 提示相似工单时，由确定性服务决定关联还是新建。

## 4. DiagnosticRun 与 Graph State

DiagnosticRun 保存长期业务事实：

- 工单、Thread/Run、Prompt、模型、工具目录和知识索引版本。
- 当前阶段、结论等级、根因代码和升级原因。
- 已完成检查、重试次数、降级组件和成本摘要。

LangGraph State 只保存执行所需的小型引用：

- `organization_id`, `actor_user_id`, `support_case_id`
- `target_system_id`, `resource_refs`
- `diagnostic_run_id`, `thread_id`
- `normalized_symptom`, `missing_fields`
- `hypothesis_ids`, `active_hypothesis_ids`
- `completed_tool_execution_ids`, `step_count`
- `pending_action_plan_id`, `pending_approval_id`
- `warnings`, `errors`, `degraded_components`

日志全文、知识正文和工具大结果存数据库/对象存储，State 中只放 ID 和安全摘要，防止检查点膨胀。

## 5. Hypothesis 与 Evidence

Hypothesis 至少记录：

- `cause_code`, `summary`, `status`。
- 初始依据和适用条件。
- 需要验证的观测及建议工具。
- 支持证据、反对证据和未解决矛盾。
- 结论等级与终止原因。

Evidence 类型：

- `KNOWLEDGE`：官方文档/Runbook 引用，只说明一般规律。
- `OBSERVATION`：从目标系统读取的当前状态，是确认根因的主要依据。
- `USER_INPUT`：用户提供或确认的信息。
- `ACTION_RESULT`：工具执行返回。
- `VERIFICATION`：处置后恢复证据。

每条 Evidence 保存来源类型、来源 ID、时间、内容哈希、安全摘要、可见范围、支持/反对关系和是否过期。知识证据不能冒充运行时观测。

## 6. 工具契约与风险级别

| 级别 | 含义 | 示例 | Agent 行为 |
|---|---|---|---|
| `READ_ONLY` | 无副作用的受控查询 | 查角色、任务、健康、脱敏日志 | 授权通过后可调用 |
| `LOW_RISK_WRITE` | 可回退、范围小的业务写入 | 建单、添加备注、标记处理中 | 可按策略执行并审计 |
| `APPROVAL_REQUIRED` | 对目标系统产生可见副作用 | 重跑报表、重试导出 | interrupt 后由授权人批准 |
| `FORBIDDEN` | 首版永不自动执行 | 改凭据、授管理员、任意 SQL/Shell、删资产 | 不注册为模型可用工具 |

ToolExecution 保存：工具/Schema 版本、服务端注入的授权范围、请求安全摘要、响应安全摘要、错误类型、开始/结束时间、重试次数、幂等键和关联审计事件。

## 7. ActionPlan、Approval 与 Verification

ActionPlan 必须包括：

- 动作类型和精确资源范围。
- 当前证据、预期效果、风险等级和可逆性。
- 执行前置条件、超时和验证方法。
- 是否需要审批及所需角色。

Approval 绑定动作内容哈希和版本；动作内容改变后旧批准失效。批准不能转授权给其他资源，也不能无限期有效。

Verification 分开保存：

- 系统观测是否恢复。
- 用户是否确认。
- 验证时间和使用工具。
- `PASSED`、`FAILED`、`PARTIAL`、`INCONCLUSIVE`。

接口返回 2xx 只代表动作被接收，不自动代表 `PASSED`。

## 8. 工单与运行状态约束

允许状态转换由确定性状态机管理，例如：

```text
OPEN → DIAGNOSING → WAITING_USER → DIAGNOSING
                  → WAITING_APPROVAL → RESOLVING → VERIFYING
                  → ESCALATED
VERIFYING → RESOLVED → CLOSED
VERIFYING → DIAGNOSING / ESCALATED
```

模型只能建议下一状态；服务端验证当前状态、角色和前置条件。历史状态不覆盖，通过 AuditEvent 记录。

## 9. 知识、来源与向量

KnowledgeDocument 至少保存：

- 标题、来源 URL/对象键、来源类型和目标系统版本。
- 发布者、许可证/使用说明、访问时间和内容哈希。
- 采集方式、解析版本、有效时间和可见范围。
- `OFFICIAL_DOC`、`OFFICIAL_REPOSITORY`、`PUBLIC_ISSUE`、`INTERNAL_RUNBOOK`、`SYNTHETIC` 标记。

KnowledgeChunk 保存定位、正文安全快照、1024 维向量、Embedding 版本和检索元数据。不同 Embedding 空间不能混用；更新文档产生新版本，不静默覆盖历史引用。

## 10. FaultScenario 真值结构

建议字段：

- `id`, `category`, `target_system_version`
- `preconditions`, `seed_state`
- `injection_method`, `reset_method`, `safety_scope`
- `user_symptom_variants`
- `expected_root_cause_code`
- `required_observations`, `required_tool_groups`
- `forbidden_tools`, `allowed_actions`, `approval_required`
- `expected_verification`
- `difficulty`, `distractors`, `dataset_split`

注入和重置必须是受控白名单操作，由测试夹具执行，不开放给普通 Agent 工具。

## 11. 范围与数据隔离

即使求职版只使用一个演示组织，也必须：

- 业务表保留 `organization_id`。
- 工单和工具查询绑定 `target_system_id`、用户和资源范围。
- Repository/Service 层从认证上下文注入过滤，忽略模型企图传入的越权组织 ID。
- 向量检索先按组织、来源可见性、目标系统和版本过滤。
- 对象键包含组织/工单层级，但权限不能只依赖路径。
- 用两个演示组织/两个用户做隔离测试，不需要实现完整租户计费。

## 12. 幂等、版本和并发

- 创建工单：`source_event_id` 或确定性去重键。
- 图节点写入：`diagnostic_run_id + node + semantic_step/version`。
- 工具写动作：`support_case_id + action_plan_hash + attempt_policy`。
- 审批：唯一动作版本 + 审批角色，重复提交返回已有结果。
- 关闭工单：要求最新 Verification 已通过并使用乐观锁/版本号。

Prompt、Schema、工具、知识、模型、故障场景、评测数据和代码提交都要记录版本。并发冲突必须显式返回，不能最后写入者静默覆盖人工决定。

## 13. 日志与保留

- 普通日志不保存 API Key、密码、Cookie、完整连接串或完整敏感附件。
- 目标系统日志进入证据前先脱敏并限制长度；原始样本放受控对象存储。
- 不保存隐藏思维链，只保存用户可理解的理由、结构化假设和证据关系。
- 删除演示数据前设计引用与对象清理并测试；不得对 D 盘或工作区根目录做递归删除。
