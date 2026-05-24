# Obsidian 笔记格式

本文件只用于 Twitter/X 内容入库。保存 Markdown 前读取本文件和 `assets/template-twitter.md`。

## 保存路径

- 创作素材：`/00-Inbox/Twitter/创作素材/`
- 知识资源：`/00-Inbox/Twitter/知识资源/`
- 视频媒体：`/00-Inbox/Twitter/多媒体/`
- 图文图片：保存到笔记同级附件目录，目录名使用 `标题附件/`。

拿不准分类时，默认保存到知识资源。

## 文件名与标题

- 文件名：`YYYY-MM-DD-X-标题.md`
- 标题去掉 `/ \ : * ? " < > |` 等不安全字符，控制在约 50 个中文字符以内。
- H1：`# YYYY-MM-DD 标题`
- `url` 和正文「原链接」必须保留用户发送的原始链接。

## Frontmatter

必须包含：

```yaml
---
tags: [Twitter, 主题标签1, AI-agent, 知识收集]
created: YYYY-MM-DD
type: 知识收集
source: Twitter
author: 作者名
url: 用户发送的原始链接
date: YYYY-MM-DD
note: 一句话说明
---
```

规则：

- 不额外增加 `handle` 等未约定 YAML 属性；账号可以写在正文作者行。
- `tags` 必须是数组格式，至少包含 `Twitter`、2-4 个主题标签和末尾分类标签：`知识收集` 或 `创作素材`。
- tag 不允许包含空格。英文词组用 `-` 连接，例如 `AI-agent`、`content-strategy`、`market-research`。
- `激活` 必须存在，且至少一个维度为 `true` 或非空数组。

## 正文头部

```markdown
# YYYY-MM-DD 标题

**作者：** 作者名（@handle）
**来源：** Twitter/X
**原链接：** [原始链接](原始链接)
**发布时间：** YYYY-MM-DD HH:MM
**互动数据：** 回复 X | 转发 Y | 喜欢 Z | 浏览 V | 书签 B
```

互动数据字段顺序固定：回复、转发、喜欢、浏览、书签。缺失字段写 `-`，不要省略整行。

## 文章或图文

必须包含：

```markdown
## 正文内容

推文 / 长推 / X Article 原文。

---

## 内容摘要

200 字以内，提炼核心内容。

---

## 热门回复（Top 10）
```

图片规则：

- 图片必须下载成本地附件，并使用标准 Markdown 相对路径：`![图1](标题附件/01.jpg)`。
- 普通图文推文：正文后、内容摘要前创建 `## 图片` 区域集中放图。
- X Article / 长文章：图片插入到正文对应段落后，例如原文出现「下图」「结果预览」「对照」「架构」「截图」等位置。
- 不做 OCR，不把图片上的文字写入「媒体文字内容」。

X Article / 长文章格式：

- 章节小标题转成 Markdown 二级标题 `##`，如 `一、...`、`二、...`、`1. ...`。
- 命令、代码、JSON、数组、日志、字段列表、树状轨迹必须保存为 fenced code block，例如 `bash`、`json`、`text`。
- `plaintext`、`bash`、`json`、`text` 等语言标记要转成代码块信息字符串，不要作为正文行保留。

文章或图文没有逐字稿时，删除 `## 媒体文字内容` 和 `## 视频` 区域。

## 热门回复

```markdown
## 热门回复（Top 10）

| # | 用户 | 回复内容 | 互动 |
|---|------|---------|------|
| 1 | 用户名 | 回复内容 | 点赞/转发/回复数，缺失写 - |
```

只记录页面真实可见的回复。不要把正文中的引用推文、嵌入推文或作者正文段落当成回复。

页面未稳定展示回复时，写：`当前页面未提取到可见回复。`

## 视频和逐字稿

视频逐字稿写入：

```markdown
## 媒体文字内容

字幕或 ASR 原文。有时间戳就保留时间戳；不要总结、改写或缩写。
```

用户明确要求下载视频时，视频文件保存到 `00-Inbox/Twitter/多媒体/标题/`，并在笔记中写：

```html
<video src="../多媒体/标题/视频文件.mp4" controls></video>
```

## 尾注

末尾固定：

```markdown
*保存时间：YYYY-MM-DD HH:MM*

---

*由 [twitter-reader](https://github.com/Jiaranbb/content-reader-skills/tree/main/twitter-reader) 提取保存 | 作者：嘉然 · 公众号「嘉然学习笔记」*
```

不要把 cookies、token、localStorage、报错堆栈或调试信息写入笔记。
