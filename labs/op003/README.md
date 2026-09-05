# OP-003 Superset 故障实验室

这是隔离的本地测试控制面，不是 OpsPilot 应用、Tool Gateway 或 MCP Provider 实现。它只使用固定 `apache/superset:6.1.0-dev` 镜像，所有运行时凭据在未跟踪的 `.runtime/op003.env` 中随机生成；合成场景的权威真值在 [`fault_scenarios.json`](fault_scenarios.json)。

## Profile 与安全边界

- `target-light`：仅 Superset Web/API 和元数据库。
- `target-mcp`：额外启动原生 MCP 服务，仅绑定 `127.0.0.1:5008`。
- `target-reports`：独立的 Target Redis、单 Worker、单 Beat；不能与 `target-light`/`target-mcp` 同时运行，因为 Web 端口相同。
- 故障注入只由本目录的主机测试脚本对名称固定的 `opspilot-op003-*` 容器执行。它不属于应用容器、没有 API 路由、没有 Docker Socket 挂载，也不会被 Agent/Skill 注册。

## 首次运行

```powershell
uv --cache-dir .cache/uv run python labs/op003/prepare_lab.py
docker compose --env-file labs/op003/.runtime/op003.env -f labs/op003/compose.yml --profile target-mcp up -d
```

所有报告必须经由验证脚本生成，报告和 `.runtime/` 不能手改或提交凭据。停止实验时只能操作本文件明确的 Compose 项目：

```powershell
docker compose --env-file labs/op003/.runtime/op003.env -f labs/op003/compose.yml --profile target-mcp down --volumes
```

## 受控响应超限验证

默认响应上限为 256 tokens。要验证上游确实在超限时拒绝只读工具输出，可仅在当前 PowerShell 进程把实验 profile 降为 1 token，再调用 `get_instance_info`；验证器始终先写报告，若未观测到 `isError` 拒绝则以退出码 1 失败。此退出是预期的风险闸门结果，不能被忽略或改成成功。

```powershell
$env:OP003_MCP_RESPONSE_TOKEN_LIMIT = "1"
docker compose --env-file labs/op003/.runtime/op003.env -f labs/op003/compose.yml --profile target-mcp up -d
uv --cache-dir .cache/uv run python labs/op003/verify_mcp_gate.py --response-token-limit 1 --require-size-rejection --report evidence/OP-003_MCP_GATE_YYYY-MM-DD.json
Remove-Item Env:OP003_MCP_RESPONSE_TOKEN_LIMIT
```

## 已知的原生 MCP 风险假设

固定 6.1.0 镜像的 `superset mcp run` CLI 不读取 `MCP_FACTORY_CONFIG` 的 `include_tags`/`exclude_tags`。默认目录含 `execute_sql`、保存、生成、创建和更新工具；因此 OP-003 的验证必须把它判定为 **原生只读闸门未通过**，而不是将这些工具暴露给模型。OP-006 只可在固定稳定工具和双层允许列表下实现 REST/只读 Probe 回退；不能把本实验脚本变成生产 Provider。
