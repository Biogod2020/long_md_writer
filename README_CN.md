# LongMDWriter

LongMDWriter 是一个由**单一 Codex App Server**承载、可验证的 Markdown 长文
创作系统。Codex 负责持久线程、历史、压缩、澄清、恢复和 Goal；LongMDWriter
只负责受控出版工具和三个正式记录：

```text
project.json
article.md
assets/manifest.json
```

根线程运行在只读 sandbox。模型不能用通用写文件或 shell 修改正式手稿，只能
调用 `commit_chunk`、`revise_chunk` 和受控视觉工具。只有确定性 validator 与
全新、SHA 绑定的独立 reviewer 都通过后，`finalize_publication` 才能完成 Goal。

复杂 SVG 可以异步交给全新的临时子线程，根线程同时继续写作或研究。首版必须带稳定 DOM
id；后续修改只能通过 host 提供的 `svg_edit` 按 id 局部编辑保留的冠军版本，不能重新输出
整份 SVG 覆盖；多个关联修改可以在一个事务批次中一起提交，任一操作无效则整体回滚。
首稿和修订线程各自拥有只读专用预检工具，直接返回精确元素 id 与 CoreText 几何；通用 shell
探索达到有限阈值后，host 会在同一个活动回合中把线程引回编辑、预检与交付，而不会收回读取、
联网或 shell 权限。已通过的标签、科学检查、设计检查和几何预检会被锁定，退步候选不会成为
新基线，重复候选和总尝试次数也都有明确上限。
每个 SVG 子线程可以广泛读取文件、访问互联网并运行常规 shell，审批采用
`on-request + auto_review`（即 Codex 的 “Approve for me”）。通用文件写入仅允许落在
该次尝试独有、可保留检查的 scratch 目录；正式文章、manifest 和资产仍只能由 host
的领域边界修改。
一个计划一旦委派，根线程就不能再用直接 `svg_submit` 另开修订链，只能收集该 job
保留并经审核绑定的冠军版本。
透明、隐藏或移出画布的文字不能满足必需标签。易缺字的数学上下标采用可见 tspan 排版，
并在同一个可见文本元素上提供与画面等价的精确 `aria-label`，兼顾渲染稳定性和可审计性；
最终 publication validator 与 SVG 预检使用相同的可见性和排版等价规则。

## 快速开始

需要 Codex CLI `0.151.0`、Node.js 22+、Python 3.11+、pnpm，以及兼容
Responses API 的 provider 凭据。

```bash
cd codex-app-server
pnpm install --frozen-lockfile
pnpm test

# 可 export IWORLD_API_KEY，也可写入已被 Git 忽略的 codex-app-server/.env。
node cli.js start \
  --run ../runs/my-publication \
  --config config/iworld-muse12.json \
  --task ../runs/my-publication/task.txt
```

中断后恢复同一个线程：

```bash
node cli.js resume --run ../runs/my-publication --config config/iworld-muse12.json
```

每个 run 会保留 `run.json`、`events.jsonl`、隔离的 `.codex-home/` 和正式
workspace。密钥只从环境变量读取，不会写入配置或日志；本地 `.env` 已被 Git
忽略，且不会覆盖调用者已经 export 的变量。

## 工具与输入

- 出版工具：`initialize_publication`、`plan_visuals`、
  `publication_status`、`commit_chunk`、`revise_chunk`、
  `review_publication`、`finalize_publication`；
- 视觉工具：`mermaid_submit`、`svg_check`、`svg_submit`、
  `svg_preflight`、`svg_delegate`、`svg_status`、`svg_wait`、`svg_collect`、
  `image_submit`、`inspect_visual`；
- 搜索：仓库的 `dsh-bing-search/` 服务由 App Server 适配为四个扁平 function
  tools；不再把 Codex 专有 MCP namespace 发送给 iWorld，也不使用 DSH 运行时。

任务已经写明可测合同时，作者会跳过澄清并直接 initialize。只在仍缺用户
选择时问一次。交互式 CLI 把该问题原样交给用户并在同一 turn 继续。非交互
模式若仍被要求澄清会明确失败，不会擅自猜测。

`inspect_visual` 不会把图片字节返回持久根线程。host 会为每张已登记 PNG 启动一个
临时只读 reviewer，只传一张 `localImage`；验证并保存 SHA 绑定的审查收据后，仅向
根线程返回文字 JSON。最终手稿 reviewer 读取这些紧凑视觉报告，不再一次附带全部图片。

可执行 `pnpm run smoke:provider` 验证真实动态工具往返；执行
`pnpm run smoke:resume` 会重启 App Server，并验证同一持久 thread、active Goal
与动态工具注册表均能恢复。两者只发送合成标记，不发送创作材料。

详细设计见 [架构文档](docs/CODEX_APP_SERVER_ARCHITECTURE.md)、
[Mermaid 模块](docs/MERMAID_MODULE.md) 与 [SVG 模块](docs/SVG_MODULE.md)。
