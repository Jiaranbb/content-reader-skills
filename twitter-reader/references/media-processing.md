# 媒体处理

## 分流原则

- 文章或图文：下载图片媒体到笔记附件目录；不读取图片上的文字，不做 OCR。
- 视频：默认拿字幕或逐字稿，不下载最终视频文件。
- 只有用户明确说需要原视频、下载视频、把视频发我、同时下载视频时，才下载视频媒体并在 Obsidian 中预览。

## 视频逐字稿顺序

必须按这个顺序执行，不要跳过网页步骤：

1. 先打开用户主浏览器中的 Twitter/X 登录网页，读取页面可见内容和视频状态。
2. 如果视频播放器正在显示字幕或 CC 文本，优先用浏览器进度条逐点跳转采样页面可见字幕；这是登录网页可见内容，不导出 cookies/token/localStorage。
3. 尝试获取 Twitter/X 官方字幕或自动字幕。
4. 如果没有字幕，用网页可见文案、作者、外链、视频主题查找原始 YouTube 视频；多数 Twitter/X 转发视频都有原视频，不要只做一次泛搜索就放弃。
5. 对 YouTube 候选做匹配校验：标题、作者、内容主题必须能对应；YouTube 原视频可以长于 Twitter 剪辑，但要能解释剪辑关系。无法解释时，只能写成候选，不得当作确定原视频。
6. 确认或高置信匹配到 YouTube 原视频后，使用本文件内置的 YouTube 字幕流程直接提取，不调用其他 skill。
7. 如果没有可信 YouTube 原视频，最后才下载临时音频或视频，用本地 Whisper/ASR 识别。

## 浏览器可见字幕采样

Twitter/X 视频如果播放器里直接显示字幕，优先用这个方法，不要先跳到 ASR：

1. 用用户主浏览器打开推文页面，确认视频和字幕在页面内可见。
2. 让视频暂停或保持可控状态。
3. 按固定间隔在进度条上跳转，读取页面当前显示的字幕文本。
4. 记录 `{start, text}`，相邻重复字幕去重。
5. 保存为临时 JSON，再写入 Markdown 的「媒体文字内容」。

采样边界：

- 只读取页面已经可见的字幕文本。
- 不导出 cookies、token、localStorage。
- 不保存最终视频媒体。
- 如果播放器无法跳转、字幕不稳定或只显示极少片段，再进入 Twitter/X 官方字幕、YouTube 原视频字幕或本地 ASR。

## Twitter/X 字幕

在完成网页读取后，尝试获取官方字幕或自动字幕：

```bash
yt-dlp --write-subs --write-auto-subs --sub-lang "zh,zh-Hans,zh-CN,en" --sub-format vtt --skip-download -o "/tmp/twitter_subs" "$ORIGINAL_LINK"
```

如果拿到字幕，直接使用字幕文本。不要安装或运行 `faster-whisper`。

## YouTube 原视频逐字稿

如果 Twitter/X 没有字幕，必须尝试找原始 YouTube 视频：

1. 用网页标题、作者、外链锚文本、视频封面文字、转推文案和视频主题搜索 YouTube。
2. 优先检查网页外链、作者提到的来源、视频标题中的专有名词。
3. 对候选视频检查标题、作者、主题和时长。Twitter 视频可能是 YouTube 原视频剪辑；原视频更长不直接排除，但必须能从标题/内容/片段解释对应关系。
4. 可信候选有平台字幕时，先用本 skill 自带脚本提取 YouTube 字幕，不调用外部 skill：

```bash
python3 scripts/youtube_subtitles.py \
  --url "$YOUTUBE_URL" \
  --out-dir "/tmp/twitter-youtube-subs"
```

脚本会输出：

- `/tmp/twitter-youtube-subs/youtube_transcript.txt`
- `/tmp/twitter-youtube-subs/youtube_transcript.meta.json`

脚本内部的字幕下载策略如下：

```bash
mkdir -p "/tmp/twitter-youtube-subs"

yt-dlp \
  --skip-download \
  --write-auto-subs \
  --write-subs \
  --extractor-args "youtube:player_client=android" \
  --sub-langs "zh-Hans,zh-CN,zh-Hant,zh,en-orig,en" \
  --sub-format vtt \
  -o "/tmp/twitter-youtube-subs/%(id)s.%(ext)s" \
  "$YOUTUBE_URL"
```

5. 如果第一轮多语言字幕触发 `429 Too Many Requests`、PO token、SABR、或没有下载到字幕文件，缩窄到英文原文重试：

```bash
yt-dlp \
  --skip-download \
  --write-auto-subs \
  --write-subs \
  --extractor-args "youtube:player_client=android" \
  --sub-langs "en-orig,en" \
  --sub-format vtt \
  -o "/tmp/twitter-youtube-subs/%(id)s.%(ext)s" \
  "$YOUTUBE_URL"
```

6. 选择字幕文件的优先级固定为：`zh-Hans` -> `zh-CN` -> `zh-Hant` -> `zh` -> `en-orig` -> `en`。如果都没有，继续本地 ASR。
7. 清洗 VTT：
   - 跳过 `WEBVTT`、`NOTE`、`Kind:`、`Language:`、纯数字 cue id、时间轴行。
   - 移除 `<00:00:00.000>` 这类内联时间戳和 HTML 标签。
   - HTML entity 解码，删除零宽字符。
   - 删除 `[music]`、`[Music]`、`[applause]`、`[Applause]`。
   - 合并滚动字幕：如果新 cue 已出现在最近约 600 字窗口里，跳过；否则按后缀/前缀最大重叠拼接。
   - 按句号、问号、感叹号、中文标点拆行；超长行按约 200-220 字硬换行。
8. 将清洗后的字幕写入「媒体文字内容」。保留来源说明：`字幕来源：YouTube 原视频（$YOUTUBE_URL）`；如果只是候选原视频，写成 `字幕来源：YouTube 候选原视频（未完全确认）`。
9. 找不到可信 YouTube 原视频，继续本地 ASR。

## 本地 ASR 兜底

只有在没有 Twitter/X 字幕、没有可信 YouTube 原视频逐字稿，且用户仍然需要逐字稿时，才使用本地 ASR。

1. 下载临时公开视频到 `/tmp`，只用于转写：

```bash
yt-dlp -o "/tmp/twitter_video.%(ext)s" "$ORIGINAL_LINK"
```

2. 提取音频：

```bash
ffmpeg -i /tmp/twitter_video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 /tmp/twitter_audio.wav
```

3. 使用已有本地 ASR 脚本：

```bash
python3 scripts/xhs_extract.py --url "/tmp/twitter_audio.wav" --action transcribe --asr-model small
```

如果本地 ASR 命令不可用，标注：`无字幕，且本地 ASR 依赖缺失`。

## 明确下载视频

只有用户明确要求下载媒体时，才把视频保存到 Obsidian：

```bash
mkdir -p "/00-Inbox/Twitter/多媒体/标题"
yt-dlp -o "/00-Inbox/Twitter/多媒体/标题/%(title)s.%(ext)s" "$ORIGINAL_LINK"
```

下载完成后，在 Markdown 里使用相对路径预览：

```html
<video src="../多媒体/标题/视频文件.mp4" controls></video>
```

## 逐字稿规则

- 保留字幕或 ASR 原文。
- 有时间戳就保留时间戳。
- 不总结、不改写、不缩写。
