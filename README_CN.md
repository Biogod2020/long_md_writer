# LongMDWriter (Magnum Opus)

一个以 **DeepSeek Harness (DSH) 插件**形式运行的受限长文出版系统。
当前仓库只保留一条实现：`dsh-native/`。

## 它是什么

DSH 原生的出版循环。DSH 负责会话历史、事件持久化、上下文压缩、崩溃恢复、
工具执行、Goal 续跑和子代理生命周期；本插件只负责出版领域的策略与三个
正式工作区文件：

```text
project.json          结构真相（目标、章节、质量契约）
article.md            唯一正式手稿
assets/manifest.json  资产溯源真相
```

循环方式：一个持久的 root Session + 一个已武装的 Goal。每个自动 Goal 轮次
通过 `commit_chunk` / `revise_chunk` 最多原子提交一个章节块。
`finalize_publication` 只有在确定性验证 + 全新独立评审都通过后才完成 Goal——
模型无法自证完成。

当前里程碑：**M1 — 仅 Markdown**。搜图与视觉评审规划在 M2/M3
（见 `docs/DSH_NATIVE_ARCHITECTURE.md`）。

## 快速开始

锁定 DSH `0.1.0-rc.6`。请先读 `dsh-native/README.md` 和
`dsh-native/DSH_COMPATIBILITY.md`：

```bash
npm install --global @deepseek-ai/dsh@0.1.0-rc.6
cd long_md_writer
dsh plugin --profile web add ./dsh-native
dsh --profile web --dump-config
dsh --profile web
```

在 Web 会话中打开出版工作区，请 root agent 创建出版任务。它会调用
`initialize_publication`，随后 Goal Round Driver 自动续轮，直到
`finalize_publication` 验证完成。

目录结构：

```text
dsh-native/
├── index.js                     # 领域工具定义与策略
├── lib/
│   ├── project-store.js         # 带防注入的原子章节块存储
│   ├── validator-runner.js      # 调用 Python 验证器的子进程桥
│   └── dsh-compat.js            # 唯一耦合 DSH 的适配层
├── python/validate_publication.py  # 确定性验收权威
├── test/                        # 领域与插件契约测试
├── cordis.patch.yml             # profile 组合（会话命名空间、压缩）
└── examples/project.example.json
```

## 验证

```bash
cd dsh-native
node --test test/project-store.test.js
python3 -m unittest discover -s test -p 'test_validator.py'
```

CI（`.github/workflows/dsh-native.yml`）会安装锁定版本的 DSH、把本插件组合进一个
真实的 DSH Web profile 并启动 Web 服务。

## 历史与对比基准

Codex 时代实现（`src/orchestration/`，OpenAI Agents SDK + Codex 五阶段流水线）
以及更早的 LangGraph 多 Agent 实现，均已从工作树移除，保留在 Git 历史中。

**本仓库的所有对比一律以引入 Codex 之前（LangGraph 时代）的版本为基准**，
即"DSH vs Codex 之前"。

保留并受保护的材料：

- `inputs/` — 出版源材料
- `assets/` — 出版素材库
- `conductor/` — 历史开发记录（只读存档）