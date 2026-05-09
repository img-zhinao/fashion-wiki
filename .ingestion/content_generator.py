#!/usr/bin/env python3
"""
Fashion Wiki 内容智造引擎 (Content Generator)
将原始采集内容转化为 LLM-Wiki 格式的高质量文章

用法: python3 content_generator.py --input-dir ./raw --output-dir ../content
"""

import os
import json
import sys
import re
from datetime import datetime
from pathlib import Path
import requests

# 配置
BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "raw"
OUTPUT_DIR = BASE_DIR.parent / "content"
LOG_FILE = BASE_DIR / "logs" / f"generator_{datetime.now().strftime('%Y%m%d')}.log"

# API Keys
# 尝试加载 .env 文件
def load_env():
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    if key and value:
                        os.environ[key.strip()] = value.strip()

load_env()

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")

# 时尚行业关键词（用于内容相关性过滤）
FASHION_KEYWORDS = [
    # 中文
    "服装", "服饰", "时装", "时尚", "潮流", "穿搭", "搭配",
    "面料", "布料", "纤维", "纺织", "棉", "丝", "毛", "麻", "绒",
    "品牌", "设计师", "联名", "系列", "新品", "发布", "秀场",
    "时装周", "春夏", "秋冬", "趋势", "流行", "色彩", "款式",
    "供应链", "代工", "工厂", "生产", "制造", "快反", "小单",
    "消费者", "市场", "零售", "电商", "直播", "买手", "门店",
    "可持续", "环保", "有机", "再生", "低碳", "循环经济",
    "OEM", "ODM", "FOB", "CMT", "贴牌", "外贸", "出口", "订单",
    "汉服", "国潮", "新中式", "旗袍", "唐装", "民族风",
    "西装", "衬衫", "连衣裙", "T恤", "牛仔裤", "外套", "大衣",
    "童装", "女装", "男装", "内衣", "运动服", "瑜伽", "户外",
    "高跟鞋", "运动鞋", "包包", "配饰", "珠宝", "手表", "眼镜",
    # 英文
    "fashion", "apparel", "garment", "clothing", "textile",
    "fabric", "fiber", "wool", "silk", "cotton", "linen",
    "brand", "designer", "collection", "runway", "show",
    "trend", "style", "couture", "luxury", "premium",
    "retail", "ecommerce", "boutique", "wholesale",
    "sustainable", "eco-friendly", "organic", "recycled",
    "supply chain", "manufacturing", "factory", "sourcing",
    "knitwear", "denim", "leather", "fur", "down",
    "activewear", "sportswear", "lingerie", "swimwear",
]

def is_fashion_related(title: str, summary: str = "") -> bool:
    """检测内容是否与时尚行业相关"""
    text = f"{title} {summary}".lower()
    
    # 计算匹配的关键词数量
    matches = sum(1 for kw in FASHION_KEYWORDS if kw.lower() in text)
    
    # 至少匹配 2 个关键词，或 1 个强相关词
    strong_keywords = ["服装", "时装", "时尚", "fashion", "apparel", "面料", "品牌", "designer"]
    has_strong = any(kw.lower() in text for kw in strong_keywords)
    
    return matches >= 2 or has_strong
KNOWN_ENTITIES = {
    "UR": "[[ur]]", "URBAN REVIVO": "[[ur]]", "Urban Revivo": "[[ur]]",
    "太平鸟": "[[peacebird]]", "PEACEBIRD": "[[peacebird]]",
    "ICICLE": "[[icicle]]", "之禾": "[[icicle]]",
    "MO&Co": "[[mo-co]]", "MOCo": "[[mo-co]]",
    "例外": "[[exceptions]]", "EXCEPTION": "[[exceptions]]",
    "天丝": "[[tencel]]", "TENCEL": "[[tencel]]", "莱赛尔": "[[tencel]]",
    "美利奴羊毛": "[[merino-wool]]", "Merino": "[[merino-wool]]",
    "真丝": "[[silk]]", "蚕丝": "[[silk]]", "桑蚕丝": "[[silk]]",
    "羊绒": "[[cashmere]]",
    "有机棉": "[[organic-cotton]]",
    "再生涤纶": "[[recycled-polyester]]",
    "GEO": "[[geo-fashion]]",
    "2026 春夏": "[[spring-summer-2026]]", "春夏趋势": "[[spring-summer-2026]]",
    "多巴胺": "[[spring-summer-2026]]",
    "新中式": "[[new-chinese-style]]",
    "静奢风": "[[quiet-luxury]]",
    "运动休闲": "[[athleisure]]",
    "ODM": "[[odm-vs-oem]]", "OEM": "[[odm-vs-oem]]",
    "小单快反": "[[small-batch]]",
    "体型穿搭": "[[body-type-dressing]]",
    "职场衣橱": "[[career-wardrobe]]",
}

