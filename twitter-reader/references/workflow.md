# 工作流

## 先访问网页

所有 Twitter/X 链接都先用用户主浏览器访问网页，不默认直接 `yt-dlp`。

1. 打开用户提供的 `ORIGINAL_LINK`。
2. 判断用户主浏览器网页中是否可见：
   - 可见正文 / 作者 / 图片 / 视频 / X Article：继续。
   - 仍然无法看到正文、X Article 403：停止并说明网页不可见限制。
3. 如果是短链接或 t.co 链接，解析最终目标，但仍以用户发送的原始链接写入笔记。
4. 不输出、不保存、不复制 cookies、token、localStorage。
5. 回复、引用、互动数据、文章正文等页面信息默认从这个已登录网页读取；不要刻意改用未登录页面或公开接口导致少拿信息。

## 内容类型判断

打开网页后先判断内容类型：

- **文章或图文**：X Article、长文、普通文字推文、带图片但没有视频的推文。
- **视频**：页面可见 `<video>`、播放器、视频封面，或 `yt-dlp` 元数据表明有视频格式。

不要只根据用户触发词决定流程。只有链接、没有额外指令时，必须先判断内容类型：

- 文章或图文：保存文字，并下载图片媒体。
- 视频：默认提取字幕或逐字稿，不默认下载视频。

## 文章或图文保存

1. 从网页可见内容提取：
   - `author`
   - `handle`
   - `title`
   - `text`
   - `published_at`
   - `reply_count`
   - `repost_count`
   - `like_count`
   - `view_count`
   - `bookmark_count`
   - `images`
   - `article_url`
2. 如果网页显示的是 X Article，进入文章页面读取可见正文；不可见或 403 就停止。
3. 可见时，再尝试 `yt-dlp --dump-single-json --skip-download "$ORIGINAL_LINK"` 获取辅助元数据。失败不影响保存网页可见内容；如果命令行结果和登录网页不一致，以登录网页可见内容为准。
4. 判断保存目录：
   - 可复用于写作、选题、社交文案、内容角度：`00-Inbox/Twitter/创作素材/`
   - 教程、方法、参考资料、研究、学习型内容：`00-Inbox/Twitter/知识资源/`
   - 拿不准时默认 `00-Inbox/Twitter/知识资源/`
5. 文件名：`YYYY-MM-DD-X-标题.md`，去除不安全字符，标题控制在约 50 个字符内。
6. 创建图片附件目录，位于笔记同级目录：

```bash
mkdir -p "标题附件"
```

7. 下载可见图片媒体到附件目录，命名为 `01.jpg`、`02.png`、`03.webp` 等。图片只保存为媒体，不做 OCR，不读取图片上的文字。
8. 将网页提取结果整理为 JSON，优先交给 `scripts/twitter_note.py` 写入 Markdown 和图片附件。JSON 字段建议：
   - `original_url` / `url`
   - `title`
   - `author`
   - `handle`
   - `published_at`
   - `text`
   - `summary`
   - `tags`
   - `interactions`: `reply_count`、`repost_count`、`like_count`、`view_count`、`bookmark_count`
   - `images`: 图片 URL 列表或 `{url, alt}` 对象列表
   - `replies`: `{user, text, interaction}` 对象列表
   - `transcript`、`video_path`：仅视频需要
9. 脚本命令：

```bash
python3 scripts/twitter_note.py \
  --input-json "/tmp/twitter-note.json" \
  --category "知识资源" \
  --model "agent"
```

