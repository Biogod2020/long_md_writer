# LongWriter（Magnum Opus）

LongWriter 是一个与具体 Agent 生态无关的长文出版控制内核。它负责文章状态、原子
修改、共享 revision、素材证据、确定性验证和最终验收；不会把产品本体绑定到 DSH、
Claude、Codex 或某个模型 API。

```text
Skill                    教 Agent 如何工作
CLI / MCP                两种通用调用入口
@longwriter/core         真正执行并强制规则
可选 Adapter             对接 DSH 的 Goal、会话与独立子代理
```

目录：

```text
packages/core       核心产品
packages/cli        命令行入口
packages/mcp        MCP stdio 服务
skills/longwriter   跨生态工作流说明
adapters/dsh        可选 DSH 适配层
dsh-native          旧安装路径的兼容壳
```

正文仍以 `project.json`、`article.md`、`assets/manifest.json` 为可读真相源；
`.longwriter/` 只保存 revision、跨进程锁、操作记录、完成状态和独立审稿收据。

```bash
corepack enable
pnpm install --no-frozen-lockfile
pnpm check
pnpm test
```

CLI 与 MCP 调用完全相同的 Core。Skill 只规定工作方法，不承担安全边界。DSH 只负责
会话、Goal 和真正启动隔离 reviewer，不再拥有出版规则。
