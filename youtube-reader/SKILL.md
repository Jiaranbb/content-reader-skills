---
name: youtube-reader
description: >
  由 content-reader 路由调用的 YouTube 执行 skill。
  负责 YouTube 单视频和 playlist 的逐字稿笔记、中文字幕优先、划重点和媒体下载。
  不作为通用入口直接触发；用户链接和意图先交给 content-reader 识别。
  默认只保存逐字稿笔记，不下载媒体。
---

# youtube-reader

YouTube 执行 skill。核心规则：默认只拿逐字稿并保存为 Markdown；只有 `content-reader` 路由出的标准意图包含媒体下载时才下载媒体。

## 模式分流

本 skill 只处理 `content-reader` 已经识别出的标准意图，不自行根据用户原话做入口触发。

| 标准意图 | 流程 | 命令 |
|---|---|---|
| `transcript` | 保存逐字稿笔记，不下载媒体 | `--action transcript` |
| `download_media` | 只下载媒体，不生成 Markdown 笔记 | `--action download-media` |
| `transcript_with_media` | 保存逐字稿笔记，并在笔记中嵌入本地视频预览 | `--action transcript --include-media` |
| `batch_transcript` | 展开 playlist，一条视频生成一篇笔记 | `--action transcript --max-items N` |

## 执行规则

1. 先运行环境检查：确认 `yt-dlp` 可用；如果会进入 ASR 兜底，再确认 `faster-whisper` 可用。
2. 单链接默认保存逐字稿笔记。
3. playlist/合集链接默认逐条保存逐字稿笔记；如果条目很多且 `content-reader` 未传入完整批量意图，先让用户给范围或 `--max-items`。
4. YouTube 字幕默认优先抓中文，参考 `podcast-transcript-txt` 的窄语言重试策略：按 `zh-Hans -> zh-CN -> zh-Hant -> zh -> en-orig -> en` 逐个请求。遇到 `429 Too Many Requests` 先退避再重试当前中文语言；只有中文都不可用时才退回英文；最后才用本地 `faster-whisper`。
5. `## 内容摘要` 不能留空，不能只写 `待整理`。保存前必须从完整逐字稿中提炼 3-4 条核心观点/知识点；如果原字幕是英文，摘要也优先写成中文。脚本自动摘要只作为兜底，质量不足时执行 agent 必须人工改写。
6. 笔记必须包含 `## 划重点`，每条格式是时间戳 + “从这里开始看什么”。不要只复制该时间点字幕；要看该时间点后约 60-90 秒内容，提炼成可回看的观看导航。
7. 不主动读取或导出浏览器 cookies、token、localStorage。遇到私有、会员、年龄限制或地区限制时，返回阻塞原因，让用户明确决定是否授权登录态方案。

## 常用命令

```bash
python3 scripts/youtube_reader.py \
  --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

```bash
python3 scripts/youtube_reader.py \
  --url "https://www.youtube.com/playlist?list=PLAYLIST_ID" \
  --max-items 20
```

```bash
python3 scripts/youtube_reader.py \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --action transcript \
  --include-media
```

```bash
python3 scripts/youtube_reader.py \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --action download-media
```

## 输出位置

输出根目录由 `config.json` 的 `obsidian_vault`、`note_root` 和 `media_root` 决定。首次使用时如果 `obsidian_vault` 为空，先让用户指定保存目录或运行初始化。

## Reference

- 工作流细节：`references/workflow.md`
- 环境要求：`references/environment.md`
- 踩坑点：`references/gotchas.md`
