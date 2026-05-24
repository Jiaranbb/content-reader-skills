# bilibili-reader

Developer notes for the Bilibili execution skill. In the full suite, `content-reader` should route Bilibili links here.

## Role

`bilibili-reader` handles:

- Single-video transcript notes.
- Multi-part videos, collections, and playlists.
- Subtitle-first extraction.
- Local ASR fallback when subtitles are unavailable.
- Highlight timestamps for review.
- Optional original video download.

## Standard Intents

| Intent | Behavior | Script |
|--------|----------|--------|
| `transcript` | Save transcript note | `--action transcript` |
| `download_media` | Download video only | `--action download-media` |
| `transcript_with_media` | Save transcript note and download video | `--action transcript --include-media` |
| `batch_transcript` | Process collection, playlist, or multi-part video | `--action transcript --max-items N` |

## Output Requirements

- Capture interaction data when visible: views, danmaku, likes, coins, favorites, shares, comments.
- `## 内容摘要` must summarize core ideas from the full transcript.
- `## 划重点` must be timestamp plus viewing guidance, not copied subtitle text.

## Configure

Set `obsidian_vault` in `config.json`.

```json
{
  "obsidian_vault": "",
  "note_root": "00-Inbox/Bilibili/知识资源",
  "media_root": "00-Inbox/Bilibili/多媒体",
  "scripts_path": "scripts"
}
```

## Dependencies

- `yt-dlp`: subtitles, metadata, and media download.
- `ffmpeg`: local audio/video handling.
- `faster-whisper`: optional ASR fallback.

Check the environment:

```bash
python3 scripts/bilibili_reader.py --doctor
```

## Maintenance

- Workflow details are in `references/workflow.md`.
- Environment notes are in `references/environment.md`.
- Known failures are in `references/gotchas.md`.
- Update `assets/template-video.md` if note output changes.
- Keep broad trigger phrases in `content-reader`, not here.

## Author

嘉然 | 公众号「嘉然学习笔记」
