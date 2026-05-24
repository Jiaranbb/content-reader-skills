# youtube-reader

Developer notes for the YouTube execution skill. In the full suite, `content-reader` should route YouTube links here.

## Role

`youtube-reader` handles:

- Single-video transcript notes.
- Playlist batch transcript notes.
- Chinese subtitle preference.
- English fallback when Chinese subtitles are unavailable.
- Highlight timestamps for review.
- Optional original video download.

## Standard Intents

| Intent | Behavior | Script |
|--------|----------|--------|
| `transcript` | Save transcript note | `--action transcript` |
| `download_media` | Download video only | `--action download-media` |
| `transcript_with_media` | Save transcript note and download video | `--action transcript --include-media` |
| `batch_transcript` | Process playlist items | `--action transcript --max-items N` |

## Subtitle Strategy

Language order:

```text
zh-Hans -> zh-CN -> zh-Hant -> zh -> en-orig -> en
```

On `429 Too Many Requests`, back off and retry the current language before falling back. Use local ASR only when usable subtitles are unavailable.

## Configure

Set `obsidian_vault` in `config.json`.

```json
{
  "obsidian_vault": "",
  "note_root": "00-Inbox/YouTube/知识资源",
  "media_root": "00-Inbox/YouTube/多媒体",
  "scripts_path": "scripts"
}
```

## Dependencies

- `yt-dlp`: subtitles, metadata, and media download.
- `ffmpeg`: local audio/video handling.
- `faster-whisper`: optional ASR fallback.

Check the environment:

```bash
python3 scripts/youtube_reader.py --doctor
```

## Maintenance

- Workflow details are in `references/workflow.md`.
- Environment notes are in `references/environment.md`.
- Known failures are in `references/gotchas.md`.
- Update `assets/template-video.md` if note output changes.
- Keep broad trigger phrases in `content-reader`, not here.

## Author

嘉然 | 公众号「嘉然学习笔记」
