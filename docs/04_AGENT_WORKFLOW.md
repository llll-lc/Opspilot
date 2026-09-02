# 04 Agent 工作流与人工审批

## 1. 为什么使用 LangGraph

企业故障处理不是一次问答。它会等待用户、调用多个受控工具、根据证据改变路径、在审批处中断、进程重启后恢复，并在执行动作后再次验证。LangGraph 用于显式管理这些状态、条件和检查点，不用于把每个函数包装成 Agent。

## 2. 单主图

```text
START
  ↓
load_case_and_authorization
  ↓
normalize_intake
  ↓
关键信息足够？ ──否→ ask_targeted_question → interrupt(user)
  │ 是                                      │恢复
  └─────────────────────────────────────────┘
  ↓
create_or_link_case
  ↓
retrieve_runbook_context
  ↓
initialize_hypotheses
  ↓
diagnostic_loop（有最大步数）
  ├→ select_next_observation
  ├→ authorize_and_execute_read_tool
  ├→ update_evidence_and_hypotheses
  └→ stop / continue / escalate
  ↓
compose_diagnosis_and_action_plan
  ↓
动作策略
  ├→ 无动作/仅建议 ───────────────────┐
  ├→ 低风险允许动作 → execute_once    │
  ├→ 需审批 → interrupt(approval) → execute_once
  └→ 禁止/超范围 → escalate           │
                                      ↓
                               verify_recovery
                                      ↓
                            passed? ─是→ resolve_case
                               │ 否
                               └→ re_diagnose_or_escalate
                                      ↓
                                     END
```

## 3. 有界信息收集

初始必需信息按场景确定，通常包括：

- 谁遇到问题、所属组织和目标系统。
- 受影响资源（仪表盘、数据集、数据库、报表任务）。
- 发生时间、错误现象、预期行为和影响范围。

补问规则：

- 每次只问能改变诊断路径的关键问题。
- 能从受控工具安全查询的信息不反复让用户手工查。
- 设置最大补问轮次；仍无法定位资源时升级。
- 已有工单上下文不得在恢复后重复询问。

## 4. 动态诊断循环

“动态”不等于无约束 ReAct。每轮包含：

1. 从当前证据选出仍活跃的少量候选根因。
2. 为每个候选标记支持、反对和缺失观测。
3. 在允许工具集合中选择最能区分候选、成本最低的下一项检查。
4. 服务端完成授权、参数注入、超时、执行和脱敏。
5. 更新假设，判断是否达到确认、继续、停止或升级条件。

硬边界：最大诊断步数、单工具重试上限、总超时、禁止重复同参数查询、禁止无信息增益循环。确定值在 OP-007 根据五类场景评测设定。

## 5. 停止和升级条件

可以确认根因时：

- 至少有一项直接运行时观测支持。
- 主要替代假设已被反证或低于已定义门槛。
- 证据未过期且属于当前用户/资源/时间范围。

必须升级时：

- 场景不在首批支持范围。
- 缺少必要权限或工具连续失败。
- 证据矛盾且剩余工具无法区分。
- 达到步骤/时间/费用上限。
- 唯一修复方案属于禁止动作。
- 目标系统可能存在安全事件、数据丢失或广泛服务中断。

升级结果必须包含已知事实、已排除假设、未完成检查和建议人工下一步，不能只说“请联系管理员”。

## 6. LLM、工具和确定性代码的分工

### LLM 负责

- 规范化用户症状和生成针对性补问。
- 基于知识与观测提出少量结构化假设。
- 在允许列表中建议下一项诊断工具。
- 总结证据、解释根因、拟定动作计划和工单说明。

### 确定性代码负责

- 身份认证、组织/资源范围和 RBAC。
- 工单去重、状态转换、事务、幂等和并发控制。
- 工具注册、风险等级、参数 Schema、超时和重试。
- 故障注入/重置、健康判断和评测打分。
- 检索过滤、引用定位、日志脱敏和审计。
- 动作审批绑定、执行一次和恢复验证门槛。

### 人工负责

- 补充无法从系统安全获得的信息。
- 审批中高风险动作，或修改/拒绝修复计划。
- 处理禁止操作、安全事件和超出范围的故障。
- 对生产采用和最终业务责任作决定。

