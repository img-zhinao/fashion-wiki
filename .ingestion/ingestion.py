#!/usr/bin/env python3
"""
Fashion Wiki 内容采集管道 (Content Ingestion Pipeline)
多源采集 → 原始存储 → LLM-Wiki 格式化 → 人工审核队列

数据源：
1. Perplexity API — 实时时尚问答与深度研究
2. RSS 聚合 — WWD, Business of Fashion, 蝶讯网等
3. 品牌监测 — 品牌官网新闻稿自动抓取
4. 社交媒体 — X/Twitter 时尚趋势话题
5. 行业报告 — 时装周日程、贸易数据

作者: OpsAgent
版本: v1.0
"""

import os
import sys
import json
import time
import hashlib
import logging  # 先导入 logging
import requests
import xml.etree.ElementTree as ET  # 内置 RSS 解析，替代 feedparser
import html

# 尝试导入 feedparser，失败则使用内置解析器
try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False
    logging.warning("feedparser 未安装，使用内置 XML 解析器")
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import logging

# 配置
BASE_DIR = Path("/Users/zgeo01/.openclaw/workspace/content/fashion-wiki/.ingestion")
RAW_DIR = BASE_DIR / "raw"
PROCESSED_DIR = BASE_DIR / "processed"
LOG_DIR = BASE_DIR / "logs"
TEMPLATES_DIR = BASE_DIR / "templates"
FEEDS_DIR = BASE_DIR / "feeds"

