# llm-wiki-mcp

[**English**](README.md) | [中文](README.zh-CN.md)

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-94%20passing-brightgreen)

一个给 AI agent 用的 MCP server，让 agent 有一个受管理的 wiki，而不是在文件系统里为所欲为。它介于"全权开放"和"只读限制"之间——正式 wiki 的任何写入，都需要经过你的批准。

> 设计理念源自 [Karpathy 的 LLM Wiki 方法论](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)：知识应在 ingest / maintenance 阶段被编译成可持续复用的 wiki，而不是每次 query 时从 raw source 临时综合。[Astro-Han/karpathy-llm-wiki](https://github.com/Astro-Han/karpathy-llm-wiki) 和 [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) 作为工程实现参考。

本项目先通过手工搭建 `~/llm-wiki` 验证工作流，再抽象为 MCP server —— 工具设计来自实际使用，不是纸上谈兵。

---

## 为什么需要它

你用 AI agent 帮自己建知识库。agent 能读、能写。但没有约束的话：

- 它会覆盖你花时间整理的内容。
- 文件散落各处，没有统一结构。
- 它写 `index.md` 但不记日志。
- 改了东西你根本不知道谁改的、改了什么、为什么改。

这个 server 让每次写入都经过一道审查流程。agent 提方案，你审完再批准，wiki 才更新。

---

## 它能做什么

- **候选优先写入** — 正式页面、索引更新和公开导出都是提案。不调用 `apply_candidate` 就不会真正写入。
- **不可变的原始来源** — `raw/` 文件只能创建，不能覆盖。源材料天然受保护。
- **路径安全** — 所有操作限定在 `wiki_root` 内。父目录遍历攻击直接在路径层被拒绝。
- **结构化 lint** — `run_lint` 返回解析后的结果（错误、警告、建议），不是用退出码把 MCP 传输打断。
- **变更日志** — 每次变更记录操作、影响和验证结果，保留期限可配置。
- **搜索会告诉你下一步做什么** — 正式页面和原始来源分开排序。带作用域的搜索会返回 `next_action` 提示（`read_page` 还是 `read_raw_source`）。
- **Frontmatter 校验** — 未知字段、空目录列表、非法保留值在到达 wiki 之前就被拦下。

---

## 工作流

![LLM Wiki MCP workflow example](docs/assets/llm-wiki-exc.png)

```text
添加 / 修订原始来源
        ↓
compile_page 或 create_update_candidate
        ↓
审查 Candidate 包（页面、索引、公开草稿、日志、来源清单）
        ↓
显式批准后调用 apply_candidate
        ↓
run_lint
```

使用这个 server 的 agent 会先返回持久化的 **Candidate 包**。你（或 agent 的人工介入环节）审查完整的变更集，然后才会触及正式 wiki。

---

## 快速开始

```bash
git clone https://github.com/jaronlu/llm-wiki-mcp.git
cd llm-wiki-mcp
uv sync --dev
cp config/examples.config.yaml config/config.yaml
uv run llm-wiki-mcp
```

编辑 `config/config.yaml` 适配你的机器。保持本地、不被跟踪。

```yaml
wiki_root: ~/llm-wiki
allow_write_raw: false
allow_write_formal: false
allow_update_index: false
allow_modify_schema: false
log_retention_entries: 120
formal_dirs: [domains, entities]
raw_dirs: [raw]
workshop_dirs: [workshop]
non_formal_dirs: [drafts, reading]
```

`workshop_dirs` 用于启用项目包：项目根 `README.md` 是正式 entity
页面，项目内 `raw/` 保存原始项目证据。

```text
llm-wiki/
├── workshop/
│   ├── agentic-rag-securities/
│   │   ├── README.md
│   │   └── raw/
│   └── wiki-mcp/
│       ├── README.md
│       └── raw/
├── domains/
├── entities/
└── raw/
```

---

## MCP 工具

| 工具 | 功能 |
|------|------|
| `init_wiki` | 创建或补全 wiki 根目录结构 |
| `inspect_wiki` | 检查目录是否为有效 wiki 并报告状态 |
| `search_wiki` | 跨正式页面和原始来源的作用域感知搜索 |
| `read_page` | 读取正式页面（含 frontmatter 解析和链接分析） |
| `read_raw_source` | 读取原始来源文件（不可变视图） |
| `create_raw_source` | 创建新的原始来源（仅创建，不可覆盖） |
| `append_log` | 追加一条结构化的变更日志条目 |
| `compile_page` | 从原始来源构建候选正式页面 |
| `create_update_candidate` | 构建候选索引更新 |
| `apply_candidate` | 应用之前已审查的候选包 |
| `run_lint` | 运行结构化 lint 检查并返回解析结果 |
| `knowledge_health_review` | 审查 wiki 健康状况（覆盖率、孤立页面、过期内容） |
| `write_public_draft` | 创建面向公众的草稿（候选优先） |
| `validate_public_safety` | 检查公开导出是否泄露敏感内容 |

变更类工具默认保守。原始写入需要 `allow_write_raw: true`；应用候选需要 `allow_write_formal: true`。

---

## 配置

配置加载顺序：

1. 内置默认值。
2. 项目本地 `config/config.yaml`（存在时）。

Server 有意忽略 MCP host 的配置路径环境变量和根目录覆盖环境变量，运行时唯一数据源始终是仓库本地的配置文件。

配置校验拒绝未知顶级字段、嵌套目录名称、空目录列表和非正数 `log_retention_entries` 值。

---

## 安全边界

- 所有路径必须在 `wiki_root` 下解析。
- 未提供显式 `root` 参数时，`init_wiki` 默认创建或补全 `wiki_root`。
- `raw/` 写入仅可创建，不可覆盖现有文件。
- 正式页面写入需要 `allow_write_formal: true`；`index.md` 更新、迁移和公开导出均采用候选优先。
- `.llm-wiki/source-manifest.json` 跟踪原始来源摘要，但不修改页面 frontmatter。
- `run_lint` 返回结构化 lint 数据，不会因为 lint 失败而中断 MCP 传输。

---

## MCP Host 配置

```toml
[mcp_servers.llm_wiki]
command = "uv"
args = ["--directory", "/path/to/llm-wiki-mcp", "run", "llm-wiki-mcp"]
startup_timeout_sec = 120
```

Server 始终从 `<repo>/config/config.yaml` 读取配置；不需要 MCP host 环境变量。

---

## 开发

```bash
uv run ruff check .
uv run pytest
```

## 贡献

参见 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发设置和设计规则。

## 许可证

MIT — 详见 [LICENSE](LICENSE)。