10. 如果脚本不适合当前内容，再读取 `assets/template-twitter.md` 手动填写 Markdown：
   - 「正文内容」放推文 / 长文 / X Article 原文。
   - 「互动数据」放在发布时间之后；字段顺序固定为：回复、转发、喜欢、浏览、书签。缺失字段写 `-`，不要省略整行。
   - 「内容摘要」放 200 字以内摘要。
   - 「热门回复（Top 10）」放在内容摘要之后；必须在用户主浏览器登录页面中滚动读取真实可见回复，不把正文中的引用推文、嵌入推文或作者正文段落当成回复。
   - 可见回复字段为：用户、回复内容、互动。互动缺失写 `-`。只有登录页面确实无法稳定展示回复时，才写 `当前页面未提取到可见回复。`
   - X Article / 长文章：图片插入到正文里对应的位置，例如原文出现「下图」「结果预览」「对照」「架构」「截图」等段落后。
   - 普通图文推文：图片放在正文内容之后、内容摘要之前的「图片」区域。
   - 使用标准 Markdown 相对路径预览语法：`![图1](标题附件/01.jpg)`，与小红书笔记附件格式保持一致。
   - 没有图片就不创建图片区域。
   - X Article / 长文章中的章节小标题转成 Markdown 二级标题 `##`，例如 `一、...`、`二、...`、`1. ...`；标题前后保留空行。
   - X Article / 长文章里的命令、代码、JSON、数组、日志、树状轨迹、字段列表保存为 fenced code block。
   - `plaintext`、`bash`、`json`、`text` 等语言标记要转成代码块信息字符串，不要作为正文行保留。
   - 文章或图文没有逐字稿时删除「媒体文字内容」区域。
   - 尾注写成 `*由 [twitter-reader](https://github.com/Jiaranbb/content-reader/tree/main/twitter-reader) 提取保存 | 作者：嘉然 · 公众号「嘉然学习笔记」*`。

## 只下载视频

1. 先访问网页，确认用户主浏览器页面中视频可见。
2. 创建目录：

```bash
mkdir -p "/00-Inbox/Twitter/多媒体/标题"
cd "/00-Inbox/Twitter/多媒体/标题"
```

3. 尝试下载公开媒体：

```bash
yt-dlp -o "%(title)s.%(ext)s" "$ORIGINAL_LINK"
```

4. `yt-dlp` 要求登录或 unsupported 时，先尝试用页面可见媒体 URL 下载；仍失败则说明需要用户单独确认命令行登录凭证。无论媒体下载是否成功，回复和互动仍从主浏览器登录页面读取。

## 视频默认流程

视频推文默认不下载视频文件。读取 `references/media-processing.md`，按顺序获取：

1. 先访问用户主浏览器中的登录网页，提取可见正文、作者、发布时间、互动数据、视频时长、外链和可见回复。
2. 如果登录网页播放器显示字幕，先按进度条逐点跳转采样页面可见字幕，不保存视频文件。
3. 用 `yt-dlp` 尝试获取 Twitter/X 官方字幕或自动字幕，不使用浏览器 cookies。
4. 没有 Twitter/X 字幕时，根据网页可见标题、作者、外链、视频主题去 YouTube 找原视频；多数转发视频都有原始 YouTube 来源，不要只做一次泛搜索就放弃。
5. 对 YouTube 候选做匹配校验：标题/作者/主题必须对应；时长允许是原视频长于 Twitter 剪辑，但要能解释剪辑关系。无法解释时，只标为候选，不当作确定原视频。
6. 确认或高置信匹配到 YouTube 原视频后，按 `references/media-processing.md` 内置的 YouTube 字幕流程直接提取，不调用外部 skill。
7. 没有可信 YouTube 原视频或 YouTube 字幕不可用时，才下载临时 Twitter 音频或视频，使用本地 Whisper/ASR 识别。
8. 将逐字稿写入「媒体文字内容」区域。
9. 如果以上都不可用，保存可见正文并标注逐字稿失败原因。

## 视频并下载媒体

用户明确说 `需要原视频`、`原视频也需要`、`同时下载视频`、`下载这个视频`、`把视频发我` 时，才下载视频媒体。

1. 先按「视频默认流程」生成逐字稿。
2. 按「只下载视频」下载公开视频到 `00-Inbox/Twitter/多媒体/标题/`。
3. 在 Markdown 的「视频」区域写入相对路径预览：

```html
<video src="../多媒体/标题/视频文件.mp4" controls></video>
```

4. 如果笔记保存在 `创作素材`，相对路径同样从当前目录到 `../多媒体/...`。

## 只拿逐字稿

读取 `references/media-processing.md`。先读登录网页可见内容，再查 Twitter/X 字幕，再查可信 YouTube 原始字幕，最后才走本地 Whisper/ASR。
