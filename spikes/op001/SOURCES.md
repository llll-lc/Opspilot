# OP-001 外部来源与下载清单

访问日期：2026-09-02。

| 来源 | 固定版本 | 许可证/边界 | 下载与用途 |
|---|---|---|---|
| https://github.com/apache/superset | tag `6.1.0`, commit `c83fb2bb1dcfac41ac51bcebd82471f4a7180d18` | Apache-2.0；已核验 LICENSE/NOTICE；OpsPilot 与其无官方隶属关系 | 只拉官方镜像做本地实验，不复制源码进仓库 |
| `apache/superset:6.1.0-dev` | image ID `sha256:07d08f5d...f45b24d8` | 官方开发/测试镜像，不作为生产部署模板 | 766,731,628 bytes；Superset Web/API 与 reports spike |
| https://github.com/pgvector/pgvector | tag `v0.8.6`, commit `8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c` | PostgreSQL License | `pgvector/pgvector:0.8.6-pg17-bookworm`，image ID `sha256:cf134a76...760f8e6f`，157,781,872 bytes |
| `postgres:16-bookworm` | image ID `sha256:bb3e1a57...a78dd825` | PostgreSQL License | 155,131,839 bytes；Superset 6.1 元数据库，运行时 PostgreSQL 16.15 |
| `redis:7.4-alpine` | image ID/digest `sha256:ff02b58f...fe28eadf` | Redis 7.4 镜像许可边界由正式交付再复核 | 已存在本机，16,276,863 bytes；仅供 Superset reports spike |
| https://github.com/langchain-ai/agent-chat-ui | commit `325517352ca3672c8bc0745c4143b2301dd74997` | MIT | 浅克隆 + 固定 lockfile；依赖 635 包；vendor 约 0.728 GiB，pnpm store 约 0.572 GiB |
| https://github.com/rexrex9/agent-chat-ui | commit `021921639e75f3a34a66c5ba6eea17f1921836f5` | MIT | 只做教程 fork 差异审计，不作为默认基线 |
| PyPI/PyTorch CPU 包索引 | `requirements-models.txt` 固定直接依赖 | 各依赖自身许可证，正式锁文件由 OP-002 生成 | OP-001 独立 Python 3.12 虚拟环境；47 包一致性检查通过；用于两模型 CPU 基准 |

下载前已检查：本机没有 Superset/pgvector 镜像、卷或源码副本；现有其他项目容器保持停止且不修改。
