# Fashion Wiki 部署指南

## 概述
将 Fashion Wiki 从本地 Mac Mini 部署到 Vercel，实现自动构建和全球 CDN 加速。

---

## 第一步：创建 GitHub 仓库

### 方法 A：通过浏览器（推荐）

1. 访问 https://github.com/new
2. 仓库名称：`fashion-wiki`
3. 设置为 **Public**（Vercel 免费部署需要公开仓库）
4. 不要初始化 README（本地已有）
5. 点击 **Create repository**

### 方法 B：命令行（需要 GitHub CLI）

```bash
# 安装 GitHub CLI
brew install gh

# 登录
gh auth login

# 创建仓库
gh repo create fashion-wiki --public --source=. --remote=origin --push
```

---

## 第二步：推送本地代码到 GitHub

如果通过浏览器创建，复制以下命令执行：

```bash
cd /Users/zgeo01/.openclaw/workspace/content/fashion-wiki

# 添加你的 GitHub 仓库作为 origin
git remote add origin https://github.com/你的用户名/fashion-wiki.git

# 推送到 main 分支
git branch -M main
git push -u origin main
```

---

## 第三步：Vercel 部署

### 方法 A：Vercel CLI（推荐，最快）

```bash
# 安装 Vercel CLI
npm i -g vercel

# 登录（浏览器会自动打开）
vercel login

# 部署
cd /Users/zgeo01/.openclaw/workspace/content/fashion-wiki
vercel --prod

# 按照提示：
# - 选择 "Link to existing project" 或 "Create new"
# - 确认项目设置
```

### 方法 B：Vercel 网站 + GitHub 集成

1. 访问 https://vercel.com/new
2. 导入你的 `fashion-wiki` GitHub 仓库
3. 项目设置：
   - **Framework Preset**: `Other`
   - **Build Command**: `npx quartz build`
   - **Output Directory**: `public`
   - **Install Command**: `npm install`
4. 点击 **Deploy**

---

## 第四步：绑定域名 fashion-wiki.zgeo.net

### 在 Vercel 中配置

1. 进入 Vercel Dashboard → 选择 fashion-wiki 项目
2. 点击 **Settings** → **Domains**
3. 输入：`fashion-wiki.zgeo.net`
4. 按照提示在 DNS 提供商（如 Cloudflare）添加 CNAME 记录：
   - Type: `CNAME`
   - Name: `fashion-wiki`
   - Value: `cname.vercel-dns.com`

### 如果 zgeo.net 使用 Cloudflare

1. 登录 Cloudflare Dashboard
2. 选择 zgeo.net 域名
3. 进入 **DNS** → **Records**
4. 添加：
   - Type: `CNAME`
   - Name: `fashion-wiki`
   - Target: `cname.vercel-dns.com`
   - Proxy status: DNS only（灰色云，不要橙色云）
   - TTL: Auto

---

## 第五步：自动部署配置（GitHub Actions）

创建 `.github/workflows/deploy.yml`：

```yaml
name: Deploy Fashion Wiki to Vercel

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Build Quartz
        run: npx quartz build
      
      - name: Deploy to Vercel
        uses: vercel/action-deploy@v1
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
```

### 配置 Secrets

在 GitHub 仓库 → Settings → Secrets and variables → Actions 中添加：

| Secret | 获取方式 |
|--------|---------|
| `VERCEL_TOKEN` | Vercel Dashboard → Settings → Tokens → Create |
| `VERCEL_ORG_ID` | Vercel Dashboard → 地址栏 `https://vercel.com/你的组织ID` |
| `VERCEL_PROJECT_ID` | Vercel 项目 → Settings → General → Project ID |

---

## 第六步：Obsidian + Git 自动同步（可选）

在 Obsidian 中安装 **Git 插件**，实现保存即提交：

1. Obsidian → Settings → Community Plugins → Browse
2. 搜索 "Git"
3. 安装并启用
4. 配置自动提交间隔（如每 30 分钟）

这样每次在 Obsidian 中编辑内容后，会自动推送到 GitHub，触发 Vercel 重新部署。

---

## 验证清单

| 检查项 | 命令/操作 |
|--------|----------|
| GitHub 仓库已创建 | 访问 `https://github.com/你的用户名/fashion-wiki` |
| 代码已推送 | `git log --oneline` 在浏览器中可见 |
| Vercel 部署成功 | 访问 Vercel 提供的 `*.vercel.app` 域名 |
| 自定义域名生效 | 访问 `https://fashion-wiki.zgeo.net` |
| 双向链接正常 | 点击 `[[ur]]` 能跳转到 UR 品牌页面 |
| 表格渲染正常 | 面料对比表格正确显示 |

---

## 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| Vercel 构建失败 | `public` 目录不存在 | 确认 Build Command 是 `npx quartz build` |
| 双向链接 404 | Quartz 路由问题 | 检查 `quartz.config.ts` 中 `baseUrl` |
| 域名不生效 | DNS 未传播 | 等待 5-30 分钟，或检查 CNAME 配置 |
| 内容未更新 | 缓存问题 | Vercel Dashboard → Deployments → Redeploy |

---

## 当前状态

- ✅ Git 本地仓库已初始化
- ✅ 12 个文件已提交（11 篇文章 + 配置）
- ✅ Quartz 构建成功（95 个输出文件）
- ⏳ 等待推送到 GitHub
- ⏳ 等待 Vercel 部署
- ⏳ 等待域名绑定

---

*部署指南版本: v1.0 | 2026-05-08 | 由 OpsAgent 编写*