def log(msg):
    """记录日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def classify_content(title, summary=""):
    """判断内容类型 - 增强版，支持混合类型识别"""
    text = f"{title} {summary}".lower()
    
    # 面料相关 (优先级较高)
    fabric_keywords = ["面料", "纤维", "材质", "纺织", "棉", "丝", "毛", "麻", "绒", "纱",
                      "天丝", "莫代尔", "涤纶", "尼龙", "氨纶", "羊毛", "羊绒",
                      "针织", "梭织", "牛仔", "皮革", "羽绒", "面料科技",
                      "fabric", "fiber", "textile", "knit", "woven", "denim",
                      "sustainable fabric", "organic cotton", "recycled polyester"]
    if any(k in text for k in fabric_keywords):
        return "fabric"
    
    # 供应链相关 (优先级较高)
    supply_keywords = ["供应链", "工厂", "采购", "代工", "生产", "制造", "供应商",
                      "ODM", "OEM", "FOB", "CMT", "贴牌", "外贸", "出口", "订单",
                      "小单快反", "快反", "柔性供应链", "数字化工厂",
                      "supply chain", "manufacturing", "factory", "sourcing",
                      "production", "supplier", "vendor", "logistics"]
    if any(k in text for k in supply_keywords):
        return "supply"
    
    # 品牌相关
    brand_keywords = ["品牌", "联名", "新品", "发布", "旗舰店", "门店", "零售",
                     "UR", "太平鸟", "ICICLE", "之禾", "MO&Co", "例外",
                     "Zara", "H&M", "Uniqlo", "优衣库", "Gap", "Nike", "Adidas",
                     "品牌定位", "品牌战略", "品牌升级", "品牌出海",
                     "brand strategy", "brand positioning", "brand launch",
                     "retail expansion", "store opening", "collaboration"]
    if any(k in text for k in brand_keywords):
        return "brand"
    
    # 指南/消费者相关
    guide_keywords = ["穿搭", "搭配", "体型", "衣橱", "职场", "护理", "保养",
                     "选购", "挑选", "适合", "推荐", "指南", "攻略",
                     "小个子", "高个子", "微胖", "显瘦", "显高",
                     "stying", "how to wear", "dressing guide", "wardrobe",
                     "body type", "outfit", "style guide", "fashion tips"]
    if any(k in text for k in guide_keywords):
        return "guide"
    
    # 概念/方法论
    concept_keywords = ["GEO", "方法论", "模型", "框架", "体系", "标准化",
                       "概念", "定义", "分类", "维度", "指标",
                       "方法论", "最佳实践", "行业洞察", "白皮书",
                       "framework", "methodology", "model", "standard"]
    if any(k in text for k in concept_keywords):
        return "concept"
    
    # 趋势 (默认)
    return "trend"

def build_prompt(title, summary, content_type):
    """构建 Perplexity prompt - 明确从时尚行业视角分析"""
    
    prompts = {
        "trend": """你是 Fashion Wiki 的高级趋势编辑。请基于以下资讯，撰写一篇面向中国服装行业的趋势分析文章。

重要：即使原始内容是国际新闻（如关税、贸易政策），也要从"对中国服装行业的影响"角度分析。

要求：
1. 标题用中文，不超过 30 字，突出时尚/服装行业视角
2. 开头用 ">" 给出对中国服装行业的核心影响结论（一句话）
3. 用 Markdown 表格呈现关键数据对比
4. 包含对中国服装企业的具体影响和建议
5. 底部添加"关联阅读"区域，列出 2-3 个相关 Fashion Wiki 页面
6. 标注数据来源和时效性
7. 总字数 800-1500 字
8. 纯 Markdown 格式，不要输出任何其他内容

