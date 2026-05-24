---
name: twitter-reader
description: >
  由 content-reader 路由调用的 Twitter/X 执行 skill。
  负责 Twitter/X 推文、X Article、图文媒体、视频逐字稿、热门回复和 Markdown 入库。
  不作为通用入口直接触发；用户链接和意图先交给 content-reader 识别。
  默认使用用户主浏览器访问网页，只读取网页登录状态下已经可见的内容；
  不输出、不保存 cookies/token/localStorage。
---

# twitter-reader

从 Twitter/X 链接提取网页中可见的内容，按内容类型保存到 Markdown 目录。

## 安全原则

默认使用用户主浏览器访问 Twitter/X 网页。可以读取页面上已经可见的正文、图片、视频和 X Article 内容，但不得输出、保存或复制 cookies、token、localStorage 等敏感信息。

回复、引用、互动数据、文章正文等页面信息默认从用户主浏览器登录页面读取。不要为了避开登录态而改走未登录接口；也不要导出 cookies、token、localStorage。命令行下载工具只有在需要下载媒体或字幕时使用，且不得把浏览器登录凭证写入文件或笔记。

处理顺序：

1. 先用用户主浏览器访问网页。Twitter/X 视频也必须先看登录网页中可见的正文、作者、互动和视频状态。
2. 如果页面内容可见，先判断是文章/图文还是视频。
3. 文章/图文：保存文字，并下载图片媒体到笔记附件目录；图片只作为媒体保存，不做 OCR。
4. 视频：默认拿字幕或逐字稿；只有用户明确要求下载媒体时才下载视频。
5. 视频逐字稿顺序固定为：已登录网页可见字幕采样 -> Twitter/X 官方或自动字幕 -> 根据网页线索寻找原始 YouTube 视频并直接提取 YouTube 字幕 -> 本地 Whisper/ASR 兜底。
6. 回复和互动数据继续从主浏览器登录页面滚动读取；不要因为命令行公开接口缺字段就省略。
7. 再尝试 `yt-dlp` 获取公开媒体、字幕或元数据。命令行需要登录凭证时，先使用网页可见内容完成文字保存；只有用户明确授权时才考虑命令行登录凭证。

## 工作流

1. 读取 `references/environment.md`，确认固定保存路径和依赖。
2. 根据下方「模式分流」判断走哪条流程。
3. 按 `references/workflow.md` 执行网页优先提取。
4. 视频字幕、逐字稿和 ASR 兜底，读取 `references/media-processing.md`。
5. 保存 Markdown 时读取 `references/obsidian-note-format.md`；优先使用 `scripts/twitter_note.py` 根据浏览器提取 JSON 写入笔记和图片附件。
6. 遇到图片、回复、X Article、视频字幕或下载异常时，读取 `references/gotchas.md`。

## 模式分流

本 skill 只处理 `content-reader` 已经识别出的标准意图，不自行根据用户原话做入口触发。

| 内容类型 / 标准意图 | 走哪条流程 |
|----------------------|------------|
| 文章或图文 / `save_note` | 保存 Markdown，并下载图片媒体到笔记附件目录 |
| 视频 / `transcript` | 优先字幕；没有字幕再考虑本地 ASR；不默认下载视频 |
| 视频 / `transcript_with_media` | 生成逐字稿，并下载公开视频，在 Markdown 中以预览形式嵌入 |
| 视频 / `download_media` | 只下载公开视频，不生成 Markdown |

默认规则：

- 如果 `content-reader` 未传入明确标准意图，但已经确认是 Twitter/X 链接，先判断内容类型；文章/图文按 `save_note`，视频按 `transcript`。
- 文章和图文推文里的图片只下载保存，不读取图片上的文字，不做 OCR。
- `download_media` 不生成 Markdown。
- 视频只有在标准意图包含媒体下载时，才下载视频并嵌入 Markdown 预览。

## 输出规则

- `url` 必须保留入口传入的原始链接。
- Markdown 笔记格式、frontmatter、互动数据、图片附件、热门回复、视频预览和尾注规则，以 `references/obsidian-note-format.md` 为准。
- 不把登录 cookies、token、localStorage、敏感调试信息、报错堆栈或提取过程写进笔记。
- 逐字稿保留字幕或 ASR 原文；有时间戳就保留时间戳，禁止总结、改写或缩写。

## 路由入口

本 skill 不作为用户消息的直接入口。平台识别、用户表达解析和标准意图判定统一由 `content-reader` 完成；本 skill 只接收 Twitter/X 链接、标准意图和必要的原始上下文后执行。

## Reference

- 工作流细节：`references/workflow.md`
- 媒体与逐字稿：`references/media-processing.md`
- Obsidian 笔记格式：`references/obsidian-note-format.md`
- 环境要求：`references/environment.md`
- 踩坑点：`references/gotchas.md`
- 写入脚本：`scripts/twitter_note.py`
