# Fashion Wiki 内容自动化更新管道
## 每日高质量内容自动更新方案

---

## 🎯 核心目标

**让 Fashion Wiki 像新闻网站一样，每天自动新增 2-5 篇高质量内容，无需人工干预。**

```
第 1 天: 12 篇
第 7 天: 12 + 21 = 33 篇
第 30 天: 12 + 90 = 102 篇
第 90 天: 12 + 270 = 282 篇
```

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    每日自动更新管道                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  06:00 ┃ 内容采集层                                              │
│  ├── RSS 聚合器 (WWD/BoF/Vogue/Hypebeast)                       │
│  ├── Perplexity 深度研究 (时尚趋势/品牌动态)                     │
│  ├── 品牌官网监测 (UR/太平鸟/ICICLE 新闻)                       │
│  └── 社交媒体热榜 (X/小红书趋势话题)                             │
│                                                                  │
│  06:30 ┃ AI 内容智造层                                           │
│  ├── 原始内容 → Kimi 自动润色                                    │
│  ├── 生成 LLM-Wiki 格式 Markdown                                │
│  ├── 自动补充 One-Liner + 双向链接                              │
│  └── 质量评分 (低于 70 分淘汰)                                    │
│                                                                  │
│  07:00 ┃ 人工审核层 (可选)                                       │
│  ├── 飞书/企业微信通知待审核内容                                │
│  ├── 人工 5 分钟快速审核                                         │
│  └── 一键通过/驳回/修改                                          │
│                                                                  │
│  07:30 ┃ 自动发布层                                              │
│  ├── Git 自动提交 → GitHub                                       │
│  ├── Vercel 自动构建 + 部署                                      │
│  └── RAGFeedAgent 主动投喂 AI 引擎                               │
│                                                                  │
│  08:00 ┃ 效果监测层                                              │
│  ├── AIRefWatcher 监测新内容被 AI 引用情况                       │
│  ├── 生成每日内容效果报告                                        │
│  └── 反馈优化采集策略                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 实施步骤

### 第一步：完善采集管道 (已部分实现)

当前 `ingestion.py` 已能采集 RSS，需要增强：

```bash
# 1. 配置 Perplexity API (已实现)
export PERPLEXITY_API_KEY="pplx-..."

# 2. 配置 Kimi API (用于内容润色)
export KIMI_API_KEY="sk-..."

# 3. 扩充 RSS 源列表
# 在 config.json 中添加更多中文时尚媒体
```

**扩充后的 RSS 源：**

| 类型 | 来源 | 频率 |
|------|------|------|
| 国际趋势 | WWD, BoF, Vogue | 每 4 小时 |
| 潮流文化 | Hypebeast, Highsnobiety | 每 4 小时 |
| 中文时尚 | ELLE China, YOKA, 瑞丽 | 每 4 小时 |
| 行业数据 | Fashion United, Just Style | 每 12 小时 |
| 品牌官方 | UR, 太平鸟, ICICLE | 每日 |
| 社交媒体 | X #fashiontrend, 小红书热榜 | 每日 |

---

### 第二步：AI 内容智造系统

创建 `content_generator.py`：

