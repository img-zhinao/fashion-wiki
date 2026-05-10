#!/usr/bin/env python3
"""
Fashion Wiki 全局索引自动更新脚本
扫描所有 Markdown 文件，生成 index.md 全局内容字典
"""

import re
from pathlib import Path
from datetime import datetime

WORKSPACE = Path("/Users/zgeo01/.openclaw/workspace/content/fashion-wiki")
CONTENT_DIR = WORKSPACE / "content"
INDEX_FILE = CONTENT_DIR / "index.md"

def extract_frontmatter(filepath):
    """提取 Markdown 文件的 frontmatter"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 提取 title
        title_match = re.search(r'^title:\s*(.+)$', content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else filepath.stem
        
        # 提取 description
        desc_match = re.search(r'^description:\s*(.+)$', content, re.MULTILINE)
        description = desc_match.group(1).strip() if desc_match else ""
        
        # 提取 tags
        tags_match = re.search(r'^tags:\s*\[(.*?)\]', content, re.MULTILINE)
        tags = tags_match.group(1).strip() if tags_match else ""
        
        return {
            "title": title,
            "description": description[:140],
            "tags": tags,
            "slug": filepath.stem,
            "folder": filepath.parent.name
        }
    except Exception as e:
        print(f"❌ 读取失败 {filepath}: {e}")
        return None

def categorize(folder):
    """根据文件夹分类"""
    categories = {
        "concepts": "概念层",
        "brands": "品牌层",
        "fabrics": "面料层",
        "trends": "趋势层",
        "supply-chain": "供应链层",
        "guides": "指南层",
        "faq": "问答层",
        "reports": "报告层"
    }
    return categories.get(folder, folder)

def generate_index():
    """生成全局索引"""
    
    # 扫描所有 Markdown 文件
    files = sorted(CONTENT_DIR.rglob("*.md"))
    
    # 分类收集
    categories = {}
    for f in files:
        if f.name == "index.md":
            continue
        
        fm = extract_frontmatter(f)
        if not fm:
            continue
        
        cat = categorize(fm["folder"])
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(fm)
    
    # 生成索引内容
    lines = [
        "---",
        "title: \"Fashion Wiki 全局内容字典\"",
        f"description: \"服装产业 AI 知识网络的内容索引，记录所有页面的 slug 与一句话描述。\"",
        f"date: {datetime.now().strftime('%Y-%m-%d')}",
        "tags: [index, fashion, wiki]",
        "aliases: [home, 首页]",
        "---",
        "",
        "# Fashion Wiki 全局内容字典",
        "",
        f"> 服装产业 AI 知识网络的内容索引，记录所有页面的 slug 与一句话描述。",
        f"> 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 共 {sum(len(v) for v in categories.values())} 篇文章",
        ""
    ]
    
    # 按分类输出
    for cat in ["概念层", "品牌层", "面料层", "趋势层", "供应链层", "指南层", "问答层", "报告层"]:
        if cat not in categories:
            continue
        
        items = categories[cat]
        if not items:
            continue
        
        lines.append(f"## {cat}")
        lines.append("")
        
        for item in items:
            desc = item["description"] or item["title"]
            lines.append(f"- [[{item['slug']}]] | {desc}")
        
        lines.append("")
    
    # 添加统计
    lines.append("## 统计")
    lines.append("")
    lines.append(f"- 总文章数: {sum(len(v) for v in categories.values())}")
    for cat, items in categories.items():
        lines.append(f"- {cat}: {len(items)} 篇")
    lines.append("")
    lines.append(f"*最后自动更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    
    return "\n".join(lines)

def main():
    print("📝 更新 Fashion Wiki 全局索引...")
    
    content = generate_index()
    
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"✅ 索引更新完成: {INDEX_FILE}")
    print(f"   共 {content.count('[[')} 个页面")

if __name__ == "__main__":
    main()
