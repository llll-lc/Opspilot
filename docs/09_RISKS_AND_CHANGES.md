# 09 风险与需求变更

## 1. 风险登记表

| ID | 风险 | 概率 | 影响 | 当前措施 | 责任任务 |
|---|---:|---:|---:|---|---|
| R-001 | Superset 完整栈 + 本地模型超过 13.9 GB 可见内存 | 高 | 高 | OP-001 实测；profile 分离；CPU 并发 1；按需 Reranker | OP-001/OP-011 |
| R-002 | Windows/Docker Desktop 下 Superset Compose 不稳定 | 高 | 高 | 固定版本；WSL2/Linux 容器 spike；保留受控 fixture 回退 | OP-001/OP-003 |
| R-003 | 先做 RAG/聊天导致伪 Agent | 高 | 高 | OP-003 先做故障注入、断言和真值；动态工具轨迹硬验收 | OP-003/OP-007 |
| R-004 | Agent Server 自托管/许可/资源不适配 | 中 | 高 | OP-001 核验；FastAPI + LangGraph persistence 回退 | OP-001 |
| R-005 | DeepSeek 结构化输出或工具调用不稳定 | 中 | 高 | 兼容测试、Schema 校验、有限修复、安全升级 | OP-001/OP-007 |
| R-006 | BGE-M3 与 Reranker 同时加载过重 | 高 | 中 | 单实例；候选集小；按需加载；以收益决定保留 | OP-001/OP-005 |
| R-007 | Agent 与 Superset 的 Redis/Celery 职责混淆 | 中 | 高 | 命名/网络/配置隔离；Agent 首版不自建 Celery | OP-001/OP-002 |
| R-008 | Agent 获得 Docker/元数据库危险权限 | 中 | 极高 | Docker Socket 禁止；公开 API + 只读探针；测试控制面隔离 | OP-003/OP-006 |
| R-009 | 故障注入不稳定，评测污染 | 中 | 高 | 注入前后断言；重置失败即停止；场景连续三次验证 | OP-003/OP-009 |
| R-010 | 知识库规模小或版本过时 | 中 | 中 | 高质量官方来源；版本/哈希；运行时证据为主 | OP-005 |
| R-011 | 公开 issue 被错误当作事实真值 | 中 | 高 | issue 只作症状线索；真值来自受控注入 | OP-003/OP-005 |
| R-012 | 工具越权或审批流仅有 UI | 中 | 极高 | 服务端策略；真实 interrupt/checkpoint；安全回归 | OP-006/OP-007 |
| R-013 | 恢复产生重复工单/动作 | 中 | 高 | 幂等键、唯一约束、执行前查询和重放测试 | OP-006/OP-010 |
| R-014 | 五类场景同时开发导致周期失控 | 高 | 高 | Gate A 先三类/五场景；闭环稳定后扩展五类 | OP-003/OP-009 |
| R-015 | 教程前端与当前 SDK 不兼容 | 中 | 中 | 比较上游与教程 fork，锁定最小基线 | OP-001/OP-002 |
| R-016 | 第三方代码/文档许可证或商标表述不当 | 中 | 高 | 来源 manifest；保留 LICENSE/NOTICE；非官方声明 | OP-005/OP-012 |
| R-017 | 项目宣传大于真实能力 | 中 | 高 | POC/合成标识；逐例评测；不编造 ROI/客户 | OP-009/OP-012 |
| R-018 | 新会话重复操作或文档漂移 | 中 | 中 | 权威顺序、任务 ID、预检、Git、交接证据 | 全程 |
| R-019 | 项目所有者无法复盘代码 | 中 | 高 | 每阶段学习交付、演示实操、面试问答 | 全程/OP-012 |
| R-020 | 密钥、Cookie 或真实敏感数据进入 Git | 低 | 极高 | `.env`、脱敏、提交扫描、仅合成用户 | 全程 |
| R-021 | Windows 原生 tokenizer/大权重加载路径崩溃 | 高 | 高 | 使用已核验 fast tokenizer JSON 和非 mmap loader；Linux 镜像重验 | OP-001/OP-002/OP-005 |
| R-022 | 把“一键 Docker 交付”误做成全服务单容器 | 中 | 高 | 单 OpsPilot 应用镜像；数据库/目标系统/队列仍分容器并由 Compose 编排 | OP-011 |

## 2. 已接受的方向变更

### CR-001：从 BidPilot 切换到 OpsPilot