```python
# content_generator.py - AI 内容智造核心

import os
import json
from datetime import datetime
from pathlib import Path

class FashionContentGenerator:
    """将原始内容转化为 LLM-Wiki 格式的高质量文章"""
    
    def __init__(self):
        self.kimi_api_key = os.getenv("KIMI_API_KEY")
        
    def generate_article(self, raw_content: dict) -> dict:
        """
        输入: 原始采集内容
        输出: LLM-Wiki 格式的 Markdown + 元数据
        """
        
        # 1. 分析内容类型
        content_type = self._classify(raw_content)
        
        # 2. 调用 Kimi 生成结构化内容
        prompt = self._build_prompt(raw_content, content_type)
        article = self._call_kimi(prompt)
        
        # 3. 质量评分
        score = self._quality_score(article)
        
        if score < 70:
            return None  # 淘汰低质量内容
            
        # 4. 自动补充双向链接
        article = self._add_backlinks(article)
        
        # 5. 生成 frontmatter
        markdown = self._to_llm_wiki(article, content_type)
        
        return {
            "markdown": markdown,
            "score": score,
            "type": content_type,
            "source": raw_content["source"]
        }
    
    def _classify(self, content: dict) -> str:
        """判断内容类型"""
        title = content.get("title", "")
        if any(k in title for k in ["趋势", "流行", "色彩", "时装周"]):
            return "trend"
        elif any(k in title for k in ["面料", "纤维", "材质"]):
            return "fabric"
        elif any(k in title for k in ["品牌", "联名", "新品"]):
            return "brand"
        elif any(k in title for k in ["供应链", "工厂", "采购"]):
            return "supply"
        else:
            return "guide"
    
    def _build_prompt(self, raw: dict, content_type: str) -> str:
        """构建 Kimi prompt"""
        
        prompts = {
            "trend": """你是 Fashion Wiki 的高级编辑。请基于以下时尚行业资讯，撰写一篇 LLM-Wiki 格式的趋势文章。

要求：
1. 标题用中文，一句话摘要 (description) 不超过 140 字
2. 开头用 ">" 引用给出核心结论
3. 用表格呈现对比数据（颜色、面料、价格带等）
4. 包含 "关联阅读" 部分，列出相关话题
5. 标注数据来源和时效性
6. 使用 Markdown 格式，不要输出任何其他内容

原始内容：
{title}
{summary}
""",
            "brand": """你是 Fashion Wiki 的品牌研究员。请基于以下品牌资讯，撰写一篇品牌知识卡片。

要求：
1. 一句话定位品牌
2. 品牌档案表格（创立时间、总部、价格带等）
3. 核心优势列表
4. 与竞品对比表格
5. GEO 优化建议（如何让 AI 更好引用该品牌）
6. 使用 Markdown 格式

原始内容：
{title}
{summary}
""",
            "fabric": """你是 Fashion Wiki 的面料科学家。请基于以下面料资讯，撰写一篇面料百科。

要求：
1. 一句话定义面料
2. 与其他面料对比表格
3. 核心性能优势（透气、保暖等）
4. 应用场景
5. 护理方法表格
6. 使用 Markdown 格式

原始内容：
{title}
{summary}
"""
        }
        
        template = prompts.get(content_type, prompts["trend"])
        return template.format(
            title=raw.get("title", ""),
            summary=raw.get("summary", raw.get("content", ""))
        )
    
    def _call_kimi(self, prompt: str) -> str:
        """调用 Kimi API 生成内容"""
        # 实际实现需要调用 Kimi API
        # 这里简化处理
        return "generated_content"
    
    def _quality_score(self, article: str) -> int:
        """
        质量评分算法：
        - 包含表格: +20
        - 包含 One-Liner: +20
        - 包含双向链接: +10
        - 字数 > 500: +20
        - 包含数据来源: +10
        - 包含时间标注: +10
        - 语言流畅度: +10 (人工/AI评估)
        """
        score = 0
        if "|" in article: score += 20
        if ">" in article: score += 20
        if "[[" in article: score += 10
        if len(article) > 500: score += 20
        if "来源" in article or "source" in article: score += 10
        if "202" in article: score += 10
        return min(100, score)
    
    def _add_backlinks(self, article: str) -> str:
        """自动补充 Fashion Wiki 已有的双向链接"""
        # 扫描文章中提到的已知品牌/面料/概念
        known_entities = {
            "UR": "[[ur]]",
            "太平鸟": "[[peacebird]]",
            "天丝": "[[tencel]]",
            "美利奴羊毛": "[[merino-wool]]",
            "GEO": "[[geo-fashion]]",
            "2026 春夏": "[[spring-summer-2026]]",
        }
        
        for entity, link in known_entities.items():
            if entity in article and link not in article:
                article = article.replace(entity, f"{entity} ({link})", 1)
        
        return article
    
    def _to_llm_wiki(self, article: str, content_type: str) -> str:
        """添加 LLM-Wiki frontmatter"""
        
        folder_map = {
            "trend": "trends",
            "brand": "brands",
            "fabric": "fabrics",
            "supply": "supply-chain",
            "guide": "guides"
        }
        
        frontmatter = f"""---
title: {self._extract_title(article)}
description: {self._extract_summary(article)}
date: {datetime.now().strftime('%Y-%m-%d')}
tags: [{content_type}, fashion, wiki]
aliases: []
status: published
---

"""
        
        return frontmatter + article
    
    def _extract_title(self, article: str) -> str:
        # 从文章中提取标题
        lines = article.split("\n")
        for line in lines:
            if line.startswith("# "):
                return line.replace("# ", "").strip()
        return "Untitled"
    
    def _extract_summary(self, article: str) -> str:
        # 从文章中提取摘要
        lines = article.split("\n")
        for line in lines:
            if line.startswith("> "):
                return line.replace("> ", "").strip()[:140]
        return ""
```

---

### 第三步：自动化运行脚本

创建 `daily_update.sh`：

