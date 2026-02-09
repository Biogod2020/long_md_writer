"""
SOTA 2.0 本地静态校验器 (Local Static Validators)

无需调用 API，仅靠 Python 本地代码执行的快速检查。
用于在 LLM 输出后立即验证，拦截语法错误和格式问题。

校验器类型：
1. MarkdownStructureValidator - Markdown 指令块校验
2. EmbeddedHTMLValidator - 嵌入式 HTML 标签校验
3. LaTeXBalanceValidator - LaTeX 公式符号平衡校验
4. NamespaceValidator - ID 命名空间校验
"""

import re
import json
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
from html.parser import HTMLParser


class ValidationSeverity(str, Enum):
    """校验问题严重程度"""
    ERROR = "ERROR"      # 必须修复
    WARNING = "WARNING"  # 建议修复
    INFO = "INFO"        # 仅供参考


@dataclass
class ValidationIssue:
    """校验问题"""
    severity: ValidationSeverity
    message: str
    line_number: Optional[int] = None
    column: Optional[int] = None
    context: Optional[str] = None  # 问题上下文 (如相关代码片段)
    suggestion: Optional[str] = None  # 修复建议

    def to_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "message": self.message,
            "line": self.line_number,
            "column": self.column,
            "context": self.context,
            "suggestion": self.suggestion
        }


@dataclass
class ValidationResult:
    """校验结果"""
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    validator_name: str = ""

    def add_error(self, message: str, **kwargs) -> None:
        self.issues.append(ValidationIssue(ValidationSeverity.ERROR, message, **kwargs))
        self.is_valid = False

    def add_warning(self, message: str, **kwargs) -> None:
        self.issues.append(ValidationIssue(ValidationSeverity.WARNING, message, **kwargs))

    def add_info(self, message: str, **kwargs) -> None:
        self.issues.append(ValidationIssue(ValidationSeverity.INFO, message, **kwargs))

    def merge(self, other: "ValidationResult") -> None:
        """合并另一个校验结果"""
        self.issues.extend(other.issues)
        if not other.is_valid:
            self.is_valid = False

    def to_report(self) -> str:
        """生成人类可读的报告"""
        if self.is_valid and not self.issues:
            return f"✅ {self.validator_name}: 校验通过"

        lines = [f"{'❌' if not self.is_valid else '⚠️'} {self.validator_name}:"]

        for issue in self.issues:
            icon = {"ERROR": "🔴", "WARNING": "🟡", "INFO": "🔵"}[issue.severity.value]
            loc = f" (行 {issue.line_number})" if issue.line_number else ""
            lines.append(f"  {icon} {issue.message}{loc}")
            if issue.context:
                lines.append(f"      上下文: {issue.context[:80]}...")
            if issue.suggestion:
                lines.append(f"      建议: {issue.suggestion}")

        return "\n".join(lines)


# ============================================================================
# Markdown 结构校验器
# ============================================================================

class MarkdownStructureValidator:
    """
    Markdown 指令块结构校验器

    检查内容：
    1. `:::` 容器块是否正确闭合
    2. 指令首行的 JSON 配置是否语法正确
    3. 嵌套指令块是否合法
    """

    # 匹配指令开始: :::name 或 :::name {json}
    DIRECTIVE_START_PATTERN = re.compile(r'^(:::)(\w+)(?:\s+(\{.*\}))?$', re.MULTILINE)
    # 匹配指令结束: :::
    DIRECTIVE_END_PATTERN = re.compile(r'^:::$', re.MULTILINE)
    # 匹配带类型的指令: :::visual, :::script, :::important 等
    KNOWN_DIRECTIVES = {"visual", "script", "important", "warning", "note", "tip", "details", "quote"}

    def validate(self, content: str) -> ValidationResult:
        """执行校验"""
        result = ValidationResult(is_valid=True, validator_name="MarkdownStructureValidator")

        lines = content.split("\n")
        directive_stack = []  # 栈: [(directive_name, line_number, json_config)]

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()

            # 检查指令开始
            start_match = self.DIRECTIVE_START_PATTERN.match(stripped)
            if start_match:
                directive_name = start_match.group(2)
                json_config = start_match.group(3)

                # 验证 JSON 配置
                if json_config:
                    try:
                        json.loads(json_config)
                    except json.JSONDecodeError as e:
                        result.add_error(
                            f"指令 :::{directive_name} 的 JSON 配置语法错误: {e.msg}",
                            line_number=line_num,
                            context=stripped,
                            suggestion="检查 JSON 格式：确保引号配对、逗号正确、无多余字符"
                        )

                # 检查未知指令 (警告级别)
                if directive_name not in self.KNOWN_DIRECTIVES:
                    result.add_warning(
                        f"未知指令类型: :::{directive_name}",
                        line_number=line_num,
                        suggestion=f"已知指令: {', '.join(self.KNOWN_DIRECTIVES)}"
                    )

                directive_stack.append((directive_name, line_num, json_config))
                continue

            # 检查指令结束
            if stripped == ":::":
                if not directive_stack:
                    result.add_error(
                        "发现未匹配的指令结束标记 `:::`",
                        line_number=line_num,
                        suggestion="删除多余的 `:::` 或检查是否缺少指令开始"
                    )
                else:
                    directive_stack.pop()

        # 检查未闭合的指令
        for directive_name, start_line, _ in directive_stack:
            result.add_error(
                f"指令 :::{directive_name} 未正确闭合",
                line_number=start_line,
                suggestion="在指令内容后添加单独一行 `:::`"
            )

        return result


