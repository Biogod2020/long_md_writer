# SVG 视觉模块：计划、几何预检与可审计复核

SVG 由写作 Agent 直接绘制；LongWriter Core 只做确定性安全检查、真实几何预检、受控
资产登记和复核证据留存。它不调用模型、不自动修图，也不把结构分数当成语义或审美判断。

```text
plan -> draw/check -> submit -> geometry preflight -> inspect PNG -> record review -> cite SVG
```

每个 `visual_contract.figures[]` 项必须有 `id`、`section_id`、`kind`、`purpose` 和
`required_labels`。`svg_submit` 将候选 SVG 绑定到计划和章节；修订已有候选时必须通过
`supersedes_asset_id` 形成单后继链。`svg_preflight` 保留
`assets/reviews/preview-*.png` 并把 SVG/PNG 哈希写入 manifest。macOS 使用 CoreText
实测文字边界；近似度量不能通过最终视觉验收。检查 PNG 后，必须调用
`svg_record_review` 并确认全部必需标签。

实现位于 `packages/core/src/svg/`，最终一致性检查位于
`packages/core/python/validate_publication.py`。DSH 仅在 `adapters/dsh/svg/` 提供薄工具映射。

CLI 与 MCP 都调用同一 Core。CLI 示例：

```bash
longwriter plan-visuals --workspace WORKSPACE --contract visual-contract.json --expected-revision N
longwriter svg-submit --workspace WORKSPACE --file figure.svg --visual-plan-id figure-1 \
  --used-in intro --caption "..." --alt-text "..." --expected-revision N
longwriter svg-preflight --workspace WORKSPACE --asset-id figure-1 --expected-revision N
longwriter svg-review --workspace WORKSPACE --input visual-review.json --expected-revision N
```

所有资产和收据只能经 Core 追加；不得手写 manifest、覆盖受保护资产、伪造哈希，或把非
当前候选写进正文。
