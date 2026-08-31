# SVG 视觉模块：计划、几何预检与可审计复核

## 目标与边界

SVG 的确定性模块只做安全检查、真实几何预检、受控资产登记和复核证据留存；它不调用
模型，也不把结构分数当作语义或审美判断。模型侧生成由同一个 Codex App Server host
编排：根写作线程可以异步委派给临时 SVG 子线程，但所有正式写入仍经过本模块。
视觉事实仍只落在三个规范记录中：`project.json` 的 `visual_contract`，以及
`assets/manifest.json` 的资产、预检和复核收据。

```text
plan -> svg_delegate -> initial SVG -> submit/preflight
                                      failed -> PNG visual diagnosis -> svg_edit feedback
                         revision -> svg_edit(champion by id) -> submit/preflight
                                      passed -> independent acceptance review
                                                       pass -> svg_collect -> cite SVG
```

`svg_delegate` 会立即返回 job id，根线程可以继续研究或写作。每次候选使用一个全新的
临时子线程，避免把上轮失败推理带入下一轮；首版需要为有意义的 group、连接线、图形和文字
提供稳定 DOM `id`。存在冠军版本后，子线程不再拥有“整份 SVG 覆盖”通道，只能调用
`svg_edit`，按元素 id 设置属性、改文字、删除局部元素或追加有界片段。一次调用可包含最多
16 个关联操作；编辑先作用于 host 内存草稿并对完整 SVG 做一次事务式安全检查，任一操作
失败时整个批次回滚、原草稿不变；子线程最后只报告编辑版本号、
caption、alt text 和变更摘要，送审源码由 host 的草稿提供。

SVG 子线程采用 `workspace-write + on-request + auto_review`，对应 Codex 的
“Approve for me”。每次尝试都有独立的 `RUN/svg-workers/<job>/attempt-N/` scratch
目录作为唯一通用可写根；仓库和正式 publication workspace 可以读取，互联网和常规 shell
也可以使用，以便查参考、算几何、找字体和做本地渲染实验。scratch 会保留用于排查，但不属于
正式记录。首稿仍通过结构化返回交给 host；已有冠军的源码修改仍必须像改代码一样经过
`svg_edit`，因此 shell 不能绕过 manifest、资产登记或修订链。策略还显式关闭
`workspaceWrite` 默认附带的 `/tmp` 与 `$TMPDIR` 写入例外。

首稿线程可调用只读 `svg_preflight_candidate`，修订线程可调用只读
`svg_preflight_draft`；两者都运行与正式登记相同的确定性预检，并返回带 `text_id`、
`shape_id`、`left_id`、`right_id` 的有界反馈。每次尝试的预检次数有上限。通用 shell
命令达到配置阈值后，host 使用 App Server `turn/steer` 在同一个活动回合追加交付检查点，
引导子线程停止泛化探索、完成局部编辑与预检；该机制不撤销读取、互联网、shell 或 scratch
写权限。

防震荡使用 champion-challenger 规则：预检通过、已确认标签、科学检查和设计检查一旦通过
就进入锁定账本；破坏任一已通过项的候选不能替换冠军。重复源码哈希会消耗有限尝试次数但
不会再次登记；下一轮的可执行反馈始终绑定当前冠军，不会把被拒候选的临时问题误当成冠军
问题继续追逐。同一失败签名反复出现时，策略切换为在现有 id 元素上做更简单的网格布局，
而不是重画。每个修订 worker 默认最多调用 24 次局部编辑，到达上限后必须交付当前草稿；
一个 job 用尽预算后，后续新 job 仍从已保留冠军继续，但每个视觉计划默认最多三代 job；
三代都失败时显式终止并保留证据，不再自动委派。

确定性预检失败后，host 仍会把该收据绑定的单张 PNG 发送给一个全新的、无工具 Muse
诊断线程。像素诊断的摘要、具体 finding、失败科学项和失败设计项会优先进入下一轮
`svg_edit` 提示，然后才是有界的几何问题。诊断只帮助定位“画面实际哪里难读”，不会写入
manifest 的 `visual_reviews`、不会提高候选验收等级、不会锁定通过项，也不能让失败预检的
图被正文引用。正式放行仍要求确定性预检通过后再进行独立视觉审核。字号反馈中的
`current<minimum` 明确把右侧值解释为 SVG 用户空间的最低字号；修订线程不得靠缩小字号
消除重叠，只能移动/缩放组、精简非必需文字或重排画布。

## 数据契约

每个 `visual_contract.figures[]` 项必须有安全的 `id`、`section_id`、`kind`、`purpose`
和 `required_labels`；`review_required` 默认是 `true`。`svg_submit` 将 SVG 绑定到该
计划和章节。一个计划可以有一条追加式候选修订链：首次候选不带后继字段，修正失败图时
须提供 `supersedes_asset_id`。最终只接受链尾 SVG，旧候选不能继续被正文引用。

schema v2 还要求 `design_brief`：`figure_type`、`publication_width`（单栏或双栏）、
一条可证伪的 `scientific_claim`、逐条 `scientific_checks` 与 `reading_order`。出版宽度不是
备注：预检把它换算为成稿中的 8 pt 最低字号。科学检查必须覆盖图中完整的因果/数据拓扑、
必要输入、方向、符号、单位、阈值或物理源汇守恒，而不能只复述标题。

