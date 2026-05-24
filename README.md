# content-reader

一套给 AI Agent 使用的内容保存技能：发送一条链接，自动识别平台，提取内容，保存为本地 Markdown 笔记，并按需下载图片、视频或逐字稿。

```text
小红书 / Twitter/X / YouTube / B 站链接
        ↓
content-reader 自动识别平台和意图
        ↓
对应平台 reader 执行提取、下载和保存
        ↓
Markdown 笔记 + 本地媒体文件
```

## 它能干什么

这套技能包含 5 个 skill：

| Skill | 用途 |
|-------|------|
| `content-reader` | 总入口，自动识别链接平台和用户意图 |
| `xhs-reader` | 保存小红书图文、视频、评论、图片文字和原视频 |
| `twitter-reader` | 保存 Twitter/X 推文、X Article、图片、视频逐字稿和热门回复 |
| `youtube-reader` | 保存 YouTube 单视频或 playlist 逐字稿，按需下载原视频 |
| `bilibili-reader` | 保存 B 站单视频、分 P、合集逐字稿，生成内容摘要和划重点 |

生成的笔记兼容 Obsidian、Logseq、Typora 等 Markdown 工具。你也可以把保存目录设成任意本地文件夹。

### 小红书

| 能力 | 说明 |
|------|------|
| 图文笔记 | 提取标题、正文、标签、图片文字和可见评论 |
| 视频笔记 | 提取标题、正文、标签、评论，按需保存原视频和逐字稿 |
| 账号安全 | 默认不使用小红书登录账号；检测到真实登录态会停止 |

### Twitter/X

| 能力 | 说明 |
|------|------|
| 普通推文 | 保存正文、作者、互动数据和图片 |
| X Article | 保存长文正文，并尽量按原文位置插入图片 |
| 视频推文 | 默认拿逐字稿；明确需要时才下载视频 |
| 回复 | 尽量保存页面真实可见的热门回复 |

### YouTube / B 站

| 能力 | 说明 |
|------|------|
| 单视频逐字稿 | 优先直接读取平台字幕 |
| 合集 / playlist | 支持批量保存，条目多时可限制数量 |
| 划重点 | 根据逐字稿生成带时间戳的观看导航 |
| 原视频下载 | 默认不下载，明确需要时才保存视频文件 |

## 快速开始

### 1. 安装到你的 AI Agent

先克隆仓库：

```bash
git clone https://github.com/Jiaranbb/content-reader.git
```

Claude Code：

```bash
mkdir -p ~/.claude/skills
cp -R content-reader/content-reader ~/.claude/skills/
cp -R content-reader/xhs-reader ~/.claude/skills/
cp -R content-reader/twitter-reader ~/.claude/skills/
cp -R content-reader/youtube-reader ~/.claude/skills/
cp -R content-reader/bilibili-reader ~/.claude/skills/
```

Codex：

```bash
mkdir -p ~/.codex/skills
cp -R content-reader/content-reader ~/.codex/skills/
cp -R content-reader/xhs-reader ~/.codex/skills/
cp -R content-reader/twitter-reader ~/.codex/skills/
cp -R content-reader/youtube-reader ~/.codex/skills/
cp -R content-reader/bilibili-reader ~/.codex/skills/
```

其他 Agent：将上述 5 个目录放到 agent 能读取的 skills 目录中，并确保它能打开网页、执行命令、读写本地文件。

### 2. 首次使用

直接把链接发给 agent：

```text
保存一下 http://xhslink.com/o/xxxxx
```

第一次保存时，如果 `config.json` 里的 `obsidian_vault` 为空，agent 会询问你的保存目录。这个目录可以是 Obsidian Vault，也可以是任意 Markdown 文件夹。

每个平台都有自己的 `config.json`，例如：

```json
{
  "obsidian_vault": "",
  "save_root": "00-Inbox/Twitter",
  "default_category": "知识资源",
  "scripts_path": "scripts"
}
```

## 使用方式

直接发送链接即可：

```text
保存一下 http://xhslink.com/o/xxxxx
保存一下 https://x.com/user/status/123456
拿逐字稿 https://www.youtube.com/watch?v=VIDEO_ID
保存一下 https://www.bilibili.com/video/BV...
```

也可以明确说明你只要媒体文件：

```text
只下载视频 https://www.youtube.com/watch?v=VIDEO_ID
下载图片 http://xhslink.com/o/xxxxx
保存一下这个视频，需要原视频 https://www.bilibili.com/video/BV...
```

默认规则：

- 只发链接：保存笔记。
- YouTube / B 站视频：默认只保存逐字稿笔记，不下载视频。
- 明确说只下载：只下载媒体，不生成 Markdown。
- 明确说需要原视频：保存笔记，同时下载视频。

## 依赖说明

推荐安装：

```bash
# macOS
brew install yt-dlp ffmpeg

# Windows
winget install yt-dlp

# Linux / 通用 Python 环境
pipx install yt-dlp
```

可选安装：

```bash
pip install faster-whisper
```

依赖说明：

| 能力 | 依赖 | 说明 |
|------|------|------|
| 网页内容提取 | Agent 浏览器能力 | 用于读取公开网页或用户已可见页面 |
| 字幕 / 媒体下载 | `yt-dlp` | 推荐安装 |
| 视频处理 | `ffmpeg` | 下载、转音频、本地 ASR 时使用 |
| 本地转写 | `faster-whisper` | 没有可用字幕时才需要 |