原始内容：
标题: {title}
摘要: {summary}
""",
        "brand": """你是 Fashion Wiki 的品牌研究员。请基于以下品牌资讯，撰写一篇品牌知识卡片。

要求：
1. 一句话定位品牌（不超过 50 字）
2. 品牌档案表格：创立时间、总部、价格带、目标人群
3. 核心优势列表（3-5 条）
4. 与主要竞品对比表格
5. GEO 优化建议（如何让 AI 更好引用该品牌，2-3 条）
6. 底部添加"关联阅读"
7. 总字数 600-1200 字
8. 纯 Markdown 格式

原始内容：
标题: {title}
摘要: {summary}
""",
        "fabric": """你是 Fashion Wiki 的面料科学家。请基于以下面料资讯，撰写一篇面料百科。

要求：
1. 一句话定义该面料（不超过 50 字）
2. 与其他常见面料对比表格（至少 3 种）
3. 核心性能优势（透气、保暖、环保等）
4. 应用场景列表
5. 护理方法简表
6. 底部添加"关联阅读"
7. 总字数 600-1200 字
8. 纯 Markdown 格式

原始内容：
标题: {title}
摘要: {summary}
""",
        "supply": """你是 Fashion Wiki 的供应链专家。请基于以下资讯，撰写供应链相关文章。

要求：
1. 核心概念解释（不超过 100 字）
2. 关键数据表格
3. 行业实践案例
4. 对服装企业的建议
5. 底部添加"关联阅读"
6. 总字数 600-1000 字
7. 纯 Markdown 格式

原始内容：
标题: {title}
摘要: {summary}
""",
        "guide": """你是 Fashion Wiki 的消费指南编辑。请基于以下资讯，撰写消费者指南。

要求：
1. 核心建议的一句话总结
2. 分场景表格（不同体型/场合/季节的推荐）
3. 具体 actionable 的建议
4. 常见误区提醒
5. 底部添加"关联阅读"
6. 总字数 500-1000 字
7. 纯 Markdown 格式

原始内容：
标题: {title}
摘要: {summary}
"""
    }
    
    template = prompts.get(content_type, prompts["trend"])
    return template.format(title=title, summary=summary[:2000])

def call_ai(prompt, max_retries=2):
    """调用 Perplexity API 生成内容（替代 Kimi）"""
    if not PERPLEXITY_API_KEY:
        log("⚠️ PERPLEXITY_API_KEY 未设置，跳过 AI 生成")
        return None
    
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """你是 Fashion Wiki 的高级内容编辑。请基于提供的时尚行业资讯，撰写一篇结构化的 LLM-Wiki 格式文章。

要求：
1. 标题用中文，不超过 30 字
2. 开头用 ">" 给出核心结论的一句话摘要
3. 用 Markdown 表格呈现关键数据对比
4. 包含 3-5 个核心要点
5. 底部添加"关联阅读"
6. 标注数据来源和时效性
7. 纯 Markdown 格式，不要输出任何其他内容"""
    
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 4000
    }
    
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return content
            else:
                log(f"⚠️ Perplexity API 返回 {resp.status_code}: {resp.text[:200]}")
                if attempt < max_retries - 1:
                    continue
        except Exception as e:
            log(f"❌ Perplexity API 调用失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                continue
    
    return None

def quality_score(content):
    """
    质量评分算法 (0-100)
    """
    score = 0
    
    # 基础分
    if len(content) > 500: score += 15
    if len(content) > 800: score += 10
    if len(content) > 1200: score += 5
    
    # 结构化
    if "|" in content: score += 20  # 表格
    if ">" in content: score += 15   # One-Liner/引用
    if "##" in content: score += 10  # 标题层级
    
    # 双向链接
    if "[[" in content: score += 10
    
    # 完整性
    if "关联阅读" in content or "相关" in content: score += 10
    if "来源" in content or "数据" in content: score += 5
    if "202" in content: score += 5  # 时效性
    
    return min(100, score)

def add_backlinks(content):
    """自动补充双向链接"""
    modified = content
    
    for entity, link in KNOWN_ENTITIES.items():
        if entity in modified and link not in modified:
            # 只替换第一次出现，避免过度链接
            modified = modified.replace(entity, f"{entity}{link}", 1)
    
    return modified

def slugify(title):
    """将标题转为 URL slug"""
    # 中文标题：用拼音或保留中文
    # 简化处理：取前 20 个字符，替换空格为 -
    slug = re.sub(r'[^\w\u4e00-\u9fff\s-]', '', title)
    slug = re.sub(r'[\s]+', '-', slug.strip())
    return slug[:40].lower()

def generate_filename(content_type, title):
    """生成文件名"""
    folder_map = {
        "trend": "trends",
        "brand": "brands", 
        "fabric": "fabrics",
        "supply": "supply-chain",
        "guide": "guides"
    }
    
    folder = folder_map.get(content_type, "concepts")
    slug = slugify(title)
    timestamp = datetime.now().strftime('%Y%m%d')
    
    return f"{folder}/{slug}-{timestamp}.md"

def add_frontmatter(content, title, description, content_type):
    """添加 LLM-Wiki frontmatter"""
    
    tags_map = {
        "trend": "趋势, 2026, 时尚",
        "brand": "品牌, 国产, 快时尚",
        "fabric": "面料, 环保, 可持续",
        "supply": "供应链, 代工, 生产",
        "guide": "指南, 穿搭, 消费者"
    }
    
    tags = tags_map.get(content_type, "时尚, wiki")
    date = datetime.now().strftime('%Y-%m-%d')
    
    frontmatter = f"""---