# ============================================================================
# 嵌入式 HTML 校验器
# ============================================================================

class ImgTagParser(HTMLParser):
    """HTML 解析器 - 专门用于提取和验证 img 标签"""

    def __init__(self):
        super().__init__()
        self.img_tags = []  # [(line, attrs_dict)]
        self.errors = []
        self._current_line = 1

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            attrs_dict = dict(attrs)
            self.img_tags.append((self._current_line, attrs_dict))

    def error(self, message):
        self.errors.append((self._current_line, message))

    def feed(self, data):
        # 跟踪行号
        for i, line in enumerate(data.split("\n"), start=1):
            self._current_line = i
            try:
                super().feed(line)
            except Exception as e:
                self.errors.append((i, str(e)))
        self.reset()


class EmbeddedHTMLValidator:
    """
    嵌入式 HTML 标签校验器

    检查内容：
    1. `<img>` 标签是否符合 HTML5 语法
    2. `style` 属性中的 CSS 是否合法
    3. 必要属性 (src, alt) 是否存在
    4. object-position 等裁切参数格式是否正确
    """

    # CSS 属性值的简单验证模式
    CSS_VALUE_PATTERNS = {
        "object-position": re.compile(r'^[\d.]+%?\s+[\d.]+%?$|^(top|bottom|left|right|center)(\s+(top|bottom|left|right|center))?$'),
        "object-fit": re.compile(r'^(cover|contain|fill|none|scale-down)$'),
        "width": re.compile(r'^[\d.]+(px|%|em|rem|vw|vh)?$|^auto$'),
        "height": re.compile(r'^[\d.]+(px|%|em|rem|vw|vh)?$|^auto$'),
    }

    def validate(self, content: str) -> ValidationResult:
        """执行校验"""
        result = ValidationResult(is_valid=True, validator_name="EmbeddedHTMLValidator")

        parser = ImgTagParser()
        parser.feed(content)

        # 报告解析错误
        for line_num, error_msg in parser.errors:
            result.add_error(
                f"HTML 解析错误: {error_msg}",
                line_number=line_num
            )

        # 验证每个 img 标签
        for line_num, attrs in parser.img_tags:
            self._validate_img_tag(result, line_num, attrs)

        return result

    def _validate_img_tag(self, result: ValidationResult, line_num: int, attrs: dict) -> None:
        """验证单个 img 标签"""
        # 检查必要属性
        if "src" not in attrs:
            result.add_error(
                "img 标签缺少 src 属性",
                line_number=line_num,
                suggestion="添加 src 属性指向图片路径"
            )

        if "alt" not in attrs:
            result.add_warning(
                "img 标签缺少 alt 属性 (影响无障碍访问)",
                line_number=line_num,
                suggestion="添加 alt 属性描述图片内容"
            )

        # 验证 style 属性
        if "style" in attrs:
            self._validate_style_attribute(result, line_num, attrs["style"])

    def _validate_style_attribute(self, result: ValidationResult, line_num: int, style: str) -> None:
        """验证 style 属性中的 CSS"""
        # 解析 style 字符串
        declarations = [d.strip() for d in style.split(";") if d.strip()]

        for decl in declarations:
            if ":" not in decl:
                result.add_error(
                    f"CSS 声明格式错误: '{decl}'",
                    line_number=line_num,
                    suggestion="CSS 声明格式: property: value"
                )
                continue

            prop, value = decl.split(":", 1)
            prop = prop.strip().lower()
            value = value.strip()

            # 验证已知属性的值
            if prop in self.CSS_VALUE_PATTERNS:
                pattern = self.CSS_VALUE_PATTERNS[prop]
                if not pattern.match(value):
                    result.add_warning(
                        f"CSS 属性值可能无效: {prop}: {value}",
                        line_number=line_num,
                        suggestion=f"检查 {prop} 的有效值格式"
                    )


