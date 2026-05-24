#!/usr/bin/env python3
"""YouTube transcript/media helper for youtube-reader."""

from __future__ import annotations

import argparse
import glob
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SKILL_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = SKILL_ROOT / "config.json"


def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


CONFIG = load_config()
VAULT_ROOT = Path(str(CONFIG.get("obsidian_vault") or "")).expanduser()
NOTE_ROOT = VAULT_ROOT / str(CONFIG.get("note_root") or "00-Inbox/YouTube/知识资源")
MEDIA_ROOT = VAULT_ROOT / str(CONFIG.get("media_root") or "00-Inbox/YouTube/多媒体")
DEFAULT_ASR_MODEL = str(CONFIG.get("asr_model") or "small")
DEFAULT_MODEL_ROOT = Path(os.getenv("VIDEO_ASR_MODEL_ROOT", str(Path.home() / ".cache/faster-whisper"))).expanduser()
LANG_PRIORITY = ["zh-Hans", "zh-CN", "zh-Hant", "zh", "en-orig", "en"]
SUBTITLE_LANG_ATTEMPTS = ["zh-Hans", "zh-CN", "zh-Hant", "zh", "en-orig", "en"]
SUPPORTED_ASR_MODELS = ("small", "medium")


def compact_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def find_ytdlp() -> str:
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        raise RuntimeError("yt-dlp not found")
    return ytdlp


def sanitize_filename(name: str, limit: int = 80) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name[:limit].rstrip() or "untitled")


def seconds_to_hms(sec: float) -> str:
    value = int(max(0, sec))
    return f"{value // 3600:02d}:{(value % 3600) // 60:02d}:{value % 60:02d}"


def timestamp_to_seconds(value: str) -> float:
    match = re.match(r"(?:(\d+):)?(\d{2}):(\d{2})(?:[.,](\d{1,3}))?", value.strip())
    if not match:
        return 0.0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    millis = int((match.group(4) or "0").ljust(3, "0")[:3])
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def upload_date_to_iso(upload_date: str) -> str:
    if re.fullmatch(r"\d{8}", upload_date or ""):
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    return datetime.now().strftime("%Y-%m-%d")


def append_with_spacing(base: str, piece: str) -> str:
    if not base:
        return piece
    if not piece:
        return base
    if re.match(r"^[,.;:!?，。！？；：、)\]\"'”’]", piece):
        return base + piece
    if re.search(r"[,.;:!?]$", base) and piece[0].isalnum():
        return base + " " + piece
    if base[-1].isalnum() and piece[0].isalnum():
        return base + " " + piece
    return base + piece


def choose_vtt(workdir: Path) -> Optional[Path]:
    candidates = [Path(p) for p in glob.glob(str(workdir / "*.vtt"))]
    if not candidates:
        return None
    for lang in LANG_PRIORITY:
        for candidate in candidates:
            if candidate.name.endswith(f".{lang}.vtt"):
                return candidate
    return sorted(candidates)[0]


def parse_vtt_cues(vtt_text: str) -> List[Dict[str, Any]]:
    cues: List[Dict[str, Any]] = []
    buf: List[str] = []
    in_cue = False
    cue_start = 0.0

    def flush() -> None:
        nonlocal buf
        if not buf:
            return
        text = " ".join(buf)
        text = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        text = re.sub(r"\[(?:music|Music|applause|Applause)\]", " ", text)
        text = text.replace("\u200b", " ")
        text = compact_ws(text)
        if text:
            cues.append({"start": cue_start, "text": text})
        buf = []

    for raw in vtt_text.splitlines():
        stripped = raw.strip("\ufeff").strip()
        if not stripped:
            flush()
            in_cue = False
            continue
        if stripped.startswith(("WEBVTT", "NOTE", "Kind:", "Language:")):
            continue
        if "-->" in stripped:
            flush()
            cue_start = timestamp_to_seconds(stripped.split("-->", 1)[0].strip())
            in_cue = True
            continue
        if re.fullmatch(r"\d+", stripped):
            continue
        if in_cue or stripped:
            buf.append(stripped)
    flush()
    return cues


def merge_cues_with_overlap(cues: List[str]) -> str:
    acc = ""
    for cue in cues:
        cue = cue.strip()
        if not cue:
            continue
        if not acc:
            acc = cue
            continue
        window = acc[-600:]
        if cue in window:
            continue
        overlap = 0
        max_possible = min(len(window), len(cue))
        for size in range(max_possible, 0, -1):
            if window[-size:] == cue[:size]:
                overlap = size
                break
        acc = append_with_spacing(acc, cue[overlap:])
    acc = re.sub(r"\s+([,.!?;:])", r"\1", acc)
    acc = re.sub(r"([，。！？；：、])\s+", r"\1", acc)
    return compact_ws(acc)