- 状态：`ACCEPTED`
- 日期：2026-09-02
- 决定：新建 `D:\Agent\OpsPilot`，不覆盖或修改 `D:\Agent\BidPilot`。
- 新方向：企业软件智能故障诊断与工单闭环 Agent，首个领域聚焦 BI/数据平台支持。
- 目标系统：Apache Superset 作为真实适配对象和故障实验环境，不进入项目名称。
- 理由：更直接展示 Agent 的动态工具调用、权限、审批、恢复和轨迹评测；公开目标系统缓解私有知识/环境难获取问题。
- 代价：需要处理 Superset/Windows/资源兼容，必须防止项目退化为 FAQ RAG 或固定脚本。
- 隔离：BidPilot 保持原 Git 历史和内容，两个仓库不复制业务代码或混用任务编号。

### CR-002：最终 Docker 交付使用单一 OpsPilot 应用容器

- 状态：`ACCEPTED`
- 日期：2026-09-02
- 决定：最终交付构建一个 OpsPilot 应用镜像并默认运行一个应用容器；FastAPI/LangGraph 提供 API，并服务编译后的前端资产。PostgreSQL/pgvector、Superset、Target Redis/Worker/Beat 继续作为独立容器，由一个 Compose 入口和 profiles 编排。
- 理由：项目所有者要求把本项目环境最终容器化，同时要保留有状态数据、目标系统和队列的职责隔离、独立健康检查及按需启动能力。
- 不采用：不把应用、PostgreSQL、Superset、Redis、Worker 和 Beat 塞进一个多进程全家桶容器；这种做法会破坏 profile、持久化、故障注入和健康边界。
- 任务影响：OP-001 只记录架构与资源结论；OP-011 负责 Dockerfile、Compose、健康检查、一键启动与验收，不在本会话提前实现。
- 回退：若前端无法静态交付且必须保留 SSR，OP-011 必须新增 ADR 说明应用层拆容器的必要性，不能静默偏离单应用容器目标。

## 3. 已确认但分阶段实现的范围

- 最终求职版本覆盖五类故障。
- Gate A 先完成连接、权限、调度三个家族的至少五个确定性场景，其中调度包含两个不同根因。
- 导出与独立服务故障在核心闭环验证后由 OP-009 扩展。
- 这不是删除已确认范围，而是降低资源和开发顺序风险。

## 4. 变更状态

- `PROPOSED`：已提出，未确认，不得实施。
- `ACCEPTED`：项目所有者已确认，需要更新规格和任务。
- `REJECTED`：不实施，保留理由。
- `IMPLEMENTED`：已按任务完成并有证据。
- `SUPERSEDED`：被更新决定替代。

## 5. 变更记录模板

```text
CR-XXX：标题
状态：PROPOSED
提出日期：
动机与当前证据：
建议变化：
不做的后果：
影响的业务/架构/数据/任务：
资源、安全和许可证影响：
验收与回退：
项目所有者决定：
```

## 6. 变更判定

以下属于正式变更，必须登记：

- 改变领域、目标用户、业务闭环或最终五类故障范围。
- 增加新的目标系统、数据库、队列、独立服务、Agent 或外部工单平台。
- 让 Agent 获得新的写操作、主机/容器控制或更高权限。
- 把明确排除项加入求职版。
- 更换 LLM、Embedding、向量数据库或目标 Superset 版本并影响真值。
- 降低安全/评测硬指标或改变用户必须参与事项。

修复 Bug、补测试或同一候选栈内的小版本调整通常不需要 CR，但仍必须在任务范围内并保留实测证据。

## 7. OP-001 冲突审计清单

- DeepSeek 当前官方模型/接口是否与规划兼容。
- Agent Server 当前自托管、许可、Redis/PostgreSQL和自定义路由要求。
- 教程前端、官方 Agent Chat UI、Node/SDK 和许可证冲突。
- Docker Desktop/WSL2、本机端口、磁盘与内存事实。
- Superset 目标版本、公开 OpenAPI、Windows/Compose 限制和轻量启动方式。
- `target-reports` 的 Worker/Beat/Redis/浏览器资源。
- PostgreSQL/pgvector 是否需要与 Superset 元数据库分实例/分库/Schema。
- Agent 是否真正需要 Redis/MinIO；无明确职责则删候选。
- Test-only control plane 是否与 Agent 网络/凭据隔离。
- 文档是否重复状态或把候选技术写成已验证事实。

发现冲突先给证据和最小整改方案，再执行环境或业务开发。
