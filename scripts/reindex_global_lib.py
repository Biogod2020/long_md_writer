#!/usr/bin/env python3
"""
全局资产库重建工具

扫描 data/global_asset_lib/ 目录下的所有图片资产，
使用 Vision API 生成语义标签，并将索引保存到 master_assets.json。

特性：
- MD5 去重：已索引的资产不会重复调用 API
- 增量更新：仅为新增或修改的文件生成标签
- 跨项目复用：生成的索引可被所有项目挂载使用

用法：
    python scripts/reindex_global_lib.py [--skip-vision] [--force]

选项：
    --skip-vision   跳过 Vision API 调用 (仅扫描并计算哈希)
    --force         强制重建所有索引 (忽略已有哈希)
"""

import sys
import argparse
import hashlib
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.gemini_client import GeminiClient
from src.core.types import UniversalAssetRegistry, AssetEntry, AssetSource, AssetQualityLevel
from src.agents.asset_management.processors.vision import analyze_image


# 配置
GLOBAL_LIB_PATH = PROJECT_ROOT / "data" / "global_asset_lib"
IMAGES_PATH = GLOBAL_LIB_PATH / "images"
UAR_PATH = GLOBAL_LIB_PATH / "master_assets.json"

SUPPORTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]


def compute_hash(file_path: Path) -> str:
    """计算文件 MD5 哈希"""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def scan_images(directory: Path) -> list[Path]:
    """扫描目录下所有图片"""
    images = []
    for ext in SUPPORTED_EXTENSIONS:
        images.extend(directory.rglob(f"*{ext}"))
        images.extend(directory.rglob(f"*{ext.upper()}"))
    return sorted(set(images))


import re

def slugify(text: str) -> str:
    """将文本转换为合法的文件名 slug"""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')[:50]

def main():
    parser = argparse.ArgumentParser(description="全局资产库重建工具")
    parser.add_argument("--skip-vision", action="store_true", help="跳过 Vision API 调用")
    parser.add_argument("--force", action="store_true", help="强制重建所有索引")
    parser.add_argument("--rename", action="store_true", help="根据语义标签重命名文件 (推荐)")
    args = parser.parse_args()

    print("=" * 60)
    print(" 🗂️  全局资产库重建工具 (Enhanced)")
    print("=" * 60)
    print(f"📁 资产目录: {IMAGES_PATH}")
    print(f"📄 索引文件: {UAR_PATH}")
    print()

    # 确保目录存在
    IMAGES_PATH.mkdir(parents=True, exist_ok=True)

    # 加载或创建 UAR
    if args.force:
        print("⚠️  强制模式：创建全新索引")
        uar = UniversalAssetRegistry()
    else:
        uar = UniversalAssetRegistry.load_from_file(str(UAR_PATH))
        print(f"📊 已加载 {len(uar.assets)} 个现有资产")
    
    # 设置持久化路径
    uar.set_persist_path(str(UAR_PATH))

    # 初始化客户端
    client = GeminiClient() if not args.skip_vision else None

    # 扫描图片
    print("\n🔍 开始扫描资产目录...")
    image_files = scan_images(IMAGES_PATH)
    print(f"📷 发现 {len(image_files)} 个图片文件")

    # 索引每个图片
    new_assets = []
    for img_path in image_files:
        content_hash = compute_hash(img_path)
        
        # 检查是否已存在
        exists = any(a.content_hash == content_hash for a in uar.assets.values())
        if exists:
            # 如果文件本身已经被重命名，通过哈希跳过
            print(f"  - 跳过已索引: {img_path.name}")
            continue
        
        # 生成语义标签
        if args.skip_vision:
            semantic_label = f"Image {img_path.stem}"
            quality_level = AssetQualityLevel.UNASSESSED
        else:
            vision_result = analyze_image(client, img_path)
            semantic_label = vision_result.get("semantic_label", img_path.stem)
            quality_level = AssetQualityLevel.MEDIUM
        
        # 语义化重命名逻辑
        final_img_path = img_path
        if args.rename and not args.skip_vision:
            slug = slugify(semantic_label)
            # 包含哈希前4位和扩展名，确保物理文件名唯一
            new_name = f"{slug}-{content_hash[:4]}{img_path.suffix.lower()}"
            final_img_path = img_path.parent / new_name
            
            if img_path.name != new_name:
                if not final_img_path.exists():
                    img_path.rename(final_img_path)
                    print(f"  📝 重命名: {img_path.name} -> {new_name}")
                else:
                    # 如果目标已存在但内容哈希不同（理论上不该发生，除非 slug 碰撞）
                    print(f"  - 目标已存在: {new_name}, 跳过物理重命名")

        # 计算相对路径
        try:
            relative_path = final_img_path.relative_to(GLOBAL_LIB_PATH)
        except ValueError:
            relative_path = final_img_path
        
        # 创建资产条目
        # 在 ID 中包含哈希后缀，防止同名文件在 UAR 中冲突
        asset_id = f"global-{final_img_path.stem}"
        if not asset_id.endswith(content_hash[:4]):
             asset_id = f"{asset_id}-{content_hash[:4]}"
             
        entry = AssetEntry(
            id=asset_id,
            source=AssetSource.USER,
            local_path=str(relative_path),
            semantic_label=semantic_label,
            content_hash=content_hash,
            quality_level=quality_level,
            vqa_status="SKIPPED",
            tags=["global", final_img_path.suffix.lower().replace(".", "")],
        )
        
        uar.register_immediate(entry)  # 自动持久化
        new_assets.append(entry)
        print(f"  ✓ {asset_id}: {semantic_label[:40]}...")

    print(f"\n✅ 新增索引: {len(new_assets)} 个资产")
    print(f"📊 总资产数: {len(uar.assets)}")
    print(f"\n💾 索引已保存到: {UAR_PATH}")


    print("\n" + "=" * 60)
    print(" ✨ 完成！所有项目现在可以使用此全局索引")
    print("=" * 60)


if __name__ == "__main__":
    main()

