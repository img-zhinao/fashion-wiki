#!/bin/bash
# =================================================================
# Fashion Wiki 每日自动更新脚本 (修复版)
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
log "🤖 步骤 2: AI 内容智造 (Perplexity)..."

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
git add content/ "$INGESTION_DIR/content_generator.py" "$INGESTION_DIR/update_index.py" "$INGESTION_DIR/ingestion.py" "$INGESTION_DIR/daily_update.sh"

# 检查是否有变更
if git diff --cached --quiet; then
    log "⏭️ 无新文章，跳过提交"
else
    git commit -m "auto: $(date +%Y-%m-%d) 内容更新

- AI 自动生成 $(date '+%H:%M')
- 采集来源: $RAW_COUNT 条
- 运行主机: $(hostname)"
    
    git push origin main >> "$LOG_FILE" 2>&1
    log "✅ 代码已推送至 GitHub"
fi

# =================================================================
# 5. 生成日报 (07:00-07:05)
# =================================================================
log "📊 步骤 5: 生成日报..."

ARTICLE_COUNT=$(find "$WORKSPACE/content" -name "*.md" -not -path "*/.ingestion/*" | wc -l)
TODAY_FILES=$(find "$WORKSPACE/content" -name "*$(date +%Y%m%d)*.md" 2>/dev/null | wc -l)

REPORT="Fashion Wiki 每日更新报告 ✅
日期: $(date '+%Y-%m-%d %H:%M')
新增文章: $TODAY_FILES 篇
总文章数: $ARTICLE_COUNT 篇
采集来源: $RAW_COUNT 条
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