`svg_preflight` 将 SVG 渲染为已登记的 `assets/reviews/preview-*.png`，并在 manifest
追加与 SVG/PNG SHA-256 双向绑定的 `visual_preflights` 收据。macOS 上文字边界通过
CoreText 实测；除裁切、重叠、对比度和标签外，还检查出版尺度字号、文字数量与最长文本、
字号层级、画布占用/重心，以及连接线进入文字安全区。预检问题会携带短标签文字与图元类型，
而不只给内部索引，便于 agent 精确修订。超过 100 条时会按问题类别优先保留代表性条目，
并附带总数、截断数和类别数；这样 manifest 仍有界，修订 worker 也不会只收到笼统的超限
错误。无法获得实测时会明确标为 approximate，不能通过
最终视觉验收。随后必须用当前 `asset_id` 与 `preflight_id` 调用 `inspect_visual`。host 会在临时线程中只检查这一张
PNG；通过复核需确认全部 `required_labels`，根线程只收到文字与哈希。若审核线程调用任何
shell、文件、网络、MCP、图像查看或子 agent 工具，host 会立即中断并拒绝该回合作为证据，
最多只在新的临时线程重试两次（总计三个独立审核回合）。`fail` 还必须给出至少一条可执行
finding；空问题清单不会写入 manifest。

透明、`display:none`、`visibility:hidden` 或继承隐藏状态的文字不会进入几何与必需标签证据。
数学公式需要跨字体稳定时，可在同一个可见 `<text>` 中用普通 ASCII 字形和 `tspan`
`baseline-shift` 排出上下标，并用 `aria-label` 保存规范公式；只有规范标签与可见文字经
Unicode 兼容归一化后等价时才计入标签。CoreText 还记录实际解析字体和缺失字符：容易让整段
渲染失效的兼容上下标会直接失败并指向元素 id，普通字体回退则作为显式警告交给最终 PNG
审查确认。隐藏精确标签加可见近似文本的做法不再可能通过预检。最终 publication validator
复用同样的继承可见性和排版等价语义，避免通过预检的可见公式在整篇验收时被误判；它同样
不会把隐藏文字计作证据。

## 模块职责

| 位置 | 职责 |
| --- | --- |
| `svg/core.js` | 独立 SVG 安全、结构和基线分数 |
| `svg/metrics.js`, `coretext-metrics.swift` | 本机 CoreText 字体度量、实际字体/缺字证据，显式近似回退 |
| `svg/design.js` | 图类型、出版宽度、设计简报与按图类约束 |
| `svg/preflight.js` | 裁切、文字密度、出版字号、构图平衡、连接线安全距离、对比度、重叠、标签检查 |
| `svg/renderer.js`, `workflow.js` | PNG 渲染、保留预览与哈希绑定收据 |
| `svg/submit.js`, `svg/index.js` | 受控提交与薄 App Server 领域工具适配；均不调用模型 |
| `app-server/svg-draft-editor.js` | 仅对子线程内存草稿执行 id 定位的事务式局部编辑 |
| `app-server/svg-worker-tools.js` | 首稿/草稿专用只读预检、检查预算与有界 id 反馈 |
| `app-server/svg-job-manager.js` | 异步任务、失败候选像素诊断、有限并发/尝试、冠军选择、锁定通过项与恢复 |
| `python/validate_publication.py` | 最终验证计划、正文、SVG、预检和复核是否一致 |

异步池默认同时运行 2 个 SVG 作业；显式配置时可受控提升到 6 个，用于独立图形任务的
并行生成。每个作业仍保持自己的线程、冠军、尝试预算、草稿编辑边界和审核链。

## 使用

常规 Codex App Server 流程调用 `plan_visuals`、`svg_delegate`，在根线程继续其他工作；用
`svg_status` 查看进展，仅在没有独立工作时用 `svg_wait`。job 通过后调用 `svg_collect` 获取
已登记路径。一个计划一旦进入委派链，根线程的直接 `svg_submit` 会被 host 拒绝，不能在 job
通过、运行或耗尽后另开一条资产链。直接 `svg_check` / `svg_submit` / `svg_preflight` 仅保留给
从未委派的简单同步图和委派链之外的显式人工恢复。
无论哪条路径，只有独立单图审查通过后，才在计划章节中引用 `assets/svg/<id>.svg`。

CLI 提供相同闭环：

```bash
node codex-app-server/svg/cli.js plan --workspace WORKSPACE --contract visual-contract.json
node codex-app-server/svg/cli.js submit --workspace WORKSPACE --file figure.svg --visual-plan-id figure-1 --used-in intro --caption "..." --alt-text "..."
node codex-app-server/svg/cli.js preflight --workspace WORKSPACE --asset-id figure-1
node codex-app-server/svg/cli.js review --workspace WORKSPACE --asset-id figure-1 --preflight-id preflight-... --reviewer reviewer-1 --verdict pass --summary "..." --checked-label "Required label"
```

所有资产和收据都只能经域存储追加；不得手写 manifest、覆盖 SVG 或 PNG、伪造哈希，或
把非当前候选写进正文。

## 验证

```bash
cd codex-app-server
pnpm run check:imports
pnpm run test:app-server-contract
pnpm test
pnpm run benchmark:svg-quality -- --out /tmp/longwriter-svg-quality
```

`benchmark:svg-quality` 使用机制图、分阶段数据流程、约束散点图和物理空间循环四类纯合成
图，既验证通用门禁，也保留可供人工或外部视觉审查的 PNG。它是回归集，不替代每次运行
对当前单图的独立审查。