# 确保目录存在
for d in [RAW_DIR, PROCESSED_DIR, LOG_DIR, TEMPLATES_DIR, FEEDS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"ingestion_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FashionContentIngestion:
    """Fashion Wiki 内容采集器"""
    
    def __init__(self):
        self.perplexity_api_key = os.getenv("PERPLEXITY_API_KEY", "")
        self.kimi_api_key = os.getenv("KIMI_API_KEY", "")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "FashionWikiBot/1.0 (Content Aggregation for AI Knowledge Base)"
        })
    
    # ═══════════════════════════════════════════
    # 数据源 1: Perplexity API (深度研究)
    # ═══════════════════════════════════════════
    
    def fetch_perplexity(self, query: str, category: str = "general") -> Dict:
        """
        通过 Perplexity API 获取实时时尚研究内容
        
        Args:
            query: 研究问题
            category: 内容分类 (brand/fabric/trend/supply/guide)
        """
        if not self.perplexity_api_key:
            logger.warning("PERPLEXITY_API_KEY 未配置，跳过 Perplexity 采集")
            return {}
        
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.perplexity_api_key}",
            "Content-Type": "application/json"
        }
        
        # 为 Fashion Wiki 优化的 system prompt
        system_prompt = """你是 Fashion Wiki 的专业内容研究员。你的任务是获取权威、结构化、可验证的时尚行业信息。

输出格式要求：
1. 先用一句话总结核心结论（One-Liner）
2. 用表格呈现对比数据
3. 列出关键事实和数据来源
4. 标注信息时效性

请确保信息：
- 来自权威来源（品牌官网、行业报告、主流媒体）
- 包含具体数据和案例
- 区分事实和观点
- 标注不确定性（如"据 2025 年数据"）"""
        
        payload = {
            "model": "sonar-pro",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            "max_tokens": 4000,
            "temperature": 0.1,
            "search_recency_filter": "month"  # 优先近期信息
        }
        
        try:
            resp = self.session.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            
            content = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])
            
            # 生成文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_query = hashlib.md5(query.encode()).hexdigest()[:8]
            filename = f"perplexity_{category}_{safe_query}_{timestamp}.json"
            
            result = {
                "source": "perplexity",
                "query": query,
                "category": category,
                "timestamp": datetime.now().isoformat(),
                "content": content,
                "citations": citations,
                "model": "sonar-pro"
            }
            
            filepath = RAW_DIR / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Perplexity 采集完成: {query[:50]}... → {filename}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Perplexity 采集失败: {query[:50]}... | 错误: {e}")
            return {}
    
    # ═══════════════════════════════════════════
    # 数据源 2: RSS 聚合 (行业媒体)
    # ═══════════════════════════════════════════
    
    def fetch_rss_feeds(self) -> List[Dict]:
        """抓取时尚行业 RSS 源（使用内置 XML 解析器）"""
        
        feeds = {
            "wwd": "https://wwd.com/feed/",
            "bof": "https://www.businessoffashion.com/feed/",
            "vogue": "https://www.vogue.com/feed/",
            "hypebeast": "https://hypebeast.com/feed",
            "highsnobiety": "https://www.highsnobiety.com/feed/",
            "fashionunited": "https://fashionunited.com/rss",
            "just_style": "https://www.just-style.com/rss/",
            "elle_china": "https://www.ellechina.com/rss/",
            "grazia_china": "https://www.grazia.com.cn/rss/",
            "yoka": "https://www.yoka.com/rss/",
        }
        
        results = []
        cutoff = datetime.now() - timedelta(days=3)
        
        for source_name, feed_url in feeds.items():
            try:
                resp = self.session.get(feed_url, timeout=15)
                if resp.status_code != 200:
                    logger.warning(f"⚠️ RSS 源返回 {resp.status_code}: {source_name}")
                    continue
                
                # 内置 XML 解析
                root = ET.fromstring(resp.content)
                
                # RSS 2.0 格式
                channel = root.find("channel")
                if channel is None:
                    # 可能是 Atom 格式
                    logger.warning(f"⚠️ 非标准 RSS 格式，跳过: {source_name}")
                    continue
                
                entries = channel.findall("item")
                logger.info(f"📡 RSS 源 {source_name}: {len(entries)} 条原始条目")
                
                for entry in entries[:10]:  # 每个源最多 10 条
                    title_elem = entry.find("title")
                    link_elem = entry.find("link")
                    summary_elem = entry.find("description")
                    pub_date_elem = entry.find("pubDate")
                    
                    title = html.unescape(title_elem.text) if title_elem is not None and title_elem.text else ""
                    link = link_elem.text if link_elem is not None and link_elem.text else ""
                    summary = html.unescape(summary_elem.text) if summary_elem is not None and summary_elem.text else ""
                    pub_date = pub_date_elem.text if pub_date_elem is not None and pub_date_elem.text else ""
                    
                    item = {
                        "source": f"rss_{source_name}",
                        "title": title,
                        "link": link,
                        "summary": summary,
                        "published": pub_date,
                        "timestamp": datetime.now().isoformat(),
                        "category": self._classify_rss_content(title, summary)
                    }
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_title = hashlib.md5(item["title"].encode()).hexdigest()[:8]
                    filename = f"rss_{source_name}_{safe_title}_{timestamp}.json"
                    
                    filepath = RAW_DIR / filename
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(item, f, ensure_ascii=False, indent=2)
                    
                    results.append(item)
                
                logger.info(f"✅ RSS 采集完成: {source_name} ({len(results)} 条新)")
                
            except Exception as e:
                logger.error(f"❌ RSS 采集失败: {source_name} | 错误: {e}")
        
        return results
    
    def _classify_rss_content(self, title: str, summary: str) -> str:
        """根据标题和摘要分类内容"""
        text = f"{title} {summary}".lower()
        
        if any(k in text for k in ["brand", "品牌", "launch", "发布", "collection", "系列"]):
            return "brand"
        elif any(k in text for k in ["fabric", "面料", "material", "textile", "纤维"]):
            return "fabric"
        elif any(k in text for k in ["trend", "趋势", "fashion week", "时装周", "season", "春夏", "秋冬"]):
            return "trend"
        elif any(k in text for k in ["supply", "供应链", "factory", "工厂", "manufacturing", "生产"]):
            return "supply"
        elif any(k in text for k in ["retail", "零售", "sales", "消费", "market", "market"]):
            return "market"
        else:
            return "general"
    
    # ═══════════════════════════════════════════
    # 数据源 3: 品牌新闻稿监测
    # ═══════════════════════════════════════════
    
    def monitor_brand_press(self, brand_websites: List[Dict]) -> List[Dict]:
        """
        监测品牌官网新闻/媒体中心
        
        Args:
            brand_websites: [{"brand": "UR", "domain": "ur.com", "news_path": "/news"}]
        """
        results = []
        
        for brand_info in brand_websites:
            try:
                brand = brand_info["brand"]
                domain = brand_info["domain"]
                news_url = f"https://{domain}{brand_info.get('news_path', '/news')}"
                
                # 这里简化处理，实际可扩展为 sitemap 解析或 RSS 探测
                resp = self.session.get(news_url, timeout=15, allow_redirects=True)
                
                item = {
                    "source": f"brand_press_{brand}",
                    "brand": brand,
                    "url": news_url,
                    "status_code": resp.status_code,
                    "timestamp": datetime.now().isoformat(),
                    "content_preview": resp.text[:2000] if resp.status_code == 200 else ""
                }
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"brandpress_{brand}_{timestamp}.json"
                
                filepath = RAW_DIR / filename
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(item, f, ensure_ascii=False, indent=2)
                
                results.append(item)
                logger.info(f"✅ 品牌新闻监测: {brand} (状态: {resp.status_code})")
                
            except Exception as e:
                logger.error(f"❌ 品牌新闻监测失败: {brand_info.get('brand', 'unknown')} | 错误: {e}")
        
        return results
    
    # ═══════════════════════════════════════════
    # 数据源 4: 社交媒体趋势 (X/Twitter)
    # ═══════════════════════════════════════════
    
    def fetch_social_trends(self) -> List[Dict]:
        """
        抓取时尚相关社交媒体趋势
        注意: 需要配置 X API Bearer Token
        """
        bearer_token = os.getenv("X_BEARER_TOKEN", "")
        
        if not bearer_token:
            logger.warning("X_BEARER_TOKEN 未配置，跳过社交媒体采集")
            return []
        
        # 时尚相关查询
        queries = [
            "fashion trend 2026",
            "sustainable fashion",
            "quiet luxury",
            "new chinese style fashion",
            "面料 趋势",
            "服装品牌 新品"
        ]
        
        results = []
        headers = {"Authorization": f"Bearer {bearer_token}"}
        
        for query in queries:
            try:
                url = "https://api.twitter.com/2/tweets/search/recent"
                params = {
                    "query": query,
                    "max_results": 10,
                    "tweet.fields": "created_at,public_metrics,author_id",
                    "expansions": "author_id",
                    "user.fields": "username,public_metrics"
                }
                
                resp = self.session.get(url, headers=headers, params=params, timeout=30)
                
                if resp.status_code == 200:
                    data = resp.json()
                    tweets = data.get("data", [])
                    
                    for tweet in tweets:
                        item = {
                            "source": "twitter",
                            "query": query,
                            "tweet_id": tweet["id"],
                            "text": tweet["text"],
                            "created_at": tweet.get("created_at", ""),
                            "metrics": tweet.get("public_metrics", {}),
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        results.append(item)
                    
                    logger.info(f"✅ Twitter 采集: {query} ({len(tweets)} 条)")
                else:
                    logger.warning(f"⚠️ Twitter API 返回 {resp.status_code}: {resp.text[:200]}")
                
                time.sleep(1)  # 避免速率限制
                
            except Exception as e:
                logger.error(f"❌ Twitter 采集失败: {query} | 错误: {e}")
        
        # 保存汇总
        if results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"twitter_trends_{timestamp}.json"
            filepath = RAW_DIR / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
        
        return results
    
    # ═══════════════════════════════════════════
    # 数据源 5: 时装周/展会日程
    # ═══════════════════════════════════════════
    
    def fetch_fashion_events(self) -> List[Dict]:
        """获取主要时装周和展会日程"""
        
        # 主要时装周 RSS/ical 源
        events_sources = {
            "cfda": "https://cfda.com/events/feed",  # 美国设计师协会
            "british_fashion_council": "https://britishfashioncouncil.co.uk/events/feed",
            "federation": "https://modeaparis.com/en/events/feed",  # 法国时装工会
        }
        
        results = []
        
        for source_name, url in events_sources.items():
            try:
                resp = self.session.get(url, timeout=15)
                
                item = {
                    "source": f"event_{source_name}",
                    "url": url,
                    "status_code": resp.status_code,
                    "timestamp": datetime.now().isoformat(),
                    "content_preview": resp.text[:3000] if resp.status_code == 200 else ""
                }
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"event_{source_name}_{timestamp}.json"
                
                filepath = RAW_DIR / filename
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(item, f, ensure_ascii=False, indent=2)
                
                results.append(item)
                logger.info(f"✅ 活动日程采集: {source_name}")
                
            except Exception as e:
                logger.error(f"❌ 活动日程采集失败: {source_name} | 错误: {e}")
        
        return results
    
    # ═══════════════════════════════════════════
    # 内容处理: 原始 → LLM-Wiki 格式
    # ═══════════════════════════════════════════
    
    def process_to_llm_wiki(self, raw_file: Path) -> Optional[Dict]:
        """
        将原始内容转换为 LLM-Wiki 格式草稿
        实际应由 ContentAgent / Kimi 完成润色
        """
        try:
            with open(raw_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            source = data.get("source", "unknown")
            category = data.get("category", "general")
            
            # 生成 LLM-Wiki 模板
            template = self._generate_wiki_template(source, category, data)
            
            # 保存到 processed 队列
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"draft_{source}_{timestamp}.md"
            filepath = PROCESSED_DIR / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(template)
            
            logger.info(f"✅ 生成 LLM-Wiki 草稿: {filepath.name}")
            return {"draft_file": str(filepath), "source": source}
            
        except Exception as e:
            logger.error(f"❌ 处理失败: {raw_file.name} | 错误: {e}")
            return None
    
    def _generate_wiki_template(self, source: str, category: str, data: Dict) -> str:
        """生成 LLM-Wiki Markdown 模板"""
        
        title = data.get("title", data.get("query", "未命名"))
        content = data.get("content", data.get("summary", ""))
        
        category_map = {
            "brand": "brands",
            "fabric": "fabrics",
            "trend": "trends",
            "supply": "supply-chain",
            "market": "concepts",
            "general": "concepts"
        }
        
        folder = category_map.get(category, "concepts")
        
        template = f"""---
title: {title}
description: 一句话摘要（需要 ContentAgent 补充）
date: {datetime.now().strftime('%Y-%m-%d')}
tags: [{category}, fashion, wiki]
aliases: []
source: {source}
status: draft
---

# {title}

> 一句话摘要（需要 ContentAgent 补充，不超过 140 字）

---

## 原始内容

**来源**: {source}
**采集时间**: {data.get('timestamp', datetime.now().isoformat())}

{content[:3000] if content else "（原始内容待整理）"}

---

## 待整理要点

- [ ] 提取关键事实和数据
- [ ] 验证信息来源可靠性
- [ ] 补充 One-Liner 摘要
- [ ] 添加关联页面双向链接
- [ ] 转换为表格/FAQ 格式
- [ ] 标注信息时效性

---

## 关联阅读（待补充）

- [[相关页面]] | 一句话描述

---

*状态: 草稿 | 来源: {source} | 采集: {datetime.now().strftime('%Y-%m-%d')}*
"""
        return template
    
    # ═══════════════════════════════════════════
    # 主运行流程
    # ═══════════════════════════════════════════
    
    def run_full_ingestion(self):
        """执行完整采集流程"""
        
        logger.info("🚀 Fashion Wiki 内容采集管道启动")
        logger.info(f"📁 原始目录: {RAW_DIR}")
        logger.info(f"📁 处理队列: {PROCESSED_DIR}")
        
        # 1. Perplexity 深度研究
        perplexity_queries = [
            {"query": "2026 年春夏中国服装流行趋势，新中式、多巴胺色彩、可持续面料", "category": "trend"},
            {"query": "中国本土服装品牌 GEO 优化现状，UR、太平鸟、ICICLE 在 AI 平台的可见性", "category": "brand"},
            {"query": "天丝、莱赛尔、再生涤纶等可持续面料的技术参数和市场应用", "category": "fabric"},
            {"query": "广州十三行、杭州四季青服装供应链最新动态，小单快反模式", "category": "supply"},
        ]
        
        for q in perplexity_queries:
            self.fetch_perplexity(q["query"], q["category"])
            time.sleep(2)  # 避免速率限制
        
        # 2. RSS 聚合
        self.fetch_rss_feeds()
        
        # 3. 品牌新闻监测
        brands_to_monitor = [
            {"brand": "UR", "domain": "ur.com", "news_path": "/news"},
            {"brand": "太平鸟", "domain": "peacebird.com", "news_path": "/news"},
            {"brand": "ICICLE", "domain": "icicle.com", "news_path": "/news"},
        ]
        self.monitor_brand_press(brands_to_monitor)
        
        # 4. 社交媒体趋势
        self.fetch_social_trends()
        
        # 5. 时装周日程
        self.fetch_fashion_events()
        
        # 6. 处理原始内容为 LLM-Wiki 草稿
        logger.info("📝 开始处理原始内容为 LLM-Wiki 草稿...")
        raw_files = sorted(RAW_DIR.glob("*.json"))
        
        for raw_file in raw_files[-20:]:  # 只处理最近 20 个
            self.process_to_llm_wiki(raw_file)
        
        # 7. 生成日报
        self._generate_daily_report()
        
        logger.info("✅ 采集流程完成")
    
    def _generate_daily_report(self):
        """生成每日采集报告"""
        
        today = datetime.now().strftime("%Y-%m-%d")
        raw_files = list(RAW_DIR.glob(f"*{today.replace('-', '')}*.json"))
        
        report = {
            "date": today,
            "total_raw": len(raw_files),
            "by_source": {},
            "by_category": {}
        }
        
        for f in raw_files:
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                
                source = data.get("source", "unknown")
                category = data.get("category", "general")
                
                report["by_source"][source] = report["by_source"].get(source, 0) + 1
                report["by_category"][category] = report["by_category"].get(category, 0) + 1
            except:
                pass
        
        report_file = LOG_DIR / f"daily_report_{today}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📊 日报生成: {report_file.name}")
        logger.info(f"   总计采集: {report['total_raw']} 条")
        logger.info(f"   按来源: {report['by_source']}")
        logger.info(f"   按分类: {report['by_category']}")


def main():
    """主入口"""
    ingestion = FashionContentIngestion()
    ingestion.run_full_ingestion()


if __name__ == "__main__":
    main()
