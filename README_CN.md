# Magnum Opus

一个以 **OpenAI Agents SDK 负责委派、Codex负责工作区执行、Python负责可信控制**
的长文出版系统。

## 核心架构

```text
plan -> draft -> assets -> publish -> qa
```

- Agents SDK：只负责把边界明确的任务交给Codex。
- Codex：规划、写作、资产处理、发布、审计、修复和验证。
- Python控制面：状态、锁、人工审批、文件权限、工作区隔离、原子提升、
  Playwright证据、确定性质量门和旧版本无回归比较。

Codex不会直接写入正式workspace。每个任务在一次性临时工作区中执行，只有通过
文件系统审计和质量门的产物才会被提升到正式目录。模型声称“完成”不等于通过。

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
```

配置 `OPENAI_API_KEY` 或 `CODEX_API_KEY`。

## 运行

```bash
python main.py \
  --input inputs/prompt.txt \
  --reference inputs/source.md \
  --assets-dir inputs/assets \
  --mode html \
  --auto-approve
```

仅生成Markdown：

```bash
python main_markdown.py --intent "撰写一份严谨的技术教程" --auto-approve
```

与旧实验比较：

```bash
python main.py \
  --input inputs/prompt.txt \
  --baseline-workspace workspace/v18_comprehensive_run \
  --auto-approve
```

独立验证：

```bash
python -m src.orchestration.validate_cli \
  --workspace workspace/my-job \
  --stage qa \
  --mode html \
  --json
```

详细说明见 [架构](docs/ARCHITECTURE.md)、[安全边界](docs/SECURITY.md) 和
[迁移说明](docs/MIGRATION.md)。
