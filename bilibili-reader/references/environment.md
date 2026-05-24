# Bilibili Reader JR 环境要求

## 固定配置

路径写在 `config.json`：

- `obsidian_vault`: ``
- `note_root`: `00-Inbox/Bilibili/知识资源`
- `media_root`: `00-Inbox/Bilibili/多媒体`
- `asr_model`: `small`

脚本默认读取本 skill 目录下的 `config.json`。不要在执行过程中询问保存路径；需要调整时只改配置文件。

## 必需

- `python3`
- `yt-dlp`

检查：

```bash
python3 --version
yt-dlp --version
```

## 可选但建议

- `faster-whisper`
- `ffmpeg`

`faster-whisper` 只在 B 站平台字幕不可用时作为本地 ASR 兜底。有平台字幕时，不需要它。

## 失败处理

- 缺少 `yt-dlp`：提示用户安装后再继续。
- 缺少 `faster-whisper` 且没有字幕：说明只能拿到元数据，无法生成逐字稿。
- `yt-dlp` 返回会员/登录/地区限制：停止并说明限制，不默认读取浏览器登录态。