# ============================================================================
# LaTeX 公式平衡校验器
# ============================================================================

class LaTeXBalanceValidator:
    r"""
    LaTeX 公式符号平衡校验器

    检查内容：
    1. `$` 和 `$$` 是否成对出现
    2. 括号 `{}`, `()`, `[]` 是否平衡
    3. `\\begin{}` 和 `\\end{}` 是否配对
    """

    # 匹配 LaTeX 环境
    BEGIN_PATTERN = re.compile(r'\\begin\{(\w+)\}')
    END_PATTERN = re.compile(r'\\end\{(\w+)\}')

    def validate(self, content: str) -> ValidationResult:
        """执行校验"""
        result = ValidationResult(is_valid=True, validator_name="LaTeXBalanceValidator")

        # 检查 $ 和 $$ 符号
        self._check_dollar_signs(content, result)

        # 检查 \begin{} 和 \end{} 配对
        self._check_environments(content, result)

        return result

    def _check_dollar_signs(self, content: str, result: ValidationResult) -> None:
        """
        科学校验 $ 和 $$ 符号平衡 (SOTA 2.0 全量扫描法)
        """
        # 1. 移除代码块干扰
        clean_content = re.sub(r'```[\s\S]*?```', '', content)
        
        # 2. 移除转义的美元符号 (\$)
        clean_content = clean_content.replace(r'\$', '')

        # 3. 提取所有块级公式 ($$ ... $$)
        # 使用非贪婪匹配
        display_math = re.findall(r'\$\$[\s\S]*?\$\$', clean_content)
        for dm in display_math:
            # 内部检查：公式内部不应含有三连美元符号
            if "$$$" in dm:
                result.add_error(
                    f"块级公式内部检测到非法符号堆叠: {dm[:30]}...",
                    context=dm,
                    suggestion="请检查是否多写了美元符号。"
                )
        
        # 4. 从内容中移除已匹配的块级公式，防止干扰行内匹配
        remaining = re.sub(r'\$\$[\s\S]*?\$\$', ' [BLOCK_MATH] ', clean_content)

        # 5. 提取所有行内公式 ($ ... $)
        # 注意：这里要处理一行内有多个 $ 的情况，且不能跨段落
        inline_math = re.findall(r'\$[^\$\n]+?\$', remaining)
        
        # 6. 最后检查：剩下的文本中是否还有残留的孤立 $
        final_remnant = re.sub(r'\$[^\$\n]+?\$', ' [INLINE_MATH] ', remaining)
        
        if "$" in final_remnant:
            # 找到具体的行号
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                # 排除已经被占位符替换的部分
                # 简单检查该行是否含有奇数个 $
                if line.count("$") % 2 != 0 and "\\$" not in line:
                    result.add_error(
                        f"检测到未闭合的 LaTeX 符号 '$' 或非法堆叠",
                        line_number=i,
                        context=line.strip()[:60],
                        suggestion="确保所有 $ 或 $$ 成对出现，且没有 $$$ 这种三连符号。"
                    )

    def _check_environments(self, content: str, result: ValidationResult) -> None:
        """检查 LaTeX 环境配对"""
        lines = content.split("\n")
        env_stack = []  # [(env_name, line_number)]

        for line_num, line in enumerate(lines, start=1):
            # 查找 \begin{...}
            for match in self.BEGIN_PATTERN.finditer(line):
                env_name = match.group(1)
                env_stack.append((env_name, line_num))

            # 查找 \end{...}
            for match in self.END_PATTERN.finditer(line):
                env_name = match.group(1)
                if not env_stack:
                    result.add_error(
                        f"发现未匹配的 \\end{{{env_name}}}",
                        line_number=line_num,
                        suggestion=f"检查是否缺少对应的 \\begin{{{env_name}}}"
                    )
                elif env_stack[-1][0] != env_name:
                    expected = env_stack[-1][0]
                    result.add_error(
                        f"LaTeX 环境不匹配: 期望 \\end{{{expected}}}，实际 \\end{{{env_name}}}",
                        line_number=line_num,
                        suggestion="检查环境嵌套顺序"
                    )
                else:
                    env_stack.pop()

        # 检查未闭合的环境
        for env_name, start_line in env_stack:
            result.add_error(
                f"LaTeX 环境 \\begin{{{env_name}}} 未闭合",
                line_number=start_line,
                suggestion=f"添加对应的 \\end{{{env_name}}}"
            )


