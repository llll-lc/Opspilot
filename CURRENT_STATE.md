# CURRENT_STATE

更新时间：2026-09-02

## 当前阶段

`OP-001 风险闸门完成，准备进入 OP-002 仓库脚手架`

当前仓库只包含规格、ADR、可删除兼容性 spike 和 OP-001 交接；尚未开发正式工单、知识、Agent 图、工具网关、故障场景或业务 UI。

## 已完成

- 已完成规格—官方事实—本机现实冲突审计，并初始化本地 `main` Git 仓库；无 remote、不 push。
- 已实测 Windows/WSL2/Docker/Git/Python/Node/PyCharm、CPU/内存/磁盘、端口和用户现有 Docker 资源。
- 已固定 Python 3.12；本机 `py` 默认 3.13 不作为项目解释器。
- 已验证 BGE-M3 与 BGE-Reranker-Large 的文件、真实 CPU 推理、单独/组合加载、延迟和峰值内存；组合峰值约 4.84 GiB。
- 已定位 Windows SentencePiece 原生崩溃，并建立 fast tokenizer JSON + 非 mmap 的可复现 spike；正式 Linux 镜像仍需回归。
- 已验证 pgvector 0.8.6 的 `vector(1024)`。
- 已固定 Superset 6.1.0 spike；`target-light` 与 `target-reports` 的 Web/API、种子、OpenAPI、Redis、单 worker/beat、健康和资源均有证据。
- 已接受 ADR-002：FastAPI + 开源 LangGraph PostgreSQL persistence；删除 Agent Server 生产路径与 Agent Redis。
- 已删除首版 MinIO，Reranker 定为按需/可选；OpsPilot 与 Superset 使用独立数据库容器/卷边界。
- 已选择官方 Agent Chat UI 固定 commit 作为组件基线；格式、lint 和生产构建通过，已记录上游 warnings 与认证边界。
- 已接受 CR-002：最终一个 OpsPilot 应用镜像/容器，其他基础设施/目标服务由一个 Compose 入口分容器编排。
- OP-001 临时容器、网络和测试卷已清理；用户原有 medical-rag 停止容器未修改。

## 尚未完成

- DeepSeek 普通对话、JSON 和工具调用成功路径尚未实测：本地 `.env` 没有 Key；真实 401、超时和错误映射已通过。
- 尚未创建正式后端/前端代码结构、依赖锁、迁移或 CI 门禁。
- 尚未实现 Superset 故障场景、知识库、工单、工具网关、Agent 图、审批或评测。
- 尚未构建最终 OpsPilot 应用镜像；该实现属于 OP-011，不得提前。

## 下一任务

`OP-002：仓库脚手架与前端基线`

执行前先创建/补全 `tasks/OP-002.md`，并读取 `handoffs/OP-001.md`。OP-002 只负责正式仓库结构、配置、前后端基线与质量门禁。

## 当前阻塞与外部事项

- OP-001 本身无阻塞。
- 在 OP-007 前，项目所有者需把 `.env.example` 复制为未提交 `.env`，本地填写 DeepSeek Key，再运行兼容探针；不要通过聊天发送 Key。
- Docker 当前分配约 6.70 GiB，项目所有者表示后续可增加；即使增加，profiles 与按需模型策略仍保留。

## 新会话启动语句

```text
继续开发 D:\Agent\OpsPilot。先完整读取 AGENTS.md、PROJECT_CONTEXT.md、CURRENT_STATE.md、TASKS.md、tasks/OP-002.md 和 handoffs/OP-001.md，检查 Git 与实际文件。本会话只执行 OP-002，不提前实现后续任务。
```
