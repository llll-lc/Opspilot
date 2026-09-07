# OP-006 Provider 只读联调

`verify_target.py` 只调用固定的 Superset `/health` 与四类只读元数据 list API，并调用本地 `RuntimeProbeProvider`。访问令牌只从当前进程的 `OP006_SUPERSET_ACCESS_TOKEN` 读取，不写入报告或仓库；输出只含 health scope、状态与条目数。

默认不连接 MCP。只有显式提供 `--mcp-url` 和当前进程的 `OP006_MCP_BEARER_TOKEN` 才检查目录；可用 `--expect-mcp-error RESPONSE_TOO_LARGE` 将本地限长拒绝作为必须满足的安全结果。此脚本不会把原生 MCP 目录判为受信，也不改变 OP-003 的 FAIL 结论。

未配置 Worker、Beat、Redis 的独立可信 liveness endpoint 时，Probe 必须返回 `UNKNOWN`，不得从 Web、MCP 或容器进程存在推导运行时健康。

报告调度详情/运行历史没有纳入 OP-006 稳定目录：`target-mcp` profile 未启用该 API，且当前没有经实测确认的稳定只读响应契约。OP-005 的冻结 `scheduled-report-triage` Skill 文件保持不变，但在这些稳定观察工具实现前不可执行为完整闭环。