```bash
#!/bin/bash
# Fashion Wiki 每日自动更新脚本
# 建议添加到 crontab: 0 6 * * * /path/to/daily_update.sh

set -e

WORKSPACE="/Users/zgeo01/.openclaw/workspace/content/fashion-wiki"
LOG_FILE="$WORKSPACE/logs/daily_update_$(date +%Y%m%d).log"

mkdir -p "$WORKSPACE/logs"

echo "🚀 [$(date)] Fashion Wiki 每日更新启动" | tee -a "$LOG_FILE"

# 1. 内容采集
echo "📡 步骤 1: 内容采集..." | tee -a "$LOG_FILE"
cd "$WORKSPACE/.ingestion"
python3 ingestion.py >> "$LOG_FILE" 2>&1

# 2. AI 内容生成
echo "🤖 步骤 2: AI 内容智造..." | tee -a "$LOG_FILE"
cd "$WORKSPACE"
python3 content_generator.py \
  --input-dir "$WORKSPACE/.ingestion/raw" \
  --output-dir "$WORKSPACE/content" \
  --min-score 70 \
  --max-articles 5 >> "$LOG_FILE" 2>&1

# 3. 更新全局索引
echo "📝 步骤 3: 更新全局索引..." | tee -a "$LOG_FILE"
python3 update_index.py >> "$LOG_FILE" 2>&1

# 4. Git 提交
echo "📦 步骤 4: Git 提交..." | tee -a "$LOG_FILE"
cd "$WORKSPACE"
git add content/
git commit -m "auto: $(date +%Y-%m-%d) 内容更新" || true
git push origin main >> "$LOG_FILE" 2>&1

# 5. 通知（飞书/企业微信）
NEW_COUNT=$(ls -1 "$WORKSPACE/content"/*.md 2>/dev/null | wc -l)
echo "✅ [$(date)] 更新完成，当前共 ${NEW_COUNT} 篇文章" | tee -a "$LOG_FILE"

# 如果有飞书 webhook，发送通知
if [ -n "$FEISHU_WEBHOOK" ]; then
    curl -s -X POST "$FEISHU_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "{
            \"msg_type\": \"text\",
            \"content\": {
                \"text\": \"Fashion Wiki 每日更新完成 ✅\\n日期: $(date '+%Y-%m-%d')\\n新增文章: 查看日志\\n总文章数: ${NEW_COUNT}\\n访问: https://fashion-wiki-zgeo.vercel.app\"
            }
        }" > /dev/null 2>&1 || true
fi

echo "🎉 [$(date)] 全部完成" | tee -a "$LOG_FILE"
```

---

### 第四步：质量保障机制

| 关卡 | 机制 | 作用 |
|------|------|------|
| **采集过滤** | 关键词黑名单 + 重复检测 | 过滤垃圾内容 |
| **AI 评分** | 质量评分算法 (0-100) | 低于 70 分淘汰 |
| **人工审核** | 飞书通知 + 一键确认 | 重要文章人工把关 |
| **发布后监测** | AIRefWatcher 追踪引用 | 验证内容被 AI 引用情况 |
| **反馈循环** | 高引用内容 → 深化扩展 | 优化内容策略 |

---

### 第五步：扩展内容类型

| 类型 | 每日目标 | 生成方式 |
|------|---------|---------|
| **趋势快讯** | 1-2 篇 | RSS + Perplexity 自动生成 |
| **品牌动态** | 1 篇 | 品牌新闻监测 + AI 改写 |
| **面料百科** | 1 篇 | 行业报告 + AI 结构化 |
| **穿搭指南** | 1 篇 | 趋势数据 + AI 场景化 |
| **深度报告** | 每周 1 篇 | 多源数据 + Kimi 深度分析 |

---

## 📊 效果预期

| 时间 | 文章数 | AI 引用指数 | 覆盖品牌 | 覆盖面料 |
|------|--------|------------|---------|---------|
| **Day 1** | 12 | 基准 | 2 | 2 |
| **Day 7** | 33 | +50% | 5 | 5 |
| **Day 30** | 102 | +200% | 15 | 12 |
| **Day 90** | 282 | +500% | 40 | 30 |

---

## 🚀 立即实施

### 今天可以做的：

1. ✅ 配置 `PERPLEXITY_API_KEY` 和 `KIMI_API_KEY`
2. ✅ 编写 `content_generator.py`（核心 AI 润色）
3. ✅ 编写 `daily_update.sh`（每日自动运行）
4. ✅ 添加 crontab：`0 6 * * * /path/to/daily_update.sh`

### 明天开始的自动流程：

```
每天 06:00 ┃ 自动采集 + 生成 + 发布
每天 08:00 ┃ 飞书通知更新摘要
每天 15:00 ┃ AIRefWatcher 监测新内容引用情况
```

---

## ❓ 需要我现在生成的文件

- **A)** `content_generator.py` - AI 内容智造核心（完整可运行版本）
- **B)** `daily_update.sh` - 每日自动更新脚本（完整版本）
- **C)** `update_index.py` - 自动更新全局索引脚本
- **D)** 飞书通知配置指南

选一个，我立即生成 🎯

---

*方案版本: v1.0 | 2026-05-08 | Fashion Wiki 自动更新系统设计*