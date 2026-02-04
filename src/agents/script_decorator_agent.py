"""
ScriptDecoratorAgent: SOTA 2.0 Phase B 交互脚本装饰器

核心职责：
1. 扫描 Markdown 内容，识别可添加交互的元素
2. 注入 :::script {json} 块，定义交互行为
3. 确保所有交互契约与 components.json 对齐

交互类型：
- 图片交互：缩放、切换、对比
- 段落联动：高亮、折叠、引用跳转
- 全局状态：难度切换、主题切换
- 侧边栏：弹出说明、术语定义

执行时机：
- 在 Writer 完成创作后、HTML 转换前执行
"""

import re
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState


# ============================================================================
# 交互组件定义 (components.json 的内存表示)
# ============================================================================

AVAILABLE_CONTROLLERS = {
    "image-zoom": {
        "description": "图片点击放大查看",
        "applicable_to": ["figure", "img"],
        "params": {
            "zoom_level": {"type": "number", "default": 2.0, "min": 1.5, "max": 4.0},
            "transition": {"type": "string", "default": "ease-out", "enum": ["ease", "ease-in", "ease-out", "linear"]}
        }
    },
    "image-compare": {
        "description": "图片对比滑块（前后对比）",
        "applicable_to": ["figure"],
        "params": {
            "before_label": {"type": "string", "default": "Before"},
            "after_label": {"type": "string", "default": "After"},
            "initial_position": {"type": "number", "default": 50, "min": 0, "max": 100}
        }
    },
    "image-gallery": {
        "description": "图片画廊（多图切换）",
        "applicable_to": ["figure"],
        "params": {
            "autoplay": {"type": "boolean", "default": False},
            "interval": {"type": "number", "default": 3000},
            "show_dots": {"type": "boolean", "default": True}
        }
    },
    "tooltip": {
        "description": "悬停提示框",
        "applicable_to": ["span", "abbr", "term"],
        "params": {
            "content": {"type": "string", "required": True},
            "position": {"type": "string", "default": "top", "enum": ["top", "bottom", "left", "right"]}
        }
    },
    "collapsible": {
        "description": "可折叠内容块",
        "applicable_to": ["section", "div", "details"],
        "params": {
            "default_open": {"type": "boolean", "default": False},
            "animation": {"type": "boolean", "default": True}
        }
    },
    "highlight-link": {
        "description": "点击高亮关联段落",
        "applicable_to": ["span", "a"],
        "params": {
            "target_id": {"type": "string", "required": True},
            "highlight_color": {"type": "string", "default": "#fff3cd"},
            "duration": {"type": "number", "default": 2000}
        }
    },
    "difficulty-toggle": {
        "description": "内容难度切换（简单/详细）",
        "applicable_to": ["section", "article"],
        "params": {
            "levels": {"type": "array", "default": ["basic", "advanced"]},
            "default_level": {"type": "string", "default": "basic"}
        }
    },
    "sidebar-popup": {
        "description": "侧边栏弹出面板",
        "applicable_to": ["span", "button"],
        "params": {
            "title": {"type": "string", "required": True},
            "content": {"type": "string", "required": True},
            "position": {"type": "string", "default": "right", "enum": ["left", "right"]}
        }
    },
    "equation-stepper": {
        "description": "公式推导步进器",
        "applicable_to": ["div", "section"],
        "params": {
            "steps": {"type": "array", "required": True},
            "show_all_button": {"type": "boolean", "default": True}
        }
    },
    "quiz-check": {
        "description": "内嵌小测验/自检",
        "applicable_to": ["div", "section"],
        "params": {
            "question": {"type": "string", "required": True},
            "options": {"type": "array", "required": True},
            "correct_index": {"type": "number", "required": True},
            "explanation": {"type": "string"}
        }
    }
}


@dataclass
class ScriptDirective:
    """解析后的 :::script 指令或待注入的指令"""
    controller: str
    target_selector: str
    params: dict = field(default_factory=dict)
    position: tuple[int, int] = (0, 0)  # 在文档中的位置

    def to_markdown(self) -> str:
        """生成 :::script 块"""
        config = {
            "controller": self.controller,
            "target": self.target_selector,
            **self.params
        }
        return f':::script {json.dumps(config, ensure_ascii=False)}\n:::'

    def validate(self) -> tuple[bool, str]:
        """验证指令是否符合组件定义"""
        if self.controller not in AVAILABLE_CONTROLLERS:
            return False, f"未知的 controller: {self.controller}"

        component = AVAILABLE_CONTROLLERS[self.controller]
        schema = component.get("params", {})

        # 检查必填参数
        for param_name, param_def in schema.items():
            if param_def.get("required") and param_name not in self.params:
                return False, f"缺少必填参数: {param_name}"

        # 检查枚举值
        for param_name, value in self.params.items():
            if param_name in schema:
                param_def = schema[param_name]
                if "enum" in param_def and value not in param_def["enum"]:
                    return False, f"参数 {param_name} 的值 '{value}' 不在允许范围内: {param_def['enum']}"

        return True, ""


# ============================================================================
# 提示词
# ============================================================================

SCRIPT_ANALYSIS_PROMPT = """你是一个交互设计专家。分析以下 Markdown 内容，识别可以添加交互增强的元素。

## 可用的交互组件
{components_list}

## Markdown 内容
```markdown
{content}
```

## 任务
1. 识别适合添加交互的元素（图片、术语、公式推导等）
2. 为每个元素推荐合适的交互类型
3. 不要过度添加交互，只在真正有价值的地方添加

## 输出格式
```json
{{
  "suggestions": [
    {{
      "element_description": "元素描述",
      "element_selector": "CSS选择器或ID",
      "controller": "组件名称",
      "params": {{}},
      "reason": "添加原因"
    }}
  ]
}}
```

**注意**：只输出 JSON，不要其他内容。如果没有合适的交互建议，返回空数组。
"""


