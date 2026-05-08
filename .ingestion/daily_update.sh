#!/bin/bash
# =================================================================
# Fashion Wiki 每日自动更新脚本
# =================================================================
# 建议添加到 crontab: 0 6 * * * /Users/zgeo01/.openclaw/workspace/content/fashion-wiki/.ingestion/daily_update.sh
# =================================================================

set -e

WORKSPACE="/Users/zgeo01/.openclaw/workspace/content/fashion-wiki"
INGESTION_DIR="$WORKSPACE/.ingestion"
LOG_DIR="$INGESTION_DIR/logs"
LOG_FILE="$LOG_DIR/daily_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# =================================================================
# 0. 环境准备
# =================================================================
log "🚀 Fashion Wiki 每日自动更新启动"
log "📁 工作目录: $WORKSPACE"

# 加载 API Keys
if [[ -f "$INGESTION_DIR/.env" ]]; then
    export $(grep -v '^#' "$INGESTION_DIR/.env" | xargs)
    log "✅ 环境变量已加载"
else
    log "⚠️ 警告: .env 文件不存在"
fi

# =================================================================
# 1. 内容采集 (06:00-06:15)
# =================================================================
log "📡 步骤 1: 内容采集..."

cd "$INGESTION_DIR"
python3 ingestion.py >> "$LOG_FILE" 2>&1

RAW_COUNT=$(ls -1 "$INGESTION_DIR/raw"/*.json 2>/dev/null | wc -l)
log "📥 原始内容: $RAW_COUNT 条"

# =================================================================
# 2. AI 内容智造 (06:15-06:45)
# =================================================================
log "🤖 步骤 2: AI 内容智造..."

cd "$INGESTION_DIR"
python3 content_generator.py \
    --input-dir "$INGESTION_DIR/raw" \
    --output-dir "$WORKSPACE/content" \
    --min-score 70 \
    --max-articles 5 \
    >> "$LOG_FILE" 2>&1

NEW_COUNT=$(find "$WORKSPACE/content" -name "*.md" -not -path "*/.ingestion/*" | wc -l)
log "📄 总文章数: $NEW_COUNT 篇"

# =================================================================
# 3. 更新全局索引 (06:45-06:50)
# =================================================================
log "📝 步骤 3: 更新全局索引..."

cd "$WORKSPACE"
python3 "$INGESTION_DIR/update_index.py" >> "$LOG_FILE" 2>&1

# =================================================================
# 4. Git 提交并推送 (06:50-07:00)
# =================================================================
log "📦 步骤 4: Git 提交..."

cd "$WORKSPACE"
git add content/ "$INGESTION_DIR/logs/"

# 检查是否有变更
if git diff --cached --quiet; then
    log "⏭️ 无变更，跳过提交"
else
    git commit -m "auto: $(date +%Y-%m-%d) 内容更新

- 新增文章: 查看日志
- 采集时间: $(date '+%Y-%m-%d %H:%M')
- 运行主机: $(hostname)"
    
    git push origin main >> "$LOG_FILE" 2>&1
    log "✅ 代码已推送至 GitHub"
fi

# =================================================================
# 5. 清理旧文件 (07:00)
# =================================================================
log "🧹 步骤 5: 清理过期文件..."

# 保留最近 7 天的原始文件
find "$INGESTION_DIR/raw" -name "*.json" -mtime +7 -delete 2>/dev/null || true

# 保留最近 30 天的日志
find "$LOG_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null || true

# =================================================================
# 6. 通知与报告 (07:00-07:05)
# =================================================================
log "📊 步骤 6: 生成日报..."

# 统计信息
ARTICLE_COUNT=$(find "$WORKSPACE/content" -name "*.md" -not -path "*/.ingestion/*" | wc -l)
TODAY_FILES=$(find "$WORKSPACE/content" -name "*$(date +%Y%m%d)*.md" 2>/dev/null | wc -l)

REPORT="Fashion Wiki 每日更新报告 ✅
日期: $(date '+%Y-%m-%d %H:%M')
新增文章: $TODAY_FILES 篇
总文章数: $ARTICLE_COUNT 篇
采集来源: $RAW_COUNT 条
日志文件: fashion-wiki/.ingestion/logs/$(basename $LOG_FILE)
访问地址: https://fashion-wiki-zgeo.vercel.app"

log "$REPORT"

# 飞书通知
if [[ -n "$FEISHU_WEBHOOK" ]]; then
    curl -s -X POST "$FEISHU_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "{
            \"msg_type\": \"text\",
            \"content\": {
                \"text\": \"$REPORT\"
            }
        }" > /dev/null 2>&1 || true
    log "📱 飞书通知已发送"
fi

log "🎉 全部完成!"

exit 0