不安装 `ffmpeg` / `faster-whisper` 也可以正常保存已有字幕和普通图文笔记。

## 安全原则

- 不输出、不保存 cookies、token、localStorage。
- 小红书默认不使用登录账号，检测到真实登录态会停止。
- Twitter/X 可以读取网页登录页面上已经可见的内容，但不会导出登录凭证。
- YouTube / B 站默认使用公开字幕和元数据；遇到私有、会员、年龄或地区限制时会说明原因。
- 本项目不适合批量爬取、商业采集或任何违反平台规则的用途。

## 项目结构

```text
content-reader/
├── content-reader/       # 总入口：平台识别和意图路由
├── xhs-reader/           # 小红书保存
├── twitter-reader/       # Twitter/X 保存
├── youtube-reader/       # YouTube 逐字稿和视频下载
├── bilibili-reader/      # B 站逐字稿和视频下载
├── README.md
└── LICENSE
```

每个 reader skill 通常包含：

```text
SKILL.md        # Agent 读取的核心流程
README.md      # 开发者和安装说明
config.json    # 保存路径配置
assets/        # Markdown 模板
references/    # 详细流程、格式和踩坑点
scripts/       # 稳定执行脚本
```

## 声明

本项目仅供个人学习和研究使用。请尊重平台内容版权、用户隐私和服务条款。不得将本工具用于批量爬取、商业用途或任何违反平台规则的行为。使用者应自行承担使用风险。

## 许可

[CC BY-NC 4.0](LICENSE) — 可自由使用和修改，需署名，禁止商业用途。

## 关于作者

嘉然 Jiaran

- 公众号：嘉然学习笔记
- GitHub：[Jiaranbb/content-reader](https://github.com/Jiaranbb/content-reader)

如果觉得有用，欢迎 Star 和关注交流。

---

# English

A collection of agent skills for saving public web content as Markdown notes and optional local media.

Supported platforms:

- Xiaohongshu / 小红书: `xhs-reader`
- Twitter/X: `twitter-reader`
- YouTube: `youtube-reader`
- Bilibili / B 站: `bilibili-reader`
- Combined router: `content-reader`

The recommended entry point is `content-reader`. It detects the platform, normalizes user intent, and routes to the platform-specific skill.

## Install

Clone this repository, then copy the skill folders you need into your agent's skill directory.

```bash
git clone https://github.com/Jiaranbb/content-reader.git
```

Example for Claude Code:

```bash
mkdir -p ~/.claude/skills
cp -R content-reader/content-reader ~/.claude/skills/
cp -R content-reader/xhs-reader ~/.claude/skills/
cp -R content-reader/twitter-reader ~/.claude/skills/
cp -R content-reader/youtube-reader ~/.claude/skills/
cp -R content-reader/bilibili-reader ~/.claude/skills/
```

Example for Codex:

```bash
mkdir -p ~/.codex/skills
cp -R content-reader/content-reader ~/.codex/skills/
cp -R content-reader/xhs-reader ~/.codex/skills/
cp -R content-reader/twitter-reader ~/.codex/skills/
cp -R content-reader/youtube-reader ~/.codex/skills/
cp -R content-reader/bilibili-reader ~/.codex/skills/
```

Other agents can use the same directory layout as long as they support local skills, command execution, and file writes.

## Configure

Each platform skill has a `config.json`.

Set `obsidian_vault` to your note root, or let the agent ask for a save directory on first use.

```json
{
  "obsidian_vault": "",
  "save_root": "00-Inbox/Twitter",
  "default_category": "知识资源",
  "scripts_path": "scripts"
}
```

`obsidian_vault` can point to an Obsidian vault or any local Markdown folder.

## Dependencies

Recommended:

- `yt-dlp` for metadata, subtitles, and media download.
- `ffmpeg` for local audio/video processing.

Optional:

- `faster-whisper` for local ASR fallback when no usable subtitles are available.

Install examples:

```bash
# macOS
brew install yt-dlp ffmpeg

# Windows
winget install yt-dlp

# Python environments
pipx install yt-dlp
pip install faster-whisper
```

## Standard Intents

`content-reader` routes user requests into these standard intents:

| Intent | Meaning |
|--------|---------|
| `save_note` | Save a Markdown note |
| `download_media` | Download media only |
| `save_note_with_media` | Save a note and download original media |
| `transcript` | Save a transcript note |
| `transcript_with_media` | Save a transcript note and download media |
| `batch_transcript` | Process playlist, collection, or multi-part video |

Platform skills should receive standard intents from `content-reader`; they should not duplicate broad trigger phrases.

## Safety

- Do not publish cookies, tokens, localStorage, or browser session data.
- Xiaohongshu is designed to avoid using a logged-in account by default.
- Twitter/X may use content already visible in the user's browser, but must not export credentials.
- YouTube and Bilibili default to public subtitles and metadata; login-restricted content should stop with a clear explanation unless the user explicitly authorizes a credential-based flow.

## Repository Layout

```text
content-reader/
xhs-reader/
twitter-reader/
youtube-reader/
bilibili-reader/
```

Each skill contains:

- `SKILL.md`: agent-facing instructions.
- `README.md`: developer and installer notes.
- `config.json`: configurable output paths.
- `references/`: detailed workflow notes loaded on demand.
- `scripts/`: deterministic helper scripts.
- `assets/`: Markdown templates.

## License

CC BY-NC 4.0. See `LICENSE`.

## Author

嘉然 | 公众号「嘉然学习笔记」
