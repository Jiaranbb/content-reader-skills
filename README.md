# content-reader-skills

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
git clone https://github.com/Jiaranbb/content-reader-skills.git
```

Example for Claude Code:

```bash
mkdir -p ~/.claude/skills
cp -R content-reader-skills/content-reader ~/.claude/skills/
cp -R content-reader-skills/xhs-reader ~/.claude/skills/
cp -R content-reader-skills/twitter-reader ~/.claude/skills/
cp -R content-reader-skills/youtube-reader ~/.claude/skills/
cp -R content-reader-skills/bilibili-reader ~/.claude/skills/
```

Example for Codex:

```bash
mkdir -p ~/.codex/skills
cp -R content-reader-skills/content-reader ~/.codex/skills/
cp -R content-reader-skills/xhs-reader ~/.codex/skills/
cp -R content-reader-skills/twitter-reader ~/.codex/skills/
cp -R content-reader-skills/youtube-reader ~/.codex/skills/
cp -R content-reader-skills/bilibili-reader ~/.codex/skills/
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
