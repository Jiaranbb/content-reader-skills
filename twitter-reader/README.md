# twitter-reader

Developer notes for the Twitter/X execution skill. In the full suite, `content-reader` should route Twitter/X links here.

## Role

`twitter-reader` handles:

- Regular tweets and image tweets.
- X Articles / long posts.
- Image media download.
- Video transcript extraction.
- Optional video media download.
- Visible replies, quotes, and interaction metadata.

## Standard Intents

| Content | Intent | Behavior |
|---------|--------|----------|
| Article or image tweet | `save_note` | Save text and image media |
| Video tweet | `transcript` | Save transcript note without media download |
| Video tweet | `transcript_with_media` | Save transcript note and download video |
| Video tweet | `download_media` | Download video only |

If no explicit intent is passed, inspect the content type: article/image tweets use `save_note`; video tweets use `transcript`.

## Safety Model

Twitter/X often requires a logged-in browser page to show article text, replies, and interaction data.

Allowed:

- Read content already visible in the user's browser page.

Not allowed by default:

- Export cookies, tokens, localStorage, or browser session data.
- Use command-line `cookies-from-browser` without explicit user approval.

## Configure

Set `obsidian_vault` in `config.json`.

```json
{
  "obsidian_vault": "",
  "save_root": "00-Inbox/Twitter",
  "scripts_path": "scripts"
}
```

## Dependencies

- `yt-dlp`: media, subtitle, or metadata fallback.
- `ffmpeg`: local media processing.
- `faster-whisper`: optional ASR fallback.

Script entry:

```bash
python3 scripts/twitter_note.py --help
```

## Maintenance

- Video transcript fallback order is documented in `references/media-processing.md`.
- Markdown output rules are in `references/obsidian-note-format.md`.
- Image tweets save images as media; they do not OCR image text by default.
- Keep broad trigger phrases in `content-reader`, not here.

## Author

嘉然 | 公众号「嘉然学习笔记」
