# content-reader

Developer notes for the combined router skill.

## Role

`content-reader` is the entry point for this skill suite.

It does three things:

1. Detect the platform from the URL.
2. Normalize user intent into a standard intent.
3. Route the task to the platform-specific reader skill.

It should not implement extraction, download, transcript, or Markdown formatting logic directly.

## Platform Routing

| Platform | URL pattern | Skill |
|----------|-------------|-------|
| Xiaohongshu | `xhslink.com`, `xiaohongshu.com`, `explore/` | `xhs-reader` |
| Twitter/X | `x.com`, `twitter.com` | `twitter-reader` |
| YouTube | `youtube.com`, `youtu.be` | `youtube-reader` |
| Bilibili | `bilibili.com`, `b23.tv` | `bilibili-reader` |

## Standard Intents

| Intent | Meaning |
|--------|---------|
| `save_note` | Save a Markdown note |
| `download_media` | Download media only |
| `save_note_with_media` | Save a note and download original media |
| `transcript` | Save a transcript note |
| `transcript_with_media` | Save a transcript note and download media |
| `batch_transcript` | Process playlist, collection, or multi-part video |

## Safety

- Platform login and credential rules belong to platform skills.
- Do not export cookies, tokens, or localStorage.
- If a platform requires credentials, stop and ask for explicit user authorization before entering any credential-based command-line flow.

## Maintenance

- Add new platforms here only after creating a platform-specific skill.
- Keep broad user trigger phrases in `SKILL.md` here.
- Keep platform skills route-only when they are part of this suite.
- If standard intents change, update all platform `README.md`, `SKILL.md`, and scripts together.

## Author

嘉然 | 公众号「嘉然学习笔记」