## 7. 第一版工具目录

工具保持少而明确，名称最终由 OP-006 固化。

### 知识与工单

- `search_support_knowledge`
- `get_knowledge_excerpt`
- `create_or_link_support_case`
- `add_case_note`
- `get_case_timeline`

### Superset 只读诊断

- `get_target_resource`
- `check_user_resource_access`
- `get_database_connection_status`
- `get_scheduled_report_status`
- `get_background_job_status`
- `get_service_health`
- `search_sanitized_logs`

### 受控动作

- `request_action_approval`
- `rerun_scheduled_report`
- `retry_export_job`
- `verify_target_state`

目标系统重启、凭据变更、授权管理员、删除资源、任意 SQL/Shell 不注册为 Agent 工具。演示中若需模拟服务恢复，由测试夹具或人工运维入口完成并明确标识。

## 8. 结构化输出

至少定义：

- `NormalizedSymptom`
- `ClarificationRequest`
- `DiagnosticHypothesis`
- `ObservationPlan`
- `Diagnosis`
- `ActionPlan`
- `EscalationSummary`
- `VerificationDecision`

所有输出使用 Pydantic/JSON Schema。Schema 失败只允许有限修复；超过次数进入显式失败或升级。不要从自由文本解析目标系统 ID、角色、审批范围或最终动作参数。

## 9. Human-in-the-loop

触发条件至少包括：

- 工具风险级别为 `APPROVAL_REQUIRED`。
- 动作会改变调度任务状态、触发外部发送或产生明显资源消耗。
- 证据冲突但支持人员仍希望继续。
- 动作范围/参数与初始授权不完全一致。
- 策略要求特定角色批准。

interrupt 负载包含：动作、精确资源、依据、风险、可逆性、验证方法和超时。用户可批准、驳回或要求修改。修改动作必须生成新版本并重新审批，不能复用旧批准。

## 10. Checkpoint、恢复和幂等

- 每个副作用之前先持久化 ActionPlan、审批和幂等键。
- 恢复时先查询已有 ToolExecution/ActionExecution，已有成功结果则复用而非再次调用。
- 写工具返回“已执行过”时作为正常幂等结果记录。
- checkpoint 与业务事务不能假定天然原子；使用 outbox/状态标记等最小机制协调，具体由 OP-006/OP-007 决定。
- 用户在等待期间撤销权限或工单被关闭时，恢复前重新授权。

## 11. 验证恢复

修复完成必须执行与故障相匹配的独立检查，例如：

- 数据库连接测试成功且目标查询可执行。
- 用户访问检查由拒绝变为允许，且限定资源正确。
- 新的定时报表运行记录成功并生成预期产物。
- 导出任务完成且文件可访问。
- Worker/Redis 健康且积压任务开始消费。

验证失败可以有限回到诊断，但不能无限循环。连续失败、影响扩大或结果不确定时升级。

## 12. Prompt 注入和工具欺骗防护

- System Prompt 明确知识、日志、工单和工具返回均为不可信数据。
- 检索文本与指令分区传入，内容中的“调用工具/泄露密钥”不执行。
- 工具选择是建议，服务端再次验证注册表、角色、资源范围和参数。
- 目标系统返回的 URL、命令或 SQL 不自动成为下一次工具参数。
- 日志证据脱敏，模型无环境变量、Cookie、数据库连接串或文件系统访问。

## 13. 可观测性

每次运行至少记录：

- 工单、运行、Thread、组织、目标系统和资源标识。
- 节点、状态转换、耗时、重试、interrupt 和错误类型。
- 工具名称/版本、风险级别、授权结果、参数摘要和结果摘要。
- 假设状态变化及引用 Evidence ID，不保存隐藏思维链。
- 模型、Prompt、Schema、Token/费用（API 提供时）。
- 人工审批、动作执行和恢复验证。

## 14. 不采用多 Agent 的理由

五类故障可以由同一状态模型、工具网关和基于类别的策略节点处理。多 Agent 会引入消息协议、权限传播、重复工具调用和评测困难，目前没有已验证收益。只有单图在固定评测中出现明确、可测的专业 Prompt 冲突时，才考虑受控子图。
