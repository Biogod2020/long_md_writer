# SVG 视觉模块：计划、几何预检与可审计复核

## 目标与边界

SVG 由写作 agent 直接绘制；本模块只做确定性安全检查、真实几何预检、受控资产登记
和复核证据留存。它不调用模型、不自动修图，也不把结构分数当作语义或审美判断。
视觉事实仍只落在三个规范记录中：`project.json` 的 `visual_contract`，以及
`assets/manifest.json` 的资产、预检和复核收据。

```text
plan -> draw/check -> submit -> geometry preflight -> inspect PNG -> record review -> cite SVG
```

## 数据契约

每个 `visual_contract.figures[]` 项必须有安全的 `id`、`section_id`、`kind`、`purpose`
和 `required_labels`；`review_required` 默认是 `true`。`svg_submit` 将 SVG 绑定到该
计划和章节。一个计划可以有一条追加式候选修订链：首次候选不带后继字段，修正失败图时
须提供 `supersedes_asset_id`。最终只接受链尾 SVG，旧候选不能继续被正文引用。

`svg_preflight` 将 SVG 渲染为已登记的 `assets/reviews/preview-*.png`，并在 manifest
追加与 SVG/PNG SHA-256 双向绑定的 `visual_preflights` 收据。macOS 上文字边界通过
CoreText 实测；无法获得实测时会明确标为 approximate，不能通过最终视觉验收。随后必须
检查该 PNG 并调用 `svg_record_review`；通过复核需确认全部 `required_labels`。

## 模块职责

| 位置 | 职责 |
| --- | --- |
| `svg/core.js` | 独立 SVG 安全、结构和基线分数 |
| `svg/metrics.js`, `coretext-metrics.swift` | 本机 CoreText 字体度量，显式近似回退 |
| `svg/preflight.js` | 裁切、文字重叠、字体大小、对比度、基本形状重叠、标签检查 |
| `svg/renderer.js`, `workflow.js` | PNG 渲染、保留预览与哈希绑定收据 |
| `svg/submit.js`, `svg/index.js` | 受控提交与薄 DSH 工具适配；均不调用模型 |
| `python/validate_publication.py` | 最终验证计划、正文、SVG、预检和复核是否一致 |

## 使用

DSH 中依次调用 `plan_visuals`、`svg_check`、`svg_submit`、`svg_preflight`；使用
`read_image` 检查返回的 `preview_asset_path` 后，调用 `svg_record_review`，最后才在
计划章节中引用 `assets/svg/<id>.svg`。

CLI 提供相同闭环：

```bash
node dsh-native/svg/cli.js plan --workspace WORKSPACE --contract visual-contract.json
node dsh-native/svg/cli.js submit --workspace WORKSPACE --file figure.svg --visual-plan-id figure-1 --used-in intro --caption "..." --alt-text "..."
node dsh-native/svg/cli.js preflight --workspace WORKSPACE --asset-id figure-1
node dsh-native/svg/cli.js review --workspace WORKSPACE --asset-id figure-1 --preflight-id preflight-... --reviewer reviewer-1 --verdict pass --summary "..." --checked-label "Required label"
```

所有资产和收据都只能经域存储追加；不得手写 manifest、覆盖 SVG 或 PNG、伪造哈希，或
把非当前候选写进正文。

## 验证

```bash
cd dsh-native
pnpm run check:imports
pnpm run test:dsh-contract
pnpm test
```