def timed_lines_from_cues(cues: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    acc = ""
    sentence = ""
    sentence_start: Optional[float] = None

    def flush_sentence(force: bool = False) -> None:
        nonlocal sentence, sentence_start
        sentence = compact_ws(sentence)
        if not sentence:
            return
        if force or re.search(r"[.!?。！？]$", sentence) or len(sentence) >= 180:
            out.append(f"[{seconds_to_hms(float(sentence_start or 0.0))}] {sentence}")
            sentence = ""
            sentence_start = None

    for cue in cues:
        text = compact_ws(str(cue.get("text") or ""))
        if not text:
            continue
        window = acc[-600:]
        if text in window:
            continue
        overlap = 0
        max_possible = min(len(window), len(text))
        for size in range(max_possible, 0, -1):
            if window[-size:] == text[:size]:
                overlap = size
                break
        piece = compact_ws(text[overlap:])
        if not piece:
            continue
        acc = append_with_spacing(acc, piece)
        if sentence_start is None:
            sentence_start = float(cue.get("start") or 0.0)
        sentence = append_with_spacing(sentence, piece)
        while True:
            match = re.search(r"^(.+?[.!?。！？])\s+(.+)$", sentence)
            if not match:
                break
            first = compact_ws(match.group(1))
            rest = compact_ws(match.group(2))
            if first:
                out.append(f"[{seconds_to_hms(float(sentence_start or 0.0))}] {first}")
            sentence = rest
            sentence_start = float(cue.get("start") or 0.0)
        flush_sentence()
    flush_sentence(force=True)
    return out


def hard_wrap(text: str, width: int = 220) -> List[str]:
    out: List[str] = []
    cur = text.strip()
    while len(cur) > width:
        cut = cur.rfind(" ", 0, width + 1)
        if cut <= 0:
            cut = width
        out.append(cur[:cut].strip())
        cur = cur[cut:].strip()
    if cur:
        out.append(cur)
    return out


def split_lines(text: str) -> List[str]:
    out: List[str] = []
    for part in [p.strip() for p in text.splitlines() if p.strip()]:
        for seg in re.split(r"(?<=[.!?。！？])\s*", part):
            seg = seg.strip()
            if not seg:
                continue
            out.extend(hard_wrap(seg, 220) if len(seg) > 260 else [seg])
    deduped: List[str] = []
    for line in out:
        if deduped and deduped[-1] == line:
            continue
        deduped.append(line)
    return deduped


def parse_timed_transcript(transcript: List[str]) -> List[Tuple[int, str, str]]:
    rows: List[Tuple[int, str, str]] = []
    last_seconds = 0
    for line in transcript:
        text = compact_ws(line)
        if not text:
            continue
        match = re.match(r"^\[(\d{2}:\d{2}:\d{2})\]\s*(.+)$", text)
        if match:
            seconds = int(timestamp_to_seconds(match.group(1)))
            rows.append((seconds, match.group(1), match.group(2).strip()))
            last_seconds = seconds
        else:
            rows.append((last_seconds, seconds_to_hms(last_seconds), text))
    return rows


def sentence_value(text: str) -> int:
    text = compact_ws(text)
    keywords = [
        "key trend", "important", "essentially", "what makes", "different",
        "connectors", "mcp", "skills", "scheduled tasks", "personalization",
        "automate", "execute", "workflow", "report", "presentation", "external tools",
        "核心", "重要", "关键", "总结", "技能", "连接器", "自动化", "定时任务",
    ]
    score = min(len(text), 120)
    lower = text.lower()
    score += sum(25 for keyword in keywords if keyword in lower or keyword in text)
    if re.search(r"^(a key|the important|what makes|generalist|by now|as you work|so by now)", lower):
        score += 60
    return score


def shorten_summary_line(text: str, limit: int = 120) -> str:
    text = compact_ws(text)
    text = re.sub(r"^\[\d{2}:\d{2}:\d{2}\]\s*", "", text)
    text = re.sub(r"^(so|now|okay|all right|and|but|then)[, ]+", "", text, flags=re.I)
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    text = compact_ws(parts[0] if parts else text)
    if len(text) > limit:
        cut = text.rfind(" ", 0, limit + 1)
        if cut <= 0:
            cut = limit
        text = text[:cut].rstrip(" ,.;:，。；：") + "..."
    return text


def build_content_summary(transcript: List[str]) -> str:
    candidates: List[str] = []
    for line in transcript:
        text = shorten_summary_line(line)
        if len(text) < 24:
            continue
        if text not in candidates:
            candidates.append(text)
    ranked = sorted(candidates, key=sentence_value, reverse=True)
    selected: List[str] = []
    for text in ranked:
        if any(text.lower() in item.lower() or item.lower() in text.lower() for item in selected):
            continue
        selected.append(text)
        if len(selected) >= 4:
            break
    if not selected:
        return "- 已保存逐字稿；核心观点需要执行 agent 结合全文补写。"
    return "\n".join(f"- {text}" for text in selected)


def summarize_highlight_window(seed: str, window_texts: List[str]) -> str:
    useful: List[str] = []
    for text in window_texts:
        text = re.sub(r"^\[\d{2}:\d{2}:\d{2}\]\s*", "", compact_ws(text))
        if len(text) < 16 or text in useful:
            continue
        useful.append(text)
        if len(useful) >= 5:
            break
    if not useful:
        return f"从这里看「{seed}」相关内容。"
    ranked = sorted(useful, key=sentence_value, reverse=True)
    topic = seed if len(seed) >= 12 else ranked[0]
    details = [text for text in ranked if text != topic][:2]
    if details:
        body = "；".join(shorten_summary_line(text, 90) for text in details)
        return f"从这里看「{shorten_summary_line(topic, 60)}」：{body}。"
    return f"从这里看「{shorten_summary_line(topic, 80)}」。"


def build_highlights(transcript: List[str], limit: int = 10) -> List[str]:
    rows = parse_timed_transcript(transcript)
    if not rows:
        return ["- 暂无可用时间戳；请先确认字幕或 ASR 转写是否成功。"]
    candidates: List[Tuple[int, int, str, str, int]] = []
    for idx, (seconds, ts, text) in enumerate(rows):
        if len(text) < 16:
            continue
        score = sentence_value(text)
        if idx == 0:
            score += 80
        candidates.append((score, seconds, ts, text, idx))
    selected: List[Tuple[int, str, str, int]] = []
    for score, seconds, ts, text, idx in sorted(candidates, key=lambda item: item[0], reverse=True):
        if any(abs(seconds - chosen_seconds) < 70 for chosen_seconds, _ts, _text, _idx in selected):
            continue
        selected.append((seconds, ts, text, idx))
        if len(selected) >= limit:
            break
    selected.sort(key=lambda item: item[0])
    if not selected:
        return ["- 暂无可用时间戳；请先确认字幕或 ASR 转写是否成功。"]
    output = []
    for seconds, ts, text, idx in selected:
        window_texts = [row_text for row_seconds, _row_ts, row_text in rows[idx:] if row_seconds <= seconds + 90]
        output.append(f"- `{ts}` {summarize_highlight_window(text, window_texts)}")
    return output


def youtube_metadata(ytdlp: str, target: str) -> Dict[str, Any]:
    cmd = [ytdlp, "--extractor-args", "youtube:player_client=android", "--skip-download", "--dump-single-json", target]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"yt-dlp metadata failed: {compact_ws(p.stderr)}")
    data = json.loads(p.stdout)
    if not isinstance(data, dict):
        raise RuntimeError("unexpected yt-dlp metadata payload")
    return data