# ============================================================================
# 命名空间校验器
# ============================================================================

class NamespaceValidator:
    """
    ID 命名空间校验器

    检查内容：
    1. HTML 标签中的 ID 是否以指定命名空间开头
    2. 检测潜在的 ID 冲突
    """

    # 匹配 HTML 中的 id 属性
    ID_PATTERN = re.compile(r'id=["\']([^"\']+)["\']', re.IGNORECASE)

    def validate(self, content: str, expected_namespace: str) -> ValidationResult:
        """
        执行校验

        Args:
            content: Markdown/HTML 内容
            expected_namespace: 期望的命名空间前缀 (如 "s1", "s2")
        """
        result = ValidationResult(is_valid=True, validator_name="NamespaceValidator")
        prefix = f"{expected_namespace}-"

        lines = content.split("\n")
        found_ids = []  # [(id, line_number)]

        for line_num, line in enumerate(lines, start=1):
            for match in self.ID_PATTERN.finditer(line):
                element_id = match.group(1)
                found_ids.append((element_id, line_num))

                # 检查命名空间前缀
                if not element_id.startswith(prefix):
                    result.add_warning(
                        f"ID '{element_id}' 未使用命名空间前缀 '{prefix}'",
                        line_number=line_num,
                        suggestion=f"建议改为: {prefix}{element_id}"
                    )

        # 检测重复 ID
        id_counts = {}
        for element_id, line_num in found_ids:
            if element_id in id_counts:
                result.add_error(
                    f"发现重复的 ID: '{element_id}'",
                    line_number=line_num,
                    context=f"首次出现在行 {id_counts[element_id]}",
                    suggestion="每个 ID 必须唯一"
                )
            else:
                id_counts[element_id] = line_num

        return result


# ============================================================================
# 综合校验器
# ============================================================================

class MarkdownValidator:
    """
    综合 Markdown 校验器

    整合所有校验器，提供一站式校验服务
    """

    def __init__(self):
        self.structure_validator = MarkdownStructureValidator()
        self.html_validator = EmbeddedHTMLValidator()
        self.latex_validator = LaTeXBalanceValidator()
        self.namespace_validator = NamespaceValidator()

    def validate_all(
        self,
        content: str,
        namespace: Optional[str] = None,
        skip_latex: bool = False,
        skip_html: bool = False
    ) -> ValidationResult:
        """
        执行全面校验

        Args:
            content: Markdown 内容
            namespace: 命名空间前缀 (如果提供则进行 ID 校验)
            skip_latex: 跳过 LaTeX 校验
            skip_html: 跳过 HTML 校验

        Returns:
            综合校验结果
        """
        combined = ValidationResult(is_valid=True, validator_name="MarkdownValidator")

        # 1. 结构校验 (始终执行)
        structure_result = self.structure_validator.validate(content)
        combined.merge(structure_result)

        # 2. HTML 校验
        if not skip_html:
            html_result = self.html_validator.validate(content)
            combined.merge(html_result)

        # 3. LaTeX 校验
        if not skip_latex:
            latex_result = self.latex_validator.validate(content)
            combined.merge(latex_result)

        # 4. 命名空间校验
        if namespace:
            ns_result = self.namespace_validator.validate(content, namespace)
            combined.merge(ns_result)

        return combined

    def validate_quick(self, content: str) -> ValidationResult:
        """
        快速校验 (仅检查结构)

        用于实时校验场景，追求速度
        """
        return self.structure_validator.validate(content)