class ScriptDecoratorAgent:
    """
    交互脚本装饰器 Agent

    负责为 Markdown 内容注入交互脚本指令
    """

    def __init__(
        self,
        client: Optional[GeminiClient] = None,
        skip_analysis: bool = False,
        max_scripts_per_section: int = 5
    ):
        """
        初始化脚本装饰器

        Args:
            client: Gemini API 客户端
            skip_analysis: 跳过 LLM 分析 (用于测试)
            max_scripts_per_section: 每个章节最多添加的脚本数
        """
        self.client = client or GeminiClient()
        self.skip_analysis = skip_analysis
        self.max_scripts_per_section = max_scripts_per_section

    async def run_async(
        self,
        state: AgentState,
        section_content: str,
        namespace: str
    ) -> tuple[AgentState, str]:
        """
        异步执行脚本装饰

        Args:
            state: Agent 状态
            section_content: Markdown 章节内容
            namespace: 章节命名空间

        Returns:
            (更新后的状态, 装饰后的内容)
        """
        print(f"[ScriptDecorator] 分析章节交互需求 (namespace: {namespace})")

        if self.skip_analysis:
            print("  跳过交互分析 (测试模式)")
            return state, section_content

        # 分析内容，获取交互建议
        suggestions = await self._analyze_content(section_content)

        if not suggestions:
            print("  未发现需要添加交互的元素")
            return state, section_content

        print(f"  发现 {len(suggestions)} 个交互建议")

        # 限制数量
        suggestions = suggestions[:self.max_scripts_per_section]

        # 注入脚本指令
        decorated_content = self._inject_scripts(section_content, suggestions, namespace)

        return state, decorated_content

    def run(
        self,
        state: AgentState,
        section_content: str,
        namespace: str
    ) -> tuple[AgentState, str]:
        """同步版本"""
        import asyncio
        try:
            asyncio.get_running_loop()
            # 已在异步上下文中
            return state, section_content  # 简单返回原内容
        except RuntimeError:
            return asyncio.run(self.run_async(state, section_content, namespace))

    async def _analyze_content(self, content: str) -> list[dict]:
        """使用 LLM 分析内容，获取交互建议"""
        # 构建组件列表
        components_list = "\n".join([
            f"- **{name}**: {info['description']} (适用于: {', '.join(info['applicable_to'])})"
            for name, info in AVAILABLE_CONTROLLERS.items()
        ])

        prompt = SCRIPT_ANALYSIS_PROMPT.format(
            components_list=components_list,
            content=content  # Full content - no truncation
        )

        try:
            response = await self.client.generate_async(
                prompt=prompt,
                system_instruction="你是一个交互设计专家。请分析内容并推荐合适的交互增强。",
                temperature=0.3
            )

            if not response.success:
                print(f"  交互分析失败: {response.error}")
                return []

            # 解析 JSON
            json_match = re.search(r'\{[\s\S]*\}', response.text)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("suggestions", [])

        except Exception as e:
            print(f"  交互分析出错: {e}")

        return []

    def _inject_scripts(
        self,
        content: str,
        suggestions: list[dict],
        namespace: str
    ) -> str:
        """将脚本指令注入到内容中"""
        injected = []

        for suggestion in suggestions:
            controller = suggestion.get("controller")
            if controller not in AVAILABLE_CONTROLLERS:
                continue

            # 创建指令
            directive = ScriptDirective(
                controller=controller,
                target_selector=suggestion.get("element_selector", ""),
                params=suggestion.get("params", {})
            )

            # 验证
            is_valid, error = directive.validate()
            if not is_valid:
                print(f"    跳过无效指令 ({controller}): {error}")
                continue

            injected.append(directive)
            print(f"    ✓ 添加 {controller} 交互")

        if not injected:
            return content

        # 在内容末尾添加脚本块
        script_section = "\n\n<!-- 交互脚本定义 -->\n"
        for directive in injected:
            script_section += directive.to_markdown() + "\n"

        return content + script_section

    def parse_existing_scripts(self, content: str) -> list[ScriptDirective]:
        """解析内容中已有的 :::script 块"""
        directives = []
        pattern = r':::script\s*(\{[^}]+\})\s*:::'

        for match in re.finditer(pattern, content):
            try:
                config = json.loads(match.group(1))
                directive = ScriptDirective(
                    controller=config.get("controller", ""),
                    target_selector=config.get("target", ""),
                    params={k: v for k, v in config.items() if k not in ["controller", "target"]},
                    position=(match.start(), match.end())
                )
                directives.append(directive)
            except json.JSONDecodeError:
                continue

        return directives

    def validate_all_scripts(self, content: str) -> tuple[bool, list[str]]:
        """验证内容中所有脚本指令的合法性"""
        directives = self.parse_existing_scripts(content)
        errors = []

        for directive in directives:
            is_valid, error = directive.validate()
            if not is_valid:
                errors.append(f"{directive.controller}: {error}")

        return len(errors) == 0, errors


def get_components_schema() -> dict:
    """获取组件 schema (供前端使用)"""
    return AVAILABLE_CONTROLLERS


def save_components_json(output_path: Path):
    """保存 components.json 文件"""
    output_path.write_text(
        json.dumps(AVAILABLE_CONTROLLERS, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