def expand_targets(url: str, max_items: Optional[int]) -> List[str]:
    ytdlp = find_ytdlp()
    data = youtube_metadata(ytdlp, url)
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        return [url]
    targets: List[str] = []
    for entry in entries:
        if max_items is not None and len(targets) >= max_items:
            break
        if not isinstance(entry, dict):
            continue
        webpage_url = entry.get("webpage_url") or entry.get("url")
        video_id = entry.get("id")
        if isinstance(webpage_url, str) and webpage_url.startswith("http"):
            targets.append(webpage_url)
        elif isinstance(video_id, str):
            targets.append(f"https://www.youtube.com/watch?v={video_id}")
    return targets or [url]


def download_youtube_vtt(ytdlp: str, video_url: str, workdir: Path) -> Tuple[Optional[Path], List[Dict[str, Any]]]:
    attempts: List[Dict[str, Any]] = []
    for lang in SUBTITLE_LANG_ATTEMPTS:
        cmd = [
            ytdlp,
            "--skip-download",
            "--ignore-no-formats-error",
            "--write-auto-subs",
            "--write-subs",
            "--extractor-args",
            "youtube:player_client=android",
            "--sub-langs",
            lang,
            "--sub-format",
            "vtt",
            "-o",
            str(workdir / "%(id)s.%(ext)s"),
            video_url,
        ]
        p = run(cmd)
        detail = compact_ws(p.stderr)[-500:]
        attempts.append({"stage": "youtube_subtitle", "lang": lang, "ok": p.returncode == 0, "detail": detail})
        vtt = choose_vtt(workdir)
        if vtt is not None:
            return vtt, attempts
        if "429" in detail and lang.startswith("zh"):
            time.sleep(3)
            retry = run(cmd)
            retry_detail = compact_ws(retry.stderr)[-500:]
            attempts.append({
                "stage": "youtube_subtitle_retry_after_429",
                "lang": lang,
                "ok": retry.returncode == 0,
                "detail": retry_detail,
            })
            vtt = choose_vtt(workdir)
            if vtt is not None:
                return vtt, attempts
    return None, attempts


