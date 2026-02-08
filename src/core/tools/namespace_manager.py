"""
SOTA 2.0 命名空间管理器 (NamespaceManager)

核心职责：
1. 为章节自动分配命名空间前缀
2. 更新 Manifest 中的 SectionInfo.metadata
3. 提供 ID 生成工具函数
"""

import re
from typing import Optional
from ..types import Manifest, SectionInfo


class NamespaceManager:
    """
    命名空间管理器

    为 Manifest 中的每个章节分配唯一的命名空间前缀，
    确保跨章节的 ID 不会冲突。

    命名规则：
    - 章节命名空间: s{index+1} (如 s1, s2, s3)
    - 资产 ID 格式: {namespace}-{type}-{slug} (如 s1-img-ecg-diagram)
    - HTML ID 格式: {namespace}-{element-type}-{name} (如 s1-sec-introduction)
    """

    # 默认命名空间前缀格式
    NAMESPACE_FORMAT = "s{index}"

    def __init__(self, custom_format: Optional[str] = None):
        """
        初始化命名空间管理器

        Args:
            custom_format: 自定义命名空间格式 (包含 {index} 占位符)
        """
        self.format = custom_format or self.NAMESPACE_FORMAT

    def assign_namespaces(self, manifest: Manifest) -> Manifest:
        """
        为 Manifest 中的所有章节分配命名空间，并物理修改 ID 以确保全局唯一性。
        """
        new_knowledge_map = {}
        
        for i, section in enumerate(manifest.sections):
            namespace = self.format.format(index=i + 1)
            section.metadata["namespace"] = namespace
            
            old_id = section.id
            # 如果章节 ID 尚未包含命名空间前缀，则物理修改它
            if not old_id.startswith(f"{namespace}-"):
                section.metadata["original_id"] = old_id
                section.id = f"{namespace}-{old_id}"
                print(f"  [Namespace] ID Refactored: {old_id} -> {section.id}")
            
            # 同步更新知识图谱的 Key
            if old_id in manifest.knowledge_map:
                new_knowledge_map[section.id] = manifest.knowledge_map[old_id]
        
        # 替换为更新后的知识图谱
        if new_knowledge_map:
            manifest.knowledge_map = new_knowledge_map

        return manifest

    def get_namespace(self, section_index: int) -> str:
        """
        获取指定索引的命名空间

        Args:
            section_index: 章节索引 (0-based)

        Returns:
            命名空间字符串 (如 "s1", "s2")
        """
        return self.format.format(index=section_index + 1)

    def generate_asset_id(
        self,
        namespace: str,
        asset_type: str,
        slug: str
    ) -> str:
        """
        生成资产 ID

        Args:
            namespace: 命名空间 (如 "s1")
            asset_type: 资产类型 (如 "img", "svg", "chart")
            slug: 语义化简称 (如 "ecg-diagram")

        Returns:
            完整资产 ID (如 "s1-img-ecg-diagram")
        """
        # 清理 slug
        clean_slug = self._sanitize_slug(slug)
        return f"{namespace}-{asset_type}-{clean_slug}"

    def generate_element_id(
        self,
        namespace: str,
        element_type: str,
        name: str
    ) -> str:
        """
        生成 HTML 元素 ID

        Args:
            namespace: 命名空间 (如 "s1")
            element_type: 元素类型 (如 "sec", "fig", "tbl", "eq")
            name: 元素名称 (如 "introduction", "main-diagram")

        Returns:
            完整元素 ID (如 "s1-sec-introduction")
        """
        clean_name = self._sanitize_slug(name)
        return f"{namespace}-{element_type}-{clean_name}"

    def _sanitize_slug(self, text: str) -> str:
        """
        清理文本为合法的 slug

        - 转小写
        - 空格和下划线转为连字符
        - 移除非法字符
        - 限制长度
        """
        slug = text.lower()
        slug = re.sub(r'[\s_]+', '-', slug)  # 空格/下划线 -> 连字符
        slug = re.sub(r'[^a-z0-9\-\u4e00-\u9fff]', '', slug)  # 保留字母数字连字符和中文
        slug = re.sub(r'-+', '-', slug)  # 多个连字符合并
        slug = slug.strip('-')  # 去除首尾连字符
        return slug[:50]  # 限制长度

    def extract_namespace(self, id_string: str) -> Optional[str]:
        """
        从 ID 字符串中提取命名空间

        Args:
            id_string: ID 字符串 (如 "s1-img-diagram")

        Returns:
            命名空间 (如 "s1") 或 None
        """
        match = re.match(r'^(s\d+)-', id_string)
        if match:
            return match.group(1)
        return None

    def validate_id_namespace(self, id_string: str, expected_namespace: str) -> bool:
        """
        验证 ID 是否属于指定命名空间

        Args:
            id_string: ID 字符串
            expected_namespace: 期望的命名空间

        Returns:
            是否匹配
        """
        return id_string.startswith(f"{expected_namespace}-")


# ============================================================================
# 便捷函数
# ============================================================================

def assign_namespaces_to_manifest(manifest: Manifest) -> Manifest:
    """
    为 Manifest 分配命名空间的便捷函数

    Example:
        manifest = assign_namespaces_to_manifest(manifest)
        ns = manifest.sections[0].metadata.get("namespace")  # "s1"
    """
    manager = NamespaceManager()
    return manager.assign_namespaces(manifest)


def get_section_namespace(section: SectionInfo) -> str:
    """
    获取章节的命名空间

    Args:
        section: 章节信息

    Returns:
        命名空间字符串，如果未分配则返回 "s0"
    """
    return section.metadata.get("namespace", "s0")


def generate_scoped_id(
    section: SectionInfo,
    element_type: str,
    name: str
) -> str:
    """
    为章节生成作用域内的 ID

    Example:
        section = manifest.sections[0]  # namespace: s1
        id = generate_scoped_id(section, "fig", "main-chart")
        # Returns: "s1-fig-main-chart"
    """
    namespace = get_section_namespace(section)
    manager = NamespaceManager()
    return manager.generate_element_id(namespace, element_type, name)
