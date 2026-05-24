---
name: bilibili-reader
description: >
  由 content-reader 路由调用的 B 站执行 skill。
  负责 B 站单视频、分 P、合集/播放列表的逐字稿笔记、划重点、互动数据和媒体下载。
  不作为通用入口直接触发；用户链接和意图先交给 content-reader 识别。
  默认只保存逐字稿笔记，不下载媒体。
---

# bilibili-reader

B 站执行 skill。核心规则：默认只拿逐字稿并保存为 Markdown；只有 `content-reader` 路由出的标准意图包含媒体下载时才下载媒体。

## 模式分流

本 skill 只处理 `content-reader` 已经识别出的标准意图，不自行根据用户原话做入口触发。

| 标准意图 | 流程 | 命令 |
|---|---|---|
| `transcript` | 保存逐字稿笔记，不下载媒体 | `--action transcript` |
| `download_media` | 只下载媒体，不生成 Markdown 笔记 | `--action download-media` |
| `transcript_with_media` | 保存逐字稿笔记，并在笔记中嵌入本地视频预览 | `--action transcript --include-media` |
| `batch_transcript` | 展开合集/分 P，一条视频生成一篇笔记 | `--action transcript --max-items N` |

## 执行规则

1. 先运行环境检查：确认 `yt-dlp` 可用；如果会进入 ASR 兜底，再确认 `faster-whisper` 可用。
2. 单链接默认保存逐字稿笔记。
3. 分 P、合集、播放列表默认逐条保存逐字稿笔记；如果条目很多且 `content-reader` 未传入完整批量意图，先让用户给范围或 `--max-items`。
4. B 站字幕优先级：用户主浏览器登录页面可见字幕 -> 平台字幕 / 自动字幕 -> 本地 `faster-whisper`。默认字幕阶段不下载视频；只有前两种字幕都不可用时才下载临时音频用于 ASR。
5. 笔记必须包含 `## 划重点`，根据逐字稿提炼重要观看节点。格式是时间戳 + “从这里开始看什么”，不能只是复制该时间点的一句字幕。自动生成后如果仍像字幕摘句，必须再读逐字稿手动改写成观看导航。
6. 笔记头部必须记录互动数据：播放、弹幕、点赞、投币、收藏、分享、评论。优先使用用户主浏览器登录页面可见数据；缺失时用 `yt-dlp` 元数据补播放、点赞、评论，其余写 `-`。
7. `## 内容摘要` 不能留空，不能只写 `待整理`。保存前必须从完整逐字稿中提炼 3-4 条核心观点/知识点，每条尽量控制在 60 个中文字符以内；不要复述完整段落，也不要和 `## 划重点` 重复。脚本自动摘要质量不足时，执行 agent 必须人工改写。
8. 不主动读取或导出浏览器 cookies、token、localStorage。遇到会员、登录限制或地区限制时，返回阻塞原因，让用户明确决定是否授权登录态方案。

## 常用命令

```bash
python3 scripts/bilibili_reader.py \
  --url "https://www.bilibili.com/video/BV..."
```

如果已通过用户主浏览器登录页面提取到字幕，优先传入浏览器字幕文件：

```bash
python3 scripts/bilibili_reader.py \
  --url "https://www.bilibili.com/video/BV..." \
  --transcript-json "/private/tmp/bilibili-browser-subtitles.json" \
  --browser-meta-json "/private/tmp/bilibili-browser-meta.json"
```

```bash
python3 scripts/bilibili_reader.py \
  --url "https://www.bilibili.com/video/BV..." \
  --max-items 20
```

```bash
python3 scripts/bilibili_reader.py \
  --url "https://www.bilibili.com/video/BV..." \
  --action transcript \
  --include-media
```

```bash
python3 scripts/bilibili_reader.py \
  --url "https://www.bilibili.com/video/BV..." \
  --action download-media
```

## 输出位置

输出根目录由 `config.json` 的 `obsidian_vault`、`note_root` 和 `media_root` 决定。首次使用时如果 `obsidian_vault` 为空，先让用户指定保存目录或运行初始化。

## Reference

- 工作流细节：`references/workflow.md`
- 环境要求：`references/environment.md`
- 踩坑点：`references/gotchas.md`