def transcript_from_youtube_subtitles(ytdlp: str, video_url: str) -> Tuple[Optional[List[str]], Dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="youtube_reader_subs_") as td:
        vtt, attempts = download_youtube_vtt(ytdlp, video_url, Path(td))
        if vtt is None:
            return None, {"method": "youtube_subtitles", "attempts": attempts, "status": "missing"}
        cues = parse_vtt_cues(vtt.read_text(encoding="utf-8", errors="ignore"))
        lines = timed_lines_from_cues(cues)
        return lines, {"method": "youtube_subtitles", "selected": vtt.name, "attempts": attempts, "status": "ok"}


def resolve_model_arg(asr_model: str) -> Tuple[str, str, Path, Path]:
    model = compact_ws(asr_model).lower()
    if model not in SUPPORTED_ASR_MODELS:
        raise RuntimeError(f"unsupported asr model: {asr_model}")
    model_id = f"Systran/faster-whisper-{model}"
    cache_dir = DEFAULT_MODEL_ROOT / f"models--{model_id.replace('/', '--')}"
    if cache_dir.exists():
        return str(cache_dir), "cache", DEFAULT_MODEL_ROOT, cache_dir
    return model_id, "download", DEFAULT_MODEL_ROOT, cache_dir


def run_local_asr(audio_path: Path, asr_model: str) -> Tuple[List[str], Dict[str, Any]]:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception as e:
        raise RuntimeError("local ASR requires faster-whisper") from e
    model_arg, model_source, model_root, cache_dir = resolve_model_arg(asr_model)
    model = WhisperModel(model_arg, device="cpu", compute_type="int8", download_root=str(model_root))
    segments, info = model.transcribe(str(audio_path), beam_size=5, vad_filter=True, condition_on_previous_text=True)
    lines = []
    for seg in segments:
        text = compact_ws(getattr(seg, "text", ""))
        if text:
            lines.append(f"[{seconds_to_hms(float(getattr(seg, 'start', 0.0) or 0.0))}] {text}")
    if not lines:
        raise RuntimeError("local ASR returned empty transcript")
    return lines, {
        "method": "local_asr",
        "model": asr_model,
        "model_source": model_source,
        "model_cache_dir": str(cache_dir),
        "language": str(getattr(info, "language", "")),
        "duration_sec": float(getattr(info, "duration", 0.0) or 0.0),
    }


def download_audio_temp(ytdlp: str, video_url: str, workdir: Path) -> Path:
    cmd = [ytdlp, "--no-playlist", "-f", "bestaudio/best", "--extractor-args", "youtube:player_client=android", "-o", str(workdir / "%(id)s.%(ext)s"), video_url]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"audio download failed: {compact_ws(p.stderr)}")
    candidates = [Path(p) for p in glob.glob(str(workdir / "*")) if Path(p).suffix.lower() in (".m4a", ".mp3", ".wav", ".flac", ".aac", ".ogg", ".opus", ".mp4", ".webm")]
    if not candidates:
        raise RuntimeError("no audio file downloaded")
    return sorted(candidates)[0]


def get_transcript(ytdlp: str, video_url: str, asr_model: str) -> Tuple[List[str], Dict[str, Any]]:
    lines, meta = transcript_from_youtube_subtitles(ytdlp, video_url)
    if lines:
        return lines, meta
    with tempfile.TemporaryDirectory(prefix="youtube_reader_asr_") as td:
        audio = download_audio_temp(ytdlp, video_url, Path(td))
        asr_lines, asr_meta = run_local_asr(audio, asr_model)
    meta["fallback"] = asr_meta
    return asr_lines, meta


