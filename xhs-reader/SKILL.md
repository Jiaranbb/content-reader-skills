---
name: xhs-reader
description: >
  由 content-reader 路由调用的小红书执行 skill。负责小红书内容保存、只保存多媒体、
  评论提取、媒体/OCR/逐字稿处理和 Markdown 入库。
  不作为通用入口直接触发；用户链接和意图先交给 content-reader 识别。
  小红书默认先打开网页版链接并检查登录态；检测到真实登录态必须停止。
---

# xhs-reader

从小红书链接提取内容，保存为本地多媒体文件或 Markdown 笔记。

## 安全铁律

本 skill 不使用任何小红书登录账号。处理小红书链接时，必须先打开网页版，再按 `references/account-safety.md` 检查登录态。通过前，不运行 `yt-dlp`、脚本、页面 JS、截图、评论提取、媒体提取或内容保存。检测到真实登录态时，立即停止，并提示用户退出登录或切换到未登录隔离浏览器。只有手机号/二维码登录弹窗不算已登录，默认关闭弹窗后继续。

## 工作流

1. 首次使用或路径不明确时，读取 `references/environment.md`，询问用户保存目录，并执行其中的 `--init` 初始化命令。
2. 根据下方「模式分流」判断走哪条流程。
3. 按 `references/workflow.md` 执行对应模式。
4. 视频、OCR、图片文字和逐字稿处理，读取 `references/media-processing.md`。
5. 小红书评论提取，在账号安全门禁通过后使用 `references/comments-js.md`。
6. 提取失败或页面行为异常时，读取 `references/gotchas.md`。

## 模式分流

本 skill 只处理 `content-reader` 已经识别出的标准意图，不自行根据用户原话做入口触发。

| 标准意图 | 走哪条流程 |
|----------|------------|
| `download_media` | 只保存多媒体。下载请求的视频或图片到多媒体目录，不生成 Markdown 笔记。 |
| `save_note` | 保存 Markdown 笔记。提取正文、媒体信息、可见评论，并分类为创作素材或知识资源。 |
| `save_note_with_media` | 保存 Markdown 笔记，并额外下载原视频，在笔记中链接或嵌入。 |

默认规则：

- 如果 `content-reader` 未传入明确标准意图，但已经确认是小红书链接，默认按 `save_note` 处理。
- 如果标准意图之间存在冲突，以 `content-reader` 的最终路由结果为准。

## 输出规则

- 笔记里的 `url` 必须保留入口传入的原始链接。
- 保存 Markdown 笔记时，默认使用 `assets/template-creative.md` 或 `assets/template-knowledge.md`；如果用户提供自己的模板或保存规则，优先遵循用户规则。
- 模板字段要完整填写，再按工作流要求裁剪不适用的区域。
- 不要把调试日志、报错堆栈、提取过程写进最终笔记正文。
- 逐字稿必须保留字幕或 ASR 原文；有时间戳就保留时间戳，禁止总结、改写或缩写。

## 路由入口

本 skill 不作为用户消息的直接入口。平台识别、用户表达解析和标准意图判定统一由 `content-reader` 完成；本 skill 只接收小红书链接、标准意图和必要的原始上下文后执行。