title: {title}
description: {description[:140]}
date: {date}
tags: [{tags}]
aliases: []
status: published
source: auto-generated
---

"""
    
    return frontmatter + content

def process_single_file(raw_file):
    """处理单个原始文件"""
    try:
        with open(raw_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        title = data.get("title", "")
        # 尝试多个字段获取内容
        summary = data.get("summary", "")
        content = data.get("content", "")
        preview = data.get("content_preview", "")
        # 取最长的可用内容
        raw_text = max([summary, content, preview], key=len)
        source = data.get("source", "unknown")
        
        if not title or len(raw_text) < 50:
            log(f"⏭️ 跳过内容过短: {raw_file.name} (len={len(raw_text)})")
            return None
        
        # 分类
        content_type = classify_content(title, raw_text)
        log(f"📂 分类: {content_type} | {title[:50]}...")
        
        # 相关性检测：只处理时尚相关内容
        if not is_fashion_related(title, raw_text):
            log(f"⏭️ 跳过非时尚内容: {title[:50]}...")
            return None
        
        # 构建 prompt - 使用 raw_text 而非 summary
        prompt = build_prompt(title, raw_text, content_type)
        
        # 调用 AI 生成
        generated = call_ai(prompt)
        if not generated:
            log(f"❌ AI 生成失败: {title[:50]}...")
            return None
        
        # 质量评分
        score = quality_score(generated)
        log(f"📊 质量评分: {score}/100")
        
        if score < 70:
            log(f"⏭️ 质量不达标，跳过: {title[:50]}...")
            return None
        
        # 添加双向链接
        generated = add_backlinks(generated)
        
        # 提取描述（从生成的内容中）
        description = ""
        lines = generated.split("\n")
        for line in lines:
            if line.startswith("> "):
                description = line.replace("> ", "").strip()
                break
        if not description:
            description = summary[:140]
        
        # 添加 frontmatter
        markdown = add_frontmatter(generated, title, description, content_type)
        
        # 生成文件名
        filename = generate_filename(content_type, title)
        filepath = OUTPUT_DIR / filename
        
        # 确保目录存在
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # 检查是否已存在相似内容（去重）
        if filepath.exists():
            log(f"⏭️ 文件已存在，跳过: {filename}")
            return None
        
        # 保存
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown)
        
        log(f"✅ 生成成功: {filename} (评分: {score})")
        
        return {
            "filename": filename,
            "title": title,
            "type": content_type,
            "score": score,
            "source": source
        }
        
    except Exception as e:
        log(f"❌ 处理失败 {raw_file.name}: {e}")
        return None

def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fashion Wiki 内容智造引擎")
    parser.add_argument("--input-dir", default=str(INPUT_DIR), help="原始内容目录")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="输出目录")
    parser.add_argument("--min-score", type=int, default=70, help="最低质量评分")
    parser.add_argument("--max-articles", type=int, default=5, help="每日最大生成数")
    parser.add_argument("--dry-run", action="store_true", help="试运行，不保存文件")
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    log("=" * 60)
    log("🚀 Fashion Wiki 内容智造引擎启动")
    log(f"📂 输入: {input_dir}")
    log(f"📂 输出: {output_dir}")
    log(f"📊 最低评分: {args.min_score}")
    log(f"📊 最大生成: {args.max_articles}")
    log("=" * 60)
    
    # 检查 API Key
    if not PERPLEXITY_API_KEY:
        log("⚠️ 警告: PERPLEXITY_API_KEY 未设置，AI 润色将跳过")
    
    # 获取原始文件列表
    raw_files = sorted(input_dir.glob("*.json"))
    log(f"📥 发现 {len(raw_files)} 个原始文件")
    
    if not raw_files:
        log("⚠️ 没有原始文件，退出")
        return
    
    # 处理 - 按类型配额分配，确保多样性
    generated = []
    type_counts = {"trend": 0, "brand": 0, "fabric": 0, "supply": 0, "guide": 0, "concept": 0}
    
    # 每种类型的目标配额 (总计不超过 max_articles)
    type_quota = {
        "trend": min(2, args.max_articles),
        "brand": min(1, max(0, args.max_articles - 2)),
        "fabric": min(1, max(0, args.max_articles - 3)),
        "supply": min(1, max(0, args.max_articles - 4)),
        "guide": min(1, max(0, args.max_articles - 5)),
        "concept": min(1, max(0, args.max_articles - 5))
    }
    
    # 先按类型分组收集可处理的文件
    type_files = {"trend": [], "brand": [], "fabric": [], "supply": [], "guide": [], "concept": []}
    max_scan = min(200, len(raw_files))  # 最多扫描 200 个文件做分类
    
    for raw_file in raw_files[:max_scan]:
        try:
            with open(raw_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            title = data.get("title", "")
            summary = data.get("summary", "")
            raw_text = max([summary, data.get("content", ""), data.get("content_preview", "")], key=len)
            
            if title and len(raw_text) >= 50 and is_fashion_related(title, raw_text):
                content_type = classify_content(title, raw_text)
                type_files[content_type].append(raw_file)
        except:
            continue
    
    log(f"📊 按类型分布: trend={len(type_files['trend'])}, brand={len(type_files['brand'])}, fabric={len(type_files['fabric'])}, supply={len(type_files['supply'])}, guide={len(type_files['guide'])}, concept={len(type_files['concept'])}")
    
    # 按配额处理，确保多样性
    for content_type in ["fabric", "supply", "brand", "guide", "concept", "trend"]:
        quota = type_quota.get(content_type, 0)
        if quota <= 0:
            continue
            
        files = type_files.get(content_type, [])
        log(f"📂 处理 {content_type} 类型: {len(files)} 个候选，配额 {quota}")
        
        for raw_file in files:
            if len(generated) >= args.max_articles:
                break
            if type_counts[content_type] >= quota:
                break
                
            result = process_single_file(raw_file)
            if result and result["score"] >= args.min_score:
                generated.append(result)
                type_counts[content_type] += 1
    
    # 如果还有剩余配额，用趋势文章补充
    remaining = args.max_articles - len(generated)
    if remaining > 0 and type_files["trend"]:
        log(f"📂 用趋势文章补充剩余 {remaining} 个配额")
        for raw_file in type_files["trend"]:
            if len(generated) >= args.max_articles:
                break
            # 跳过已处理的
            if any(g.get("filename") and raw_file.name in str(g.get("filename", "")) for g in generated):
                continue
            result = process_single_file(raw_file)
            if result and result["score"] >= args.min_score:
                generated.append(result)
                type_counts["trend"] += 1
    
    # 汇总
    log("=" * 60)
    log(f"🎉 完成! 生成 {len(generated)} 篇文章")
    for g in generated:
        log(f"   ✅ {g['type']:8} | 评分: {g['score']:2} | {g['title'][:40]}...")
    log("=" * 60)

if __name__ == "__main__":
    main()