def download_media(ytdlp: str, video_url: str, title: str) -> Path:
    media_dir = MEDIA_ROOT / sanitize_filename(title, 60)
    media_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        ytdlp,
        "--no-playlist",
        "--merge-output-format",
        "mp4",
        "-o",
        str(media_dir / "%(title).100s [%(id)s].%(ext)s"),
        video_url,
    ]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"media download failed: {compact_ws(p.stderr)}")
    files = sorted([p for p in media_dir.iterdir() if p.is_file()])
    if not files:
        raise RuntimeError("media download produced no file")
    return files[-1]


def write_note(info: Dict[str, Any], transcript: List[str], transcript_meta: Dict[str, Any], media_path: Optional[Path]) -> Path:
    NOTE_ROOT.mkdir(parents=True, exist_ok=True)
    title = compact_ws(str(info.get("title") or "YouTube video"))
    video_url = str(info.get("webpage_url") or info.get("original_url") or "")
    uploader = compact_ws(str(info.get("uploader") or info.get("channel") or ""))
    upload_date = upload_date_to_iso(str(info.get("upload_date") or ""))
    duration = seconds_to_hms(float(info.get("duration") or 0.0))
    slug = sanitize_filename(title, 50)
    path = NOTE_ROOT / f"{upload_date}-YouTube-{slug}.md"
    media_block = ""
    if media_path:
        rel = os.path.relpath(media_path, start=path.parent)
        media_block = f"\n## 视频\n\n<video src=\"{rel}\" controls></video>\n"
    content_summary = build_content_summary(transcript)
    highlights = build_highlights(transcript)
    note = f"""---
tags: [YouTube, 视频, 逐字稿, 知识收集]
created: {datetime.now().strftime('%Y-%m-%d')}
type: 知识收集
source: YouTube
author: {uploader}
url: {video_url}
date: {upload_date}
激活:
  写作素材: false
  待试: true
  学习: true
  策展: []
  个人用途: true
note: YouTube 视频逐字稿
---

# {upload_date} {title}

**作者：** {uploader}
**来源：** YouTube
**原链接：** [{video_url}]({video_url})
**发布时间：** {upload_date}
**时长：** {duration}

---

## 内容摘要

{content_summary}
{media_block}
---

## 划重点

{chr(10).join(highlights)}

---

## 媒体文字内容

字幕来源：{transcript_meta.get('method', 'unknown')}
字幕文件：{transcript_meta.get('selected', '-')}

{chr(10).join(transcript)}

---

*由 GPT-5 提取保存*
"""
    path.write_text(note, encoding="utf-8")
    return path


def process_video(video_url: str, action: str, asr_model: str, include_media: bool) -> Dict[str, Any]:
    ytdlp = find_ytdlp()
    info = youtube_metadata(ytdlp, video_url)
    real_url = str(info.get("webpage_url") or video_url)
    title = compact_ws(str(info.get("title") or "YouTube video"))
    if action == "download-media":
        media = download_media(ytdlp, real_url, title)
        return {"url": real_url, "media": str(media)}
    transcript, meta = get_transcript(ytdlp, real_url, asr_model)
    media_path = download_media(ytdlp, real_url, title) if include_media else None
    note = write_note(info, transcript, meta, media_path)
    return {"url": real_url, "note": str(note), "line_count": len(transcript), "method": meta.get("method"), "media": str(media_path) if media_path else None}


def main() -> int:
    parser = argparse.ArgumentParser(description="Save YouTube transcript notes or media")
    parser.add_argument("--url", required=True, help="YouTube video, playlist, channel playlist, or youtu.be URL")
    parser.add_argument("--action", choices=("transcript", "download-media"), default="transcript")
    parser.add_argument("--include-media", action="store_true", help="Download video media after writing transcript note")
    parser.add_argument("--max-items", type=int, default=None, help="Limit playlist/batch items")
    parser.add_argument("--asr-model", choices=SUPPORTED_ASR_MODELS, default=DEFAULT_ASR_MODEL)
    args = parser.parse_args()

    targets = expand_targets(args.url, args.max_items)
    results = []
    for target in targets:
        try:
            results.append(process_video(target, args.action, args.asr_model, args.include_media))
        except Exception as e:
            results.append({"url": target, "error": str(e)})
    print(json.dumps({"count": len(results), "results": results}, ensure_ascii=False, indent=2))
    return 1 if any("error" in item for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